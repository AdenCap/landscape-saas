import json
from calendar import monthrange
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.db.models import Sum, DecimalField, Count, F, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect
from urllib.parse import urlencode
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.management import call_command

from accounts.decorators import role_required
from accounts.utils import get_business
from accounts.models import User
from businesses.models import Business
from jobs.models import Job, JobServiceItem, Crew
from billing.models import Invoice, Estimate
from customers.models import ClientMessage, Customer
from subscription.models import StripeWebhookEvent




def _previous_pay_date(next_pay_date, sorted_days):
    """Given next_pay_date and sorted list of day-of-month (e.g. [1, 15]), return the previous pay date (period start)."""
    if not sorted_days:
        return None
    # Same month: largest pay day strictly before next_pay_date.day
    prev_same_month = [d for d in sorted_days if d < next_pay_date.day]
    if prev_same_month:
        prev_day = max(prev_same_month)
        last = monthrange(next_pay_date.year, next_pay_date.month)[1]
        return next_pay_date.replace(day=min(prev_day, last))
    # Previous month: use last pay day of that month
    if next_pay_date.month == 1:
        prev_year, prev_month = next_pay_date.year - 1, 12
    else:
        prev_year, prev_month = next_pay_date.year, next_pay_date.month - 1
    last = monthrange(prev_year, prev_month)[1]
    prev_day = min(sorted_days[-1], last)
    return date(prev_year, prev_month, prev_day)


def _month_range(d: date):
    start = d.replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def _year_range(d: date):
    start = date(d.year, 1, 1)
    end = date(d.year + 1, 1, 1)
    return start, end


def _onboarding_skip_key(business_id):
    return f"onboarding_skipped_steps:{business_id}"


def _onboarding_return_url(step_key):
    return "/dashboard/onboarding/?" + urlencode({"step": step_key})


@role_required("owner", "manager")
def owner_onboarding(request):
    business = get_business(request)
    if not business:
        if request.user.is_superuser:
            return redirect("platform_home")
        return redirect("/accounts/login/")

    from businesses.context_processors import TERMINOLOGY, DEFAULT_TERMS
    terms = dict(TERMINOLOGY.get(business.business_type or "general", DEFAULT_TERMS))
    overrides = business.terminology_overrides
    if overrides and isinstance(overrides, dict):
        terms.update(overrides)

    customers_count = Customer.objects.filter(business=business).count()
    jobs_count = Job.objects.filter(property__customer__business=business).count()
    smtp_connected = bool(getattr(business, "email_smtp_user", "") and getattr(business, "email_smtp_password", ""))
    stripe_connected = bool(getattr(business, "stripe_connect_account_id", ""))

    modules = business.enabled_modules or []

    checklist = [
        {
            "key": "business_profile",
            "label": "Business profile",
            "hint": "Add your company name, address, and logo so invoices look professional.",
            "done": bool(business.name),
            "action_url": "/settings/",
            "action_label": "Open Settings",
            "optional": False,
        },
        {
            "key": "first_customer",
            "label": "Add your first customer",
            "hint": "Add a customer manually or import from a CSV file.",
            "done": customers_count > 0,
            "action_url": "/clients/add/",
            "action_label": "Add Customer",
            "secondary_action_url": "/clients/import/",
            "secondary_action_label": "Import CSV",
            "optional": False,
        },
        {
            "key": "first_job",
            "label": f"Create a {terms['job'].lower()}",
            "hint": f"Schedule your first {terms['job'].lower()} to start tracking work and generating invoices.",
            "done": jobs_count > 0,
            "action_url": "/jobs/create/",
            "action_label": f"Create {terms['job']}",
            "optional": False,
        },
        {
            "key": "first_estimate",
            "label": f"Create a {terms['estimate'].lower()} or invoice",
            "hint": f"Send a professional {terms['estimate'].lower()} or invoice to a customer.",
            "done": Invoice.objects.filter(business=business).exists() or Estimate.objects.filter(business=business).exists(),
            "action_url": "/billing/estimates/create/",
            "action_label": f"Create {terms['estimate']}",
            "optional": False,
        },
    ]

    # ── Vertical-specific optional steps based on enabled modules ───
    if "pricebook" in modules:
        from pricebook.models import PricebookItem
        checklist.append({
            "key": "pricebook",
            "label": "Set up your pricebook",
            "hint": f"Add {terms['material'].lower()}s and services with pricing so you can quickly build {terms['estimate'].lower()}s.",
            "done": PricebookItem.objects.filter(business=business).exists(),
            "action_url": "/pricebook/",
            "action_label": "Open Pricebook",
            "optional": True,
        })

    if "equipment" in modules:
        from equipment.models import Equipment
        checklist.append({
            "key": "equipment",
            "label": "Add customer equipment",
            "hint": "Track equipment at customer properties for service history and warranty tracking.",
            "done": Equipment.objects.filter(business=business).exists(),
            "action_url": "/equipment/",
            "action_label": "Add Equipment",
            "optional": True,
        })

    if "checklists" in modules:
        from checklists.models import ChecklistTemplate
        checklist.append({
            "key": "checklist_template",
            "label": "Create a checklist template",
            "hint": f"Build reusable checklists your {terms['crew_member'].lower()}s complete on every {terms['job'].lower()}.",
            "done": ChecklistTemplate.objects.filter(business=business).exists(),
            "action_url": "/checklists/",
            "action_label": "Create Checklist",
            "optional": True,
        })

    if "inspections" in modules:
        from inspections.models import InspectionTemplate
        checklist.append({
            "key": "inspection_template",
            "label": "Create an inspection template",
            "hint": "Set up inspection forms for site visits and equipment evaluations.",
            "done": InspectionTemplate.objects.filter(business=business).exists(),
            "action_url": "/inspections/",
            "action_label": "Create Template",
            "optional": True,
        })

    # Core optional steps at the end
    checklist.extend([
        {
            "key": "smtp",
            "label": "Connect email",
            "hint": f"Set up SMTP so Tradevo can send {terms['estimate'].lower()}s and invoices on your behalf.",
            "done": smtp_connected,
            "action_url": "/settings/",
            "action_label": "Connect Email",
            "optional": True,
        },
        {
            "key": "payments",
            "label": "Connect payments",
            "hint": "Link Stripe to accept card payments directly from invoices.",
            "done": stripe_connected,
            "action_url": "/billing/connect/onboarding/",
            "action_label": "Connect Stripe",
            "optional": True,
        },
    ])

    skipped_steps = set(request.session.get(_onboarding_skip_key(business.id), []))
    for item in checklist:
        item["skipped"] = item["key"] in skipped_steps
        item["effective_done"] = item["done"] or item["skipped"]
        item["action_url"] = item["action_url"] + "?" + urlencode({"next": _onboarding_return_url(item["key"])})
        if item.get("secondary_action_url"):
            item["secondary_action_url"] = item["secondary_action_url"] + "?" + urlencode({"next": _onboarding_return_url(item["key"])})

    done_count = sum(1 for item in checklist if item["effective_done"])
    completion_pct = int((done_count / len(checklist)) * 100)

    step_keys = [item["key"] for item in checklist]
    first_incomplete_key = next((item["key"] for item in checklist if not item["effective_done"]), step_keys[0])
    current_step = request.GET.get("step") or first_incomplete_key
    if current_step not in step_keys:
        current_step = first_incomplete_key
    current_index = step_keys.index(current_step)
    current_item = checklist[current_index]
    prev_step = step_keys[current_index - 1] if current_index > 0 else None
    next_step = step_keys[current_index + 1] if current_index < len(step_keys) - 1 else None

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        target_step = (request.POST.get("step") or "").strip()
        if action in {"skip", "unskip"} and target_step in step_keys:
            skip_key = _onboarding_skip_key(business.id)
            current_skipped = set(request.session.get(skip_key, []))
            item = next((x for x in checklist if x["key"] == target_step), None)
            if not item:
                return redirect(_onboarding_return_url(current_step))
            if not item.get("optional"):
                messages.warning(request, "Only optional steps can be skipped.")
                return redirect(_onboarding_return_url(target_step))
            if action == "skip":
                current_skipped.add(target_step)
                messages.info(request, f"Skipped optional step: {item['label']}")
            else:
                current_skipped.discard(target_step)
                messages.info(request, f"Restored step: {item['label']}")
            request.session[skip_key] = sorted(current_skipped)
            request.session.modified = True
            return redirect(_onboarding_return_url(target_step))

        # Skip entire onboarding — user doesn't want to be bothered
        if action == "skip_onboarding":
            business.onboarding_completed = True
            business.onboarding_completed_at = timezone.now()
            business.save(update_fields=["onboarding_completed", "onboarding_completed_at"])
            request.session.pop(_onboarding_skip_key(business.id), None)
            messages.info(request, "Setup skipped. You can always configure things from Settings.")
            return redirect("owner_dashboard")

        # Allow completion once core operational steps are done.
        core_ready = customers_count > 0 and jobs_count > 0
        if not core_ready:
            messages.warning(request, "Add at least one customer and one job before finishing, or click \"Skip setup\" to go straight to the dashboard.")
        else:
            business.onboarding_completed = True
            business.onboarding_completed_at = timezone.now()
            business.save(update_fields=["onboarding_completed", "onboarding_completed_at"])
            request.session.pop(_onboarding_skip_key(business.id), None)
            messages.success(request, "Setup complete! Welcome to your dashboard.")
            return redirect("owner_dashboard")

    return render(request, "dashboard/onboarding.html", {
        "business": business,
        "checklist": checklist,
        "done_count": done_count,
        "total_count": len(checklist),
        "completion_pct": completion_pct,
        "customers_count": customers_count,
        "jobs_count": jobs_count,
        "smtp_connected": smtp_connected,
        "stripe_connected": stripe_connected,
        "current_step": current_step,
        "current_item": current_item,
        "current_step_number": current_index + 1,
        "prev_step": prev_step,
        "next_step": next_step,
    })


@role_required("owner", "manager")
def dispatch_command_center(request):
    business = get_business(request)
    if not business:
        if request.user.is_superuser:
            return redirect("platform_home")
        return redirect("/accounts/login/")

    today = timezone.localdate()
    now_local = timezone.localtime()

    delayed_jobs = Job.objects.filter(
        property__customer__business=business,
        scheduled_date=today,
        status="scheduled",
        scheduled_time__isnull=False,
        scheduled_time__lt=now_local.time(),
    ).select_related("property__customer", "assigned_to", "assigned_crew").order_by("scheduled_time")[:25]

    unassigned_jobs = Job.objects.filter(
        property__customer__business=business,
        scheduled_date=today,
        status="scheduled",
        assigned_to__isnull=True,
        assigned_crew__isnull=True,
    ).select_related("property__customer").order_by("scheduled_time")[:25]

    crew_load = (
        Job.objects.filter(property__customer__business=business, scheduled_date=today)
        .values("assigned_crew__name")
        .annotate(total=Count("id"))
        .order_by("total")
    )

    overdue_invoices = Invoice.objects.filter(
        business=business,
        status="sent",
        due_date__lt=today,
    ).select_related("customer").order_by("due_date")[:25]

    late_risk = []
    for inv in overdue_invoices:
        customer = inv.customer
        customer_overdue_count = Invoice.objects.filter(
            business=business,
            customer=customer,
            status="sent",
            due_date__lt=today,
        ).count()
        days_overdue = (today - inv.due_date).days if inv.due_date else 0
        score = 0
        if days_overdue >= 30:
            score += 2
        if customer_overdue_count >= 2:
            score += 2
        if inv.total >= 1000:
            score += 1
        flag = "High" if score >= 4 else ("Medium" if score >= 2 else "Low")
        late_risk.append({"invoice": inv, "days_overdue": days_overdue, "flag": flag})

    suggestions = []
    if delayed_jobs.count() >= 3:
        suggestions.append("Delay chain detected: move low-priority jobs to tomorrow and notify clients automatically.")
    if unassigned_jobs.count() > 0:
        suggestions.append(f"Assign {unassigned_jobs.count()} unassigned jobs to available crews to avoid same-day spillover.")
    if overdue_invoices.count() > 0:
        suggestions.append("Trigger payment reminders for overdue invoices and prioritize high-risk accounts.")
    if not suggestions:
        suggestions.append("Day looks stable. Focus on finishing active jobs and collecting completion photos.")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "fix_my_day":
            messages.success(request, "Fix My Day generated: dispatch suggestions refreshed and priorities ranked.")
        elif action == "run_collection_autopilot":
            try:
                call_command("send_invoice_reminders", force=True)
                messages.success(request, "Cash Flow Autopilot ran invoice reminders successfully.")
            except Exception as e:
                messages.error(request, f"Autopilot run failed: {e}")
        elif action == "auto_assign_unassigned":
            crews = list(Crew.objects.filter(business=business).order_by("name"))
            if not crews:
                messages.warning(request, "No crews available for auto-assign.")
            else:
                assigned_count = 0
                for job in unassigned_jobs:
                    least = min(
                        crews,
                        key=lambda c: Job.objects.filter(
                            property__customer__business=business,
                            scheduled_date=today,
                            assigned_crew=c,
                            status__in=["scheduled", "in_progress"],
                        ).count(),
                    )
                    job.assigned_crew = least
                    job.assigned_to = None
                    job.save(update_fields=["assigned_crew", "assigned_to"])
                    assigned_count += 1
                messages.success(request, f"Auto-assigned {assigned_count} unassigned job(s) to least-loaded crews.")

    return render(request, "dashboard/dispatch_command_center.html", {
        "today": today,
        "delayed_jobs": delayed_jobs,
        "unassigned_jobs": unassigned_jobs,
        "crew_load": list(crew_load),
        "overdue_invoices": overdue_invoices,
        "late_risk": late_risk,
        "suggestions": suggestions,
    })


@role_required("owner", "manager")
def reliability_center(request):
    business = get_business(request)
    if not business:
        if request.user.is_superuser:
            return redirect("platform_home")
        return redirect("/accounts/login/")

    if request.method == "POST" and request.POST.get("action") == "retry_failed_webhooks":
        try:
            call_command("retry_failed_webhooks", limit=50)
            messages.success(request, "Triggered retry for failed webhooks.")
        except Exception as e:
            messages.error(request, f"Webhook retry failed: {e}")

    recent_webhooks = StripeWebhookEvent.objects.order_by("-created_at")[:30]
    webhook_failures = StripeWebhookEvent.objects.filter(processed=False).count()
    retry_candidates = []
    for w in StripeWebhookEvent.objects.filter(processed=False).order_by("created_at")[:15]:
        age_min = int((timezone.now() - w.created_at).total_seconds() // 60)
        # simple progressive retry hint curve
        if age_min < 5:
            next_retry = "in ~5 min"
        elif age_min < 30:
            next_retry = "in ~15 min"
        elif age_min < 120:
            next_retry = "in ~60 min"
        else:
            next_retry = "manual review recommended"
        retry_candidates.append({"event": w, "age_min": age_min, "next_retry": next_retry})

    stripe_connected = bool(getattr(business, "stripe_connect_account_id", ""))
    smtp_connected = bool(getattr(business, "email_smtp_user", "") and getattr(business, "email_smtp_password", ""))

    health_alerts = []
    if not smtp_connected:
        health_alerts.append("SMTP not connected — invoice/estimate sending can fail.")
    if not stripe_connected:
        health_alerts.append("Stripe Connect not connected — card payments unavailable.")
    if webhook_failures:
        health_alerts.append(f"{webhook_failures} unprocessed Stripe webhook events need review.")
    if not health_alerts:
        health_alerts.append("All core integrations look healthy.")

    return render(request, "dashboard/reliability_center.html", {
        "recent_webhooks": recent_webhooks,
        "stripe_connected": stripe_connected,
        "smtp_connected": smtp_connected,
        "webhook_failures": webhook_failures,
        "retry_candidates": retry_candidates,
        "health_alerts": health_alerts,
    })


@role_required("owner", "manager")
def owner_dashboard(request):
    today = timezone.localdate()
    business = get_business(request)
    if not business:
        if request.user.is_superuser:
            return redirect("platform_home")
        return redirect("/accounts/login/")

    if not getattr(business, "onboarding_completed", False):
        return redirect("owner_onboarding")

    month_start, month_end = _month_range(today)
    year_start, year_end = _year_range(today)

    # --- Revenue this month (paid invoices) ---
    revenue_this_month = Invoice.objects.filter(
        business=business,
        status="paid",
        period_start__gte=month_start,
        period_start__lt=month_end,
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]

    # --- Revenue this year (paid invoices) ---
    revenue_this_year = Invoice.objects.filter(
        business=business,
        status="paid",
        period_start__gte=year_start,
        period_start__lt=year_end,
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]

    # --- Invoices overdue (sent, due_date < today) ---
    overdue_qs = Invoice.objects.filter(
        business=business,
        status="sent",
        due_date__lt=today,
        due_date__isnull=False,
    )
    overdue_agg = overdue_qs.aggregate(
        count=Count("id"),
        total=Coalesce(
            Sum("total"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )
    invoices_overdue_count = overdue_agg["count"] or 0
    invoices_overdue_total = overdue_agg["total"] or Decimal("0.00")

    # --- Overdue aging: 0-30, 30-60, 60+ days past due ---
    day_30 = today - timedelta(days=30)
    day_60 = today - timedelta(days=60)
    overdue_base = dict(business=business, status="sent", due_date__isnull=False)
    agg = lambda qs: qs.aggregate(
        count=Count("id"),
        total=Coalesce(Sum("total"), Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
    )
    qs_0_30 = Invoice.objects.filter(**overdue_base, due_date__gte=day_30, due_date__lt=today)
    qs_30_60 = Invoice.objects.filter(**overdue_base, due_date__gte=day_60, due_date__lt=day_30)
    qs_60_plus = Invoice.objects.filter(**overdue_base, due_date__lt=day_60)
    overdue_0_30 = agg(qs_0_30)
    overdue_30_60 = agg(qs_30_60)
    overdue_60_plus = agg(qs_60_plus)

    # --- Outstanding AR (sent, unpaid) ---
    ar_outstanding = Invoice.objects.filter(
        business=business,
        status="sent",
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]

    # --- Jobs today ---
    jobs_today = Job.objects.filter(property__customer__business=business, scheduled_date=today).count()

    # --- Work completed this month (total $ of completed jobs, not payments received) ---
    work_completed_this_month = (
        JobServiceItem.objects.filter(
            job__property__customer__business=business,
            job__status="completed",
            job__scheduled_date__gte=month_start,
            job__scheduled_date__lt=month_end,
        ).aggregate(
            total=Coalesce(
                Sum(F("quantity") * F("unit_price")),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )["total"]
    )

    # --- Profit this month (revenue − costs) ---
    from financials.models import Receipt
    from time_tracking.models import TimeEntry
    receipts_this_month = (
        Receipt.objects.filter(
            business=business,
            receipt_date__gte=month_start,
            receipt_date__lt=month_end,
        ).aggregate(Sum("amount"))["amount__sum"] or Decimal("0")
    )
    time_entries_month = TimeEntry.objects.filter(
        user__business=business,
        clock_out__isnull=False,
        clock_in__date__gte=month_start,
        clock_in__date__lt=month_end,
    ).select_related("user")
    labor_this_month = Decimal("0")
    for e in time_entries_month:
        rate = (e.user.hourly_rate or Decimal("0"))
        mins = e.duration_minutes or 0
        labor_this_month += Decimal(str(mins)) / Decimal("60") * rate
    costs_this_month = receipts_this_month + labor_this_month
    profit_this_month = revenue_this_month - costs_this_month

    # --- Client messages: latest only (read-only on dashboard), unread count ---
    client_messages = list(
        ClientMessage.objects.filter(customer__business=business)
        .select_related("customer")
        .order_by("-created_at")[:20]
    )
    unread_messages_count = ClientMessage.objects.filter(
        customer__business=business,
        direction=ClientMessage.DIRECTION_RECEIVED,
        is_read=False,
    ).count()

    # --- Payroll balance: total to pay at next pay date (hours in current period × hourly rate) ---
    payroll_balance = None
    next_pay_date = None
    pay_frequency_label = None
    if getattr(business, "pay_frequency", None) and getattr(business, "next_pay_date", None):
        freq = business.pay_frequency
        if freq == "custom":
            if not getattr(business, "pay_period_days", None):
                pass  # custom selected but no days set — skip payroll balance
            else:
                period_days = business.pay_period_days
                next_pay_date = business.next_pay_date
                period_start = next_pay_date - timedelta(days=period_days)
                period_end = next_pay_date
                time_entries = TimeEntry.objects.filter(
                    user__business=business,
                    clock_out__isnull=False,
                    clock_in__date__gte=period_start,
                    clock_in__date__lte=period_end,
                ).select_related("user")
                payroll_balance = Decimal("0")
                for e in time_entries:
                    rate = e.user.hourly_rate or Decimal("0")
                    mins = e.duration_minutes or 0
                    payroll_balance += Decimal(str(mins)) / Decimal("60") * rate
                pay_frequency_label = f"Every {business.pay_period_days} days"
        elif freq == "custom_dates":
            days = getattr(business, "pay_specific_days", None) or []
            if not isinstance(days, list) or not days or not business.next_pay_date:
                pass
            else:
                sorted_days = []
                for d in days:
                    try:
                        n = int(d)
                        if 1 <= n <= 31:
                            sorted_days.append(n)
                    except (TypeError, ValueError):
                        continue
                sorted_days = sorted(set(sorted_days))
                if not sorted_days:
                    pass
                else:
                    next_pay_date = business.next_pay_date
                    period_start = _previous_pay_date(next_pay_date, sorted_days)
                    if period_start is None:
                        period_start = next_pay_date - timedelta(days=15)  # fallback
                    period_end = next_pay_date
                    time_entries = TimeEntry.objects.filter(
                        user__business=business,
                        clock_out__isnull=False,
                        clock_in__date__gte=period_start,
                        clock_in__date__lte=period_end,
                    ).select_related("user")
                    payroll_balance = Decimal("0")
                    for e in time_entries:
                        rate = e.user.hourly_rate or Decimal("0")
                        mins = e.duration_minutes or 0
                        payroll_balance += Decimal(str(mins)) / Decimal("60") * rate
                    pay_frequency_label = "Specific dates (" + ", ".join(str(d) for d in sorted_days) + ")"
        else:
            next_pay_date = business.next_pay_date
            period_days = {"weekly": 7, "biweekly": 14, "semimonthly": 15, "monthly": 30}.get(freq, 14)
            period_start = next_pay_date - timedelta(days=period_days)
            period_end = next_pay_date
            time_entries = TimeEntry.objects.filter(
                user__business=business,
                clock_out__isnull=False,
                clock_in__date__gte=period_start,
                clock_in__date__lte=period_end,
            ).select_related("user")
            payroll_balance = Decimal("0")
            for e in time_entries:
                rate = e.user.hourly_rate or Decimal("0")
                mins = e.duration_minutes or 0
                payroll_balance += Decimal(str(mins)) / Decimal("60") * rate
            pay_frequency_label = dict(Business.PAY_FREQUENCY_CHOICES).get(freq, freq)

    review_qs = Customer.objects.filter(business=business)
    review_stats = {
        "review_asked": review_qs.filter(google_review_status="asked").count(),
        "review_completed": review_qs.filter(google_review_status="reviewed").count(),
        "review_opted_out": review_qs.filter(google_review_status="opted_out").count(),
    }
    total_review_contacts = sum(review_stats.values())
    review_stats["review_conversion_pct"] = round((review_stats["review_completed"] / total_review_contacts) * 100, 1) if total_review_contacts else 0

    crew_user_count = User.objects.filter(business=business, role="crew", is_active=True).count()
    solo_plan_overage = business.subscription_plan_tier == "solo" and crew_user_count > 1

    day_start = timezone.now() - timedelta(hours=24)
    changes_feed = []
    recent_jobs = Job.objects.filter(property__customer__business=business, created_at__gte=day_start).select_related("property__customer").order_by("-created_at")[:6]
    for j in recent_jobs:
        changes_feed.append({"time": timezone.localtime(j.created_at), "text": f"Job created: {j.property.customer.name} · {j.property.address}"})
    recent_invoices = Invoice.objects.filter(business=business, issue_date__gte=(today - timedelta(days=1))).select_related("customer").order_by("-issue_date")[:6]
    for inv in recent_invoices:
        inv_time = timezone.make_aware(datetime.combine(inv.issue_date, datetime.min.time()))
        changes_feed.append({"time": inv_time, "text": f"Invoice #{inv.id} ({inv.status}) · {inv.customer.name}"})
    recent_messages = ClientMessage.objects.filter(customer__business=business, created_at__gte=day_start).select_related("customer").order_by("-created_at")[:6]
    for msg in recent_messages:
        changes_feed.append({"time": timezone.localtime(msg.created_at), "text": f"{msg.get_direction_display()} {msg.get_channel_display()} · {msg.customer.name}"})
    changes_feed = sorted(changes_feed, key=lambda x: x["time"], reverse=True)[:10]

    context = {
        "today": today,
        "revenue_this_month": revenue_this_month,
        "revenue_this_year": revenue_this_year,
        "work_completed_this_month": work_completed_this_month,
        "year_start": year_start,
        "year_end": year_end,
        "profit_this_month": profit_this_month,
        "invoices_overdue_count": invoices_overdue_count,
        "invoices_overdue_total": invoices_overdue_total,
        "overdue_0_30": overdue_0_30,
        "overdue_30_60": overdue_30_60,
        "overdue_60_plus": overdue_60_plus,
        "ar_outstanding": ar_outstanding,
        "jobs_today": jobs_today,
        "month_start": month_start,
        "month_end": month_end,
        "client_messages": client_messages,
        "unread_messages_count": unread_messages_count,
        "payroll_balance": payroll_balance,
        "next_pay_date": next_pay_date,
        "pay_frequency_label": pay_frequency_label,
        "changes_feed": changes_feed,
        "crew_user_count": crew_user_count,
        "solo_plan_overage": solo_plan_overage,
        **review_stats,
    }
    return render(request, "dashboard/owner_dashboard.html", context)


from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_date
from time_tracking.models import TimeEntry, TimeOffRequest, EmployeeSchedule
from jobs.models import Crew
from accounts.models import EmployeePayment


def _hours_from_minutes(minutes):
    if minutes is None:
        return Decimal("0")
    return Decimal(str(minutes)) / Decimal("60")


def _schedule_rows_for_user(user):
    """Build schedule_rows (day_name, slot) for a user."""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    slots = {s.day_of_week: s for s in EmployeeSchedule.objects.filter(user=user)}
    return [(day_names[i], slots.get(i)) for i in range(7)]


@role_required("owner", "manager", "crew")
def employee_management(request):
    """Combined page: Employees, Timesheets, Crews, Payroll, Time off, Schedule. Crew only sees Time off and Schedule."""
    business = get_business(request)
    if not business:
        if request.user.is_superuser:
            return redirect("platform_home")
        return redirect("/")

    is_owner = getattr(request.user, "role", None) in ("owner", "manager")

    # Owner-only data (crew gets empty)
    today = timezone.localdate()
    if is_owner:
        employees = User.objects.filter(business=business).order_by("role", "first_name", "last_name", "username")
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(year=today.year + 1, month=1, day=1)
        crew_users = User.objects.filter(role="crew", business=business).order_by("username")
        employee_stats = []
        for user in crew_users:
            rate = getattr(user, "hourly_rate", None) or Decimal("0")
            week_entries = TimeEntry.objects.filter(
                user=user, status="approved", clock_out__isnull=False,
                clock_in__date__gte=week_start, clock_in__date__lt=week_end,
            )
            week_minutes = sum(e.duration_minutes or 0 for e in week_entries)
            year_entries = TimeEntry.objects.filter(
                user=user, status="approved", clock_out__isnull=False,
                clock_in__date__gte=year_start, clock_in__date__lt=year_end,
            )
            year_minutes = sum(e.duration_minutes or 0 for e in year_entries)
            week_cost = _hours_from_minutes(week_minutes) * rate
            year_cost = _hours_from_minutes(year_minutes) * rate
            employee_stats.append({
                "user": user, "hourly_rate": rate,
                "week_minutes": week_minutes, "week_display": f"{week_minutes // 60}h {week_minutes % 60}m",
                "week_cost": week_cost,
                "year_minutes": year_minutes, "year_display": f"{year_minutes // 60}h {year_minutes % 60}m",
                "year_cost": year_cost,
            })
        total_week_cost = sum(s["week_cost"] for s in employee_stats)
        total_year_cost = sum(s["year_cost"] for s in employee_stats)
        crews = Crew.objects.filter(business=business).prefetch_related("members", "crew_leader").order_by("name")
        payroll_payments = (
            EmployeePayment.objects.filter(business=business)
            .select_related("employee")
            .order_by("-paid_date", "-created_at")
        )
        payroll_total = sum(p.amount for p in payroll_payments)
        pending_time_entries_qs = TimeEntry.objects.filter(
            user__business_id=business.id,
            status="pending_approval",
            clock_out__isnull=False,
        ).select_related("user").order_by("-clock_in")
        pending_time_entries_count = pending_time_entries_qs.count()
        pending_time_entries = list(pending_time_entries_qs[:50])
        # JSON for modal dropdowns
        all_employees_json = json.dumps([
            {"id": u.id, "name": u.get_full_name() or u.username, "hourly_rate": str(u.hourly_rate or "0")}
            for u in employees
        ])
        crew_users_json = json.dumps([
            {"id": u.id, "name": u.get_full_name() or u.username}
            for u in crew_users
        ])
        # Time off: all requests for business; schedule: pick employee
        time_off_requests = TimeOffRequest.objects.filter(business=business).select_related("user", "reviewed_by").order_by("-start_date", "-created_at")
        schedule_employees = User.objects.filter(business=business, role="crew").order_by("first_name", "last_name", "username")
        schedule_selected_id = request.GET.get("schedule_user_id")
        schedule_selected_user = get_object_or_404(User, pk=schedule_selected_id, business=business, role="crew") if schedule_selected_id else schedule_employees.first()
        schedule_rows = _schedule_rows_for_user(schedule_selected_user) if schedule_selected_user else []
    else:
        employees = []
        employee_stats = []
        total_week_cost = total_year_cost = Decimal("0")
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(year=today.year + 1, month=1, day=1)
        crews = []
        payroll_payments = []
        payroll_total = Decimal("0")
        pending_time_entries_count = 0
        pending_time_entries = []
        all_employees_json = "[]"
        crew_users_json = "[]"
        time_off_requests = TimeOffRequest.objects.filter(user=request.user).select_related("reviewed_by").order_by("-start_date", "-created_at")
        schedule_employees = []
        schedule_selected_user = request.user
        schedule_rows = _schedule_rows_for_user(request.user)

    return render(request, "dashboard/employee_management.html", {
        "employees": employees,
        "employee_stats": employee_stats,
        "week_start": week_start,
        "week_end": week_end,
        "year_start": year_start,
        "year_end": year_end,
        "total_week_cost": total_week_cost,
        "total_year_cost": total_year_cost,
        "crews": crews,
        "payroll_payments": payroll_payments,
        "payroll_total": payroll_total,
        "is_owner": is_owner,
        "time_off_requests": time_off_requests,
        "schedule_employees": schedule_employees,
        "schedule_selected_user": schedule_selected_user,
        "schedule_rows": schedule_rows,
        "time_off_employees": User.objects.filter(business=business, role="crew").order_by("first_name", "last_name", "username") if is_owner else [],
        "pending_time_entries_count": pending_time_entries_count,
        "pending_time_entries": pending_time_entries,
        "all_employees_json": all_employees_json,
        "crew_users_json": crew_users_json,
        "today_iso": today.isoformat(),
    })


@role_required("owner", "manager")
def crew_day_detail(request, user_id):
    User = get_user_model()
    crew_user = get_object_or_404(User, id=user_id, role="crew")

    # optional ?date=YYYY-MM-DD
    date_str = request.GET.get("date")
    day = parse_date(date_str) if date_str else timezone.localdate()
    if day is None:
        day = timezone.localdate()

    jobs = (
        Job.objects.select_related("property")
        .filter(assigned_to=crew_user, scheduled_date=day)
        .order_by("route_order", "id")
    )

    completed = jobs.filter(status="completed").count()
    total = jobs.count()

    return render(request, "dashboard/crew_day_detail.html", {
        "crew_user": crew_user,
        "day": day,
        "jobs": jobs,
        "completed": completed,
        "total": total,
    })
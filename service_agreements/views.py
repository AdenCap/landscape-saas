import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods

from accounts.decorators import role_required
from accounts.utils import get_business
from customers.models import Customer, Property
from jobs.models import Job, JobServiceItem
from pricing.models import ServiceTemplate
from pricing.utils import get_effective_rate
from .models import ServiceAgreement, AgreementVisit, AgreementLineItem
from jobs.models import RecurringJob


def _sync_contract_to_hubs(agreement, prop, business):
    """Auto-enroll in Mowing Hub and Fertilization Hub based on contract line items.
    Skips if the client is already enrolled in the respective hub.
    If a line item contains 'mow' → create RecurringJob for Mowing Hub.
    If a line item contains 'fert', 'weed control', or 'lawn treatment' → create Fertilization enrollment."""

    for li in agreement.line_items.all():
        svc_lower = li.service_name.lower()

        # ── Mowing sync ──
        if "mow" in svc_lower:
            # Check if this property already has an active mowing RecurringJob
            already_mowing = RecurringJob.objects.filter(property=prop, active=True).exists()
            if already_mowing:
                continue  # Already a mowing client — skip

            mowing_svc = ServiceTemplate.objects.filter(
                business=business, active=True, name__icontains="mow"
            ).first()
            if True:  # Always create since we checked already_mowing above
                # Create mowing service if it doesn't exist
                if not mowing_svc:
                    mowing_svc = ServiceTemplate.objects.create(
                        business=business, name="Mowing",
                        default_unit="visit", default_rate=0, pricing_method="flat", active=True,
                    )
                # Map frequency
                freq_map = {"per_visit": "weekly", "monthly": "monthly", "quarterly": "monthly",
                            "seasonal": "biweekly", "annual": "monthly", "as_needed": "weekly"}
                freq = freq_map.get(li.frequency, "weekly")
                # Save per-cut price
                if li.unit_price > 0:
                    from pricing.models import PropertyServiceRate
                    PropertyServiceRate.objects.update_or_create(
                        property=prop, service=mowing_svc,
                        defaults={"override_rate": li.unit_price},
                    )
                unit, rate = get_effective_rate(prop, mowing_svc)
                snapshot = [{"service_id": mowing_svc.id, "quantity": "1", "unit": unit, "unit_price": str(rate)}]
                RecurringJob.objects.create(
                    property=prop, frequency=freq, start_date=agreement.start_date or date.today(),
                    active=True, service_snapshot=snapshot,
                )

        # ── Fertilization sync ──
        fert_keywords = ["fert", "weed control", "lawn treatment", "lawn care program"]
        if any(kw in svc_lower for kw in fert_keywords):
            try:
                from fertilization.models import FertilizationProgram, CustomerProgramEnrollment
                # Check if already enrolled in ANY fertilization program this year
                already_fert = CustomerProgramEnrollment.objects.filter(
                    property=prop, year=date.today().year,
                    status__in=["enrolled", "in_progress"],
                ).exists()
                if already_fert:
                    continue  # Already a fertilization client — skip

                # Find a matching program
                program = FertilizationProgram.objects.filter(business=business, is_active=True).first()
                if program:
                    existing_enrollment = False  # We already checked above
                    if not existing_enrollment:
                        enrollment = CustomerProgramEnrollment.objects.create(
                            business=business, property=prop, program=program,
                            year=date.today().year, status="enrolled",
                            pricing_method="per_application",
                            price_per_application=li.unit_price if li.unit_price > 0 else None,
                        )
                        # Auto-create scheduled rounds from program template
                        for rnd in program.rounds.all().order_by("round_number"):
                            from fertilization.models import ScheduledRound
                            target_month = rnd.target_month_start or 4
                            sched_date = date(date.today().year, target_month, 15)
                            if sched_date < date.today():
                                sched_date = date(date.today().year + 1, target_month, 15)
                            ScheduledRound.objects.create(
                                enrollment=enrollment,
                                round_template=rnd,
                                round_number=rnd.round_number,
                                scheduled_date=sched_date,
                                status="pending",
                            )
            except Exception:
                pass  # Fertilization module might not be fully set up


@login_required
def hub(request):
    biz = request.user.business
    agreements = ServiceAgreement.objects.filter(business=biz).select_related("customer").order_by("-created_at")
    active_count = agreements.filter(status="active").count()
    draft_count = agreements.filter(status="draft").count()
    prepaid_count = agreements.filter(prepaid=True).count()
    return render(request, "service_agreements/hub.html", {
        "agreements": agreements,
        "active_count": active_count,
        "draft_count": draft_count,
        "prepaid_count": prepaid_count,
        "total_count": agreements.count(),
    })


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def agreement_create(request):
    """Create a maintenance plan — define services + auto-schedule jobs on the calendar."""
    business = get_business(request)
    if not business:
        return redirect("/")

    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        property_id = request.POST.get("property_id")
        name = (request.POST.get("name") or "").strip()
        price = request.POST.get("price") or "0"
        notes = request.POST.get("notes", "")

        if not customer_id or not property_id or not name:
            messages.error(request, "Customer, property, and plan name are required.")
            return redirect("service_agreements:agreement_create")

        customer = get_object_or_404(Customer, id=customer_id, business=business)
        prop = get_object_or_404(Property, id=property_id, customer=customer)

        billing_freq = request.POST.get("billing_frequency", "annual")
        prepaid = request.POST.get("prepaid") == "on"
        prepaid_amount = request.POST.get("prepaid_amount", "").strip()
        start_date_str = request.POST.get("start_date", "")
        end_date_str = request.POST.get("end_date", "")

        try:
            start_dt = date.fromisoformat(start_date_str) if start_date_str else date.today()
        except (ValueError, TypeError):
            start_dt = date.today()
        try:
            end_dt = date.fromisoformat(end_date_str) if end_date_str else None
        except (ValueError, TypeError):
            end_dt = None

        agreement = ServiceAgreement.objects.create(
            business=business,
            customer=customer,
            name=name,
            agreement_type="maintenance",
            status="active",
            start_date=start_dt,
            end_date=end_dt,
            billing_frequency=billing_freq,
            price=Decimal(price) if price else Decimal("0"),
            prepaid=prepaid,
            prepaid_amount=Decimal(prepaid_amount) if prepaid_amount else None,
            notes=notes,
        )

        # Save line items
        line_names = request.POST.getlist("line_name")
        line_freqs = request.POST.getlist("line_frequency")
        line_qtys = request.POST.getlist("line_qty")
        line_prices = request.POST.getlist("line_price")
        line_expected = request.POST.getlist("line_expected")
        for i in range(len(line_names)):
            ln = (line_names[i] or "").strip()
            if not ln:
                continue
            qty = Decimal(line_qtys[i]) if i < len(line_qtys) and line_qtys[i] else Decimal("1")
            AgreementLineItem.objects.create(
                agreement=agreement,
                service_name=ln,
                frequency=line_freqs[i] if i < len(line_freqs) else "per_visit",
                quantity=qty,
                unit_price=Decimal(line_prices[i]) if i < len(line_prices) and line_prices[i] else Decimal("0"),
                times_expected=int(line_expected[i]) if i < len(line_expected) and line_expected[i] else None,
                order=i,
            )

        # Auto-sync: enroll in Mowing Hub and/or Fertilization Hub based on services
        _sync_contract_to_hubs(agreement, prop, business)

        # Parse service visits from form
        visit_services = request.POST.getlist("visit_service")
        visit_months = request.POST.getlist("visit_month")
        visit_days = request.POST.getlist("visit_day")
        visit_notes = request.POST.getlist("visit_notes")

        jobs_created = 0
        year = date.today().year

        for i in range(len(visit_services)):
            svc_id = visit_services[i] if i < len(visit_services) else ""
            month = int(visit_months[i]) if i < len(visit_months) and visit_months[i] else 0
            day = int(visit_days[i]) if i < len(visit_days) and visit_days[i] else 15
            vnotes = visit_notes[i] if i < len(visit_notes) else ""

            if not svc_id or not month:
                continue

            service = ServiceTemplate.objects.filter(id=svc_id, business=business, active=True).first()
            if not service:
                continue

            # Calculate scheduled date
            try:
                sched_date = date(year, month, min(day, 28))
                # If date is in the past, schedule for next year
                if sched_date < date.today():
                    sched_date = date(year + 1, month, min(day, 28))
            except ValueError:
                sched_date = date(year, month, 15)

            # Create the job on the calendar
            job = Job.objects.create(
                property=prop,
                scheduled_date=sched_date,
                status="scheduled",
                notes=f"[{agreement.name}] {vnotes}".strip(),
            )

            # Add service line item
            unit, rate = get_effective_rate(prop, service)
            JobServiceItem.objects.create(
                job=job,
                service=service,
                description=service.name,
                quantity=1,
                unit=unit,
                unit_price=rate,
            )

            # Create agreement visit record
            AgreementVisit.objects.create(
                agreement=agreement,
                scheduled_date=sched_date,
                job=job,
                status="scheduled",
                notes=vnotes,
            )
            jobs_created += 1

        agreement.visits_included = jobs_created
        agreement.save(update_fields=["visits_included"])

        messages.success(request, f"Maintenance plan '{name}' created with {jobs_created} visits scheduled on the calendar.")
        return redirect("service_agreements:hub")

    # GET — build form context
    customers = Customer.objects.filter(business=business).prefetch_related('properties').order_by('name')
    services = ServiceTemplate.objects.filter(business=business, active=True).order_by('name')

    customers_data = []
    for c in customers:
        props = [{"id": p.id, "address": p.address, "sqft": p.yard_sqft} for p in c.properties.all()]
        customers_data.append({"id": c.id, "name": c.name, "properties": props})

    return render(request, "service_agreements/agreement_create.html", {
        "customers_json": json.dumps(customers_data),
        "services": services,
    })


@role_required("owner", "manager")
def agreement_detail(request, agreement_id):
    """View agreement details with all scheduled visits."""
    business = get_business(request)
    agreement = get_object_or_404(
        ServiceAgreement.objects.select_related('customer').prefetch_related('line_items'),
        id=agreement_id,
        business=business,
    )
    visits = agreement.visits.select_related('job').order_by('scheduled_date')
    line_items = agreement.line_items.all()
    completed_visits = visits.filter(status="completed").count()
    scheduled_visits = visits.filter(status="scheduled").count()
    return render(request, "service_agreements/agreement_detail.html", {
        "agreement": agreement,
        "visits": visits,
        "line_items": line_items,
        "completed_visits": completed_visits,
        "scheduled_visits": scheduled_visits,
    })


@require_POST
@role_required("owner", "manager")
def agreement_delete(request, agreement_id):
    """Delete an agreement."""
    business = get_business(request)
    agreement = get_object_or_404(ServiceAgreement, id=agreement_id, business=business)
    name = agreement.name
    agreement.delete()
    messages.success(request, f"Agreement '{name}' deleted.")
    return redirect("service_agreements:hub")


@role_required("owner", "manager")
def maintenance_hub(request):
    """Maintenance hub — track all contract services, progress, and scheduling."""
    business = get_business(request)
    if not business:
        return redirect("/")

    from accounts.timezone_utils import business_today
    today = business_today(business)

    # Get all active agreements with line items
    agreements = ServiceAgreement.objects.filter(
        business=business,
        status="active",
    ).select_related("customer").prefetch_related("line_items", "visits__job").order_by("customer__name")

    # Build contract data with service tracking
    contracts = []
    total_contract_value = Decimal("0")
    total_services = 0
    completed_services = 0
    overdue_services = 0

    for agreement in agreements:
        line_items = list(agreement.line_items.all())
        visits = list(agreement.visits.select_related("job").all())

        # Check if client also has mowing/fertilization
        from jobs.models import RecurringJob
        from fertilization.models import CustomerProgramEnrollment
        cust = agreement.customer
        has_mowing = RecurringJob.objects.filter(property__customer=cust, active=True).exists()
        has_fert = CustomerProgramEnrollment.objects.filter(
            property__customer=cust, status__in=["enrolled", "in_progress"]
        ).exists()

        contract_data = {
            "agreement": agreement,
            "customer": cust,
            "has_mowing": has_mowing,
            "has_fert": has_fert,
            "line_items": [],
            "total_value": Decimal("0"),
            "completed_count": 0,
            "total_count": 0,
            "progress_pct": 0,
            "visits": visits,
            "upcoming_visits": [v for v in visits if v.scheduled_date and v.scheduled_date >= today and v.status == "scheduled"],
            "completed_visits": [v for v in visits if v.status == "completed"],
        }

        for li in line_items:
            total_services += 1
            expected = li.times_expected or 0
            completed = li.times_completed or 0
            contract_data["total_count"] += expected
            contract_data["completed_count"] += completed
            completed_services += completed

            # Check if overdue (expected > 0, season is active, behind schedule)
            is_overdue = False
            if expected > 0 and completed < expected:
                # Simple heuristic: if past midpoint of year and less than half done
                month = today.month
                if li.frequency in ("monthly", "per_visit") and month > 6 and completed < expected / 2:
                    is_overdue = True
                elif li.frequency == "seasonal" and month > 8 and completed == 0:
                    is_overdue = True

            if is_overdue:
                overdue_services += 1

            contract_data["line_items"].append({
                "item": li,
                "expected": expected,
                "completed": completed,
                "remaining": max(0, expected - completed),
                "progress_pct": int(completed / expected * 100) if expected > 0 else 0,
                "is_overdue": is_overdue,
                "is_complete": li.is_complete,
            })

            contract_data["total_value"] += li.line_total
            total_contract_value += li.line_total

        if contract_data["total_count"] > 0:
            contract_data["progress_pct"] = int(contract_data["completed_count"] / contract_data["total_count"] * 100)

        contracts.append(contract_data)

    # Revenue tracking
    actual_revenue = Decimal("0")
    # Sum of paid invoices linked to agreements
    from billing.models import Invoice
    year_start = date(today.year, 1, 1)
    # Get revenue from completed agreement visits
    completed_visit_job_ids = []
    for agreement in agreements:
        for visit in agreement.visits.filter(status="completed", job__isnull=False):
            completed_visit_job_ids.append(visit.job_id)
    if completed_visit_job_ids:
        from django.db.models import Sum, F
        actual_revenue = JobServiceItem.objects.filter(
            job_id__in=completed_visit_job_ids,
        ).aggregate(
            total=Sum(F("quantity") * F("unit_price"))
        )["total"] or Decimal("0")

    return render(request, "service_agreements/maintenance_hub.html", {
        "contracts": contracts,
        "total_contracts": len(contracts),
        "total_contract_value": total_contract_value,
        "total_services": total_services,
        "completed_services": completed_services,
        "overdue_services": overdue_services,
        "actual_revenue": actual_revenue,
        "today": today,
    })


@require_POST
@role_required("owner", "manager")
def complete_service(request, line_item_id):
    """Mark a service line item as completed (increment times_completed)."""
    business = get_business(request)
    if not business:
        return redirect("/")
    li = get_object_or_404(AgreementLineItem, id=line_item_id, agreement__business=business)
    li.times_completed += 1
    li.save(update_fields=["times_completed"])
    messages.success(request, f"'{li.service_name}' marked complete ({li.progress_display}).")
    return redirect("service_agreements:maintenance_hub")


@require_POST
@role_required("owner", "manager")
def schedule_service(request, line_item_id):
    """Schedule a service line item as a job on the calendar."""
    business = get_business(request)
    if not business:
        return redirect("/")
    li = get_object_or_404(AgreementLineItem, id=line_item_id, agreement__business=business)
    schedule_date_str = request.POST.get("schedule_date", "").strip()
    if not schedule_date_str:
        messages.error(request, "Please select a date.")
        return redirect("service_agreements:maintenance_hub")
    try:
        schedule_date = date.fromisoformat(schedule_date_str)
    except (ValueError, TypeError):
        messages.error(request, "Invalid date.")
        return redirect("service_agreements:maintenance_hub")

    agreement = li.agreement
    prop = agreement.customer.properties.first()
    if not prop:
        messages.error(request, f"No property found for {agreement.customer.name}.")
        return redirect("service_agreements:maintenance_hub")

    # Create the job
    job = Job.objects.create(
        property=prop,
        scheduled_date=schedule_date,
        status="scheduled",
        notes=f"[{agreement.name}] {li.service_name}",
    )

    # Add service item
    svc = ServiceTemplate.objects.filter(business=business, active=True, name__icontains=li.service_name[:10]).first()
    JobServiceItem.objects.create(
        job=job,
        service=svc,
        description=li.service_name,
        quantity=li.quantity,
        unit=li.unit or "visit",
        unit_price=li.unit_price,
    )

    # Create agreement visit record
    AgreementVisit.objects.create(
        agreement=agreement,
        scheduled_date=schedule_date,
        job=job,
        status="scheduled",
        notes=li.service_name,
    )

    messages.success(request, f"'{li.service_name}' scheduled for {schedule_date.strftime('%b %d, %Y')}.")
    return redirect("service_agreements:maintenance_hub")

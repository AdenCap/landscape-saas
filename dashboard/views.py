from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, DecimalField, Count, F
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.decorators import role_required
from accounts.utils import get_business
from accounts.models import User
from businesses.models import Business
from jobs.models import Job, JobServiceItem
from billing.models import Invoice
from customers.models import ClientMessage




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


@role_required("owner")
def owner_dashboard(request):
    today = timezone.localdate()
    business = get_business(request)
    if not business:
        from django.shortcuts import redirect
        if request.user.is_superuser:
            return redirect("platform_home")
        return redirect("/accounts/login/")

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


@role_required("owner", "crew")
def employee_management(request):
    """Combined page: Employees, Timesheets, Crews, Payroll, Time off, Schedule. Crew only sees Time off and Schedule."""
    business = getattr(request.user, "business", None)
    if not business:
        return redirect("/")

    is_owner = getattr(request.user, "role", None) == "owner"

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
                user=user, clock_out__isnull=False,
                clock_in__date__gte=week_start, clock_in__date__lt=week_end,
            )
            week_minutes = sum(e.duration_minutes or 0 for e in week_entries)
            year_entries = TimeEntry.objects.filter(
                user=user, clock_out__isnull=False,
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
        payroll_unsynced = [p for p in payroll_payments if not p.quickbooks_journal_entry_id]
        quickbooks_connected = bool(getattr(business, "quickbooks_connection", None))
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
        payroll_unsynced = []
        quickbooks_connected = False
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
        "payroll_unsynced_count": len(payroll_unsynced),
        "quickbooks_connected": quickbooks_connected,
        "is_owner": is_owner,
        "time_off_requests": time_off_requests,
        "schedule_employees": schedule_employees,
        "schedule_selected_user": schedule_selected_user,
        "schedule_rows": schedule_rows,
        "time_off_employees": User.objects.filter(business=business, role="crew").order_by("first_name", "last_name", "username") if is_owner else [],
    })


@role_required("owner")
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
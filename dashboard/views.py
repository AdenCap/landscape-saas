from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, DecimalField, Count
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.decorators import role_required
from accounts.utils import get_business
from accounts.models import User
from jobs.models import Job
from billing.models import Invoice




def _month_range(d: date):
    start = d.replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
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

    context = {
        "today": today,
        "revenue_this_month": revenue_this_month,
        "profit_this_month": profit_this_month,
        "invoices_overdue_count": invoices_overdue_count,
        "invoices_overdue_total": invoices_overdue_total,
        "ar_outstanding": ar_outstanding,
        "jobs_today": jobs_today,
        "month_start": month_start,
        "month_end": month_end,
    }
    return render(request, "dashboard/owner_dashboard.html", context)


from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_date
from time_tracking.models import TimeEntry
from jobs.models import Crew
from accounts.models import EmployeePayment


def _hours_from_minutes(minutes):
    if minutes is None:
        return Decimal("0")
    return Decimal(str(minutes)) / Decimal("60")


@role_required("owner")
def employee_management(request):
    """Combined page: Employees, Timesheets, Crews."""
    business = getattr(request.user, "business", None)
    if not business:
        return redirect("/")

    # Employees
    employees = User.objects.filter(business=business).order_by("role", "first_name", "last_name", "username")

    # Timesheets: crew users only, week/year stats
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    year_start = today.replace(month=1, day=1)
    year_end = today.replace(year=today.year + 1, month=1, day=1)
    crew_users = User.objects.filter(role="crew", business=business).order_by("username")
    employee_stats = []
    for user in crew_users:
        rate = getattr(user, "hourly_rate", None) or Decimal("0")
        week_entries = TimeEntry.objects.filter(
            user=user,
            clock_out__isnull=False,
            clock_in__date__gte=week_start,
            clock_in__date__lt=week_end,
        )
        week_minutes = sum(e.duration_minutes or 0 for e in week_entries)
        year_entries = TimeEntry.objects.filter(
            user=user,
            clock_out__isnull=False,
            clock_in__date__gte=year_start,
            clock_in__date__lt=year_end,
        )
        year_minutes = sum(e.duration_minutes or 0 for e in year_entries)
        week_cost = _hours_from_minutes(week_minutes) * rate
        year_cost = _hours_from_minutes(year_minutes) * rate
        employee_stats.append({
            "user": user,
            "hourly_rate": rate,
            "week_minutes": week_minutes,
            "week_display": f"{week_minutes // 60}h {week_minutes % 60}m",
            "week_cost": week_cost,
            "year_minutes": year_minutes,
            "year_display": f"{year_minutes // 60}h {year_minutes % 60}m",
            "year_cost": year_cost,
        })
    total_week_cost = sum(s["week_cost"] for s in employee_stats)
    total_year_cost = sum(s["year_cost"] for s in employee_stats)

    # Crews
    crews = Crew.objects.filter(business=business).prefetch_related("members", "crew_leader").order_by("name")

    # Payroll: all payments for this business
    payroll_payments = (
        EmployeePayment.objects.filter(business=business)
        .select_related("employee")
        .order_by("-paid_date", "-created_at")
    )
    payroll_total = sum(p.amount for p in payroll_payments)
    payroll_unsynced = [p for p in payroll_payments if not p.quickbooks_journal_entry_id]
    quickbooks_connected = bool(getattr(business, "quickbooks_connection", None))

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
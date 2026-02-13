from datetime import date, timedelta
from django.db.models import Sum, F, DecimalField, Count, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from jobs.models import Job
from billing.models import Invoice, InvoiceLineItem
from accounts.models import User
from customers.models import Customer

from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, DecimalField, Count, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from jobs.models import Job
from billing.models import Invoice, InvoiceLineItem

from decimal import Decimal
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce




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
    # --- Today by Crew (ops view) ---
    crew_users = User.objects.filter(role="crew").order_by("username")

    crew_stats = (
        Job.objects.filter(scheduled_date=today, assigned_to__role="crew")
        .values("assigned_to_id", "assigned_to__username")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            remaining=Count("id", filter=~Q(status="completed")),
        )
        .order_by("assigned_to__username")
)

    # Also show crew members with zero jobs today
    stats_by_id = {row["assigned_to_id"]: row for row in crew_stats}

    crew_table = []
    for u in crew_users:
        row = stats_by_id.get(u.id, None)
        if row:
            crew_table.append({
                "name": row["assigned_to__username"],
                "total": row["total"],
                "completed": row["completed"],
                "remaining": row["remaining"],
                "user_id": u.id,
            })
        else:
            crew_table.append({
                "name": u.username,
                "total": 0,
                "completed": 0,
                "remaining": 0,
                "user_id": u.id,
            })

    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=7)

    month_start, month_end = _month_range(today)

    # --- Jobs KPIs ---
    jobs_today = Job.objects.filter(scheduled_date=today).count()
    completed_this_week = Job.objects.filter(
        status="completed",
        scheduled_date__gte=week_start,
        scheduled_date__lt=week_end,
    ).count()

    upcoming_jobs = (
        Job.objects.select_related("property", "assigned_to")
        .filter(scheduled_date__gte=today, scheduled_date__lt=today + timedelta(days=7))
        .order_by("scheduled_date", "route_order")[:15]
    )

    # --- Invoice KPIs ---
    # Revenue this month = sum of PAID invoice line totals for invoices whose period_start is in month
    # If you don't use period_start/period_end, we can switch to created_at/sent_at later.
    paid_invoices_this_month = Invoice.objects.filter(
        status="paid",
        period_start__gte=month_start,
        period_start__lt=month_end,
    )



    revenue_this_month = Invoice.objects.filter(
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

    ar_outstanding = Invoice.objects.filter(
        status="sent",
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]


    recent_invoices = (
       Invoice.objects.select_related("customer").order_by("-issue_date", "-id")[:10]
    )

    business = getattr(request.user, "business", None)
    recent_customers = []
    if business:
        recent_customers = Customer.objects.filter(business=business).order_by("-updated_at")[:8]

    context = {
        "today": today,
        "jobs_today": jobs_today,
        "completed_this_week": completed_this_week,
        "revenue_this_month": revenue_this_month,
        "ar_outstanding": ar_outstanding,
        "upcoming_jobs": upcoming_jobs,
        "recent_invoices": recent_invoices,
        "month_start": month_start,
        "month_end": month_end,
        "crew_table": crew_table,
        "recent_customers": recent_customers,
    }
    return render(request, "dashboard/owner_dashboard.html", context)


from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

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
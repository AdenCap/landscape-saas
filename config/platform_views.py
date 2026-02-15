"""
Platform admin: one superuser (you) can view platform metrics and open any business's dashboard.
Separate from company dashboards — shows users, revenue across the software, businesses, etc.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from businesses.models import Business
from accounts.models import AuditLog
from accounts.models import User
from billing.models import Invoice
from customers.models import Customer
from jobs.models import Job


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _superuser_required(view_func):
    """Decorator: require login and superuser."""
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/accounts/login/?next=" + request.get_full_path())
        if not request.user.is_superuser:
            return HttpResponseForbidden("Platform admin only.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def _last_12_months():
    """Return list of (year, month) for last 12 months, chronological (oldest first)."""
    today = date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(12):
        out.append((y, m))
        if m == 1:
            y, m = y - 1, 12
        else:
            m = m - 1
    out.reverse()
    return out


@_superuser_required
@require_http_methods(["GET"])
def platform_home(request):
    """Platform dashboard: metrics, charts (area + horizontal bar), business list, audit log."""
    businesses = Business.objects.all().order_by("name")
    today = date.today()

    # Platform-wide stats
    total_users = User.objects.count()
    owners_count = User.objects.filter(role="owner").count()
    crew_count = User.objects.filter(role="crew").count()
    total_businesses = Business.objects.count()
    total_customers = Customer.objects.count()
    total_jobs = Job.objects.count()
    platform_revenue = (
        Invoice.objects.filter(status="paid").aggregate(s=Sum("total"))["s"] or Decimal("0")
    )

    # This month (for KPIs)
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1)
    revenue_this_month = (
        Invoice.objects.filter(
            status="paid",
            issue_date__gte=month_start,
            issue_date__lt=month_end,
        ).aggregate(s=Sum("total"))["s"] or Decimal("0")
    )
    new_users_this_month = User.objects.filter(
        date_joined__year=month_start.year,
        date_joined__month=month_start.month,
    ).count()
    paid_invoices_count = Invoice.objects.filter(status="paid").count()

    # Chart data: last 12 months (revenue = area chart; new users = horizontal bar)
    monthly_revenue = []
    new_users_by_month = []
    for y, m in _last_12_months():
        m_start = date(y, m, 1)
        if m == 12:
            m_end = date(y + 1, 1, 1)
        else:
            m_end = date(y, m + 1, 1)
        rev = (
            Invoice.objects.filter(
                status="paid",
                issue_date__gte=m_start,
                issue_date__lt=m_end,
            ).aggregate(s=Sum("total"))["s"] or Decimal("0")
        )
        monthly_revenue.append({"label": m_start.strftime("%b %Y"), "value": float(rev)})
        cnt = User.objects.filter(date_joined__year=y, date_joined__month=m).count()
        new_users_by_month.append({"label": m_start.strftime("%b %Y"), "value": cnt})

    monthly_revenue_json = json.dumps(monthly_revenue)
    new_users_by_month_json = json.dumps(new_users_by_month)

    audit_logs = AuditLog.objects.select_related("user").order_by("-created_at")[:50]

    return render(request, "platform/admin_home.html", {
        "businesses": businesses,
        "audit_logs": audit_logs,
        "total_users": total_users,
        "owners_count": owners_count,
        "crew_count": crew_count,
        "total_businesses": total_businesses,
        "total_customers": total_customers,
        "total_jobs": total_jobs,
        "platform_revenue": platform_revenue,
        "revenue_this_month": revenue_this_month,
        "new_users_this_month": new_users_this_month,
        "paid_invoices_count": paid_invoices_count,
        "monthly_revenue_json": monthly_revenue_json,
        "new_users_by_month_json": new_users_by_month_json,
    })


@_superuser_required
@require_POST
def platform_enter(request, business_id):
    """Set session to view the app as this business; redirect to dashboard."""
    business = get_object_or_404(Business, pk=business_id)
    request.session["platform_business_id"] = business.id
    request.session["platform_business_name"] = business.name
    AuditLog.objects.create(
        user=request.user,
        action="platform_enter",
        details=f"Business: {business.name} (id={business.id})",
        ip_address=_get_client_ip(request),
    )
    messages.info(request, f"Viewing as: {business.name}. Use 'Exit' to return to platform admin.")
    return redirect("/")


@_superuser_required
@require_http_methods(["GET", "POST"])
def platform_exit(request):
    """Clear platform session and return to platform admin home."""
    name = request.session.get("platform_business_name", "")
    request.session.pop("platform_business_id", None)
    request.session.pop("platform_business_name", None)
    AuditLog.objects.create(
        user=request.user,
        action="platform_exit",
        details=name or "—",
        ip_address=_get_client_ip(request),
    )
    messages.success(request, "Exited business view.")
    return redirect("platform_home")

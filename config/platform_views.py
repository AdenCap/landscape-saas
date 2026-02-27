"""
Platform admin: one superuser (you) can view platform metrics and open any business's dashboard.
Separate from company dashboards — shows users, revenue across the software, businesses, etc.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum, Q
from django.db import models
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


def _platform_admin_required(view_func):
    """Decorator: require login and platform admin access."""
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/accounts/login/?next=" + request.get_full_path())
        # Allow both is_platform_admin and is_superuser (for backward compatibility)
        if not (getattr(request.user, "is_platform_admin", False) or request.user.is_superuser):
            return HttpResponseForbidden("Platform admin access required.")
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


@_platform_admin_required
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


@_platform_admin_required
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


@_platform_admin_required
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


@_platform_admin_required
@require_http_methods(["GET"])
def admin_users(request):
    """List all platform admins and allow adding/removing admin access."""
    # Get all users with platform admin access
    admin_users = User.objects.filter(
        models.Q(is_platform_admin=True) | models.Q(is_superuser=True)
    ).order_by("username")
    
    # Get all users (for adding new admins)
    all_users = User.objects.all().order_by("username")
    
    return render(request, "platform/admin_users.html", {
        "admin_users": admin_users,
        "all_users": all_users,
    })


@_platform_admin_required
@require_POST
def admin_grant(request, user_id):
    """Grant platform admin access to a user."""
    target_user = get_object_or_404(User, pk=user_id)
    if target_user.id == request.user.id:
        messages.error(request, "You cannot modify your own admin access.")
        return redirect("platform_admin_users")
    
    target_user.is_platform_admin = True
    target_user.save()
    
    AuditLog.objects.create(
        user=request.user,
        action="admin_grant",
        details=f"Granted admin access to {target_user.username} (id={target_user.id})",
        ip_address=_get_client_ip(request),
    )
    
    messages.success(request, f"Platform admin access granted to {target_user.username}.")
    return redirect("platform_admin_users")


@_platform_admin_required
@require_POST
def admin_revoke(request, user_id):
    """Revoke platform admin access from a user."""
    target_user = get_object_or_404(User, pk=user_id)
    if target_user.id == request.user.id:
        messages.error(request, "You cannot revoke your own admin access.")
        return redirect("platform_admin_users")
    
    if target_user.is_superuser:
        messages.error(request, "Cannot revoke admin access from superuser. Use Django admin to modify superuser status.")
        return redirect("platform_admin_users")
    
    target_user.is_platform_admin = False
    target_user.save()
    
    AuditLog.objects.create(
        user=request.user,
        action="admin_revoke",
        details=f"Revoked admin access from {target_user.username} (id={target_user.id})",
        ip_address=_get_client_ip(request),
    )
    
    messages.success(request, f"Platform admin access revoked from {target_user.username}.")
    return redirect("platform_admin_users")

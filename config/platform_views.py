"""
Platform admin: one superuser (you) can view platform metrics and open any business's dashboard.
Separate from company dashboards — shows users, revenue across the software, businesses, etc.
"""
import json
import os
from datetime import date
from decimal import Decimal
from django.utils import timezone

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
from subscription.models import StripeWebhookEvent


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
    crew_soft_cap_default = int(os.environ.get("PLATFORM_CREW_SOFT_CAP", "12") or "12")
    businesses = list(Business.objects.all().annotate(
        crew_users=models.Count("users", filter=Q(users__role="crew", users__is_active=True), distinct=True),
        owner_users=models.Count("users", filter=Q(users__role="owner", users__is_active=True), distinct=True),
    ).order_by("name"))
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
    active_subscriptions = Business.objects.filter(subscription_status="active").count()
    trial_subscriptions = Business.objects.filter(subscription_status="trialing").count()
    at_risk_subscriptions = Business.objects.filter(subscription_status__in=["past_due", "unpaid"]).count()
    solo_subscriptions = Business.objects.filter(subscription_plan_tier="solo", subscription_status__in=["active", "trialing"]).count()
    pro_subscriptions = Business.objects.filter(subscription_plan_tier="core", subscription_status__in=["active", "trialing"]).count()

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

    # Owner deep metrics
    monthly_price = Decimal(os.environ.get("PLATFORM_MONTHLY_PRICE", "99.99") or "99.99")
    monthly_recurring_revenue = monthly_price * Decimal(active_subscriptions)

    previous_month_end = month_start
    if month_start.month == 1:
        previous_month_start = month_start.replace(year=month_start.year - 1, month=12, day=1)
    else:
        previous_month_start = month_start.replace(month=month_start.month - 1, day=1)

    active_at_start_of_month = Business.objects.filter(
        updated_at__lt=month_start,
        subscription_status="active",
    ).count()
    canceled_this_month = StripeWebhookEvent.objects.filter(
        event_type="customer.subscription.deleted",
        created_at__gte=month_start,
        created_at__lt=month_end,
    ).count()
    monthly_churn_rate = round((canceled_this_month / active_at_start_of_month) * 100, 1) if active_at_start_of_month else 0

    failed_payments_this_month = StripeWebhookEvent.objects.filter(
        event_type="invoice.payment_failed",
        created_at__gte=month_start,
        created_at__lt=month_end,
    ).count()

    new_trial_subscriptions = StripeWebhookEvent.objects.filter(
        event_type="customer.subscription.created",
        created_at__gte=month_start,
        created_at__lt=month_end,
    ).count()
    converted_to_active = StripeWebhookEvent.objects.filter(
        event_type="customer.subscription.updated",
        created_at__gte=month_start,
        created_at__lt=month_end,
        raw_data__data__object__status="active",
    ).count()
    conversion_rate_trial_to_active = round((converted_to_active / new_trial_subscriptions) * 100, 1) if new_trial_subscriptions else 0

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

    solo_overage_count = sum(1 for b in businesses if b.subscription_plan_tier == "solo" and b.crew_users > 1)

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
        "active_subscriptions": active_subscriptions,
        "trial_subscriptions": trial_subscriptions,
        "at_risk_subscriptions": at_risk_subscriptions,
        "solo_subscriptions": solo_subscriptions,
        "pro_subscriptions": pro_subscriptions,
        "solo_overage_count": solo_overage_count,
        "revenue_this_month": revenue_this_month,
        "new_users_this_month": new_users_this_month,
        "paid_invoices_count": paid_invoices_count,
        "monthly_recurring_revenue": monthly_recurring_revenue,
        "monthly_churn_rate": monthly_churn_rate,
        "canceled_this_month": canceled_this_month,
        "failed_payments_this_month": failed_payments_this_month,
        "new_trial_subscriptions": new_trial_subscriptions,
        "converted_to_active": converted_to_active,
        "conversion_rate_trial_to_active": conversion_rate_trial_to_active,
        "monthly_revenue_json": monthly_revenue_json,
        "new_users_by_month_json": new_users_by_month_json,
        "crew_soft_cap_default": crew_soft_cap_default,
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
    messages.info(request, f"Viewing app as: {business.name}. Use 'Exit' to return to platform admin.")
    return redirect("owner_dashboard")


@_platform_admin_required
@require_POST
def platform_enter_demo(request):
    """Create a blank demo company and enter app view scoped to it."""
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    business = Business.objects.create(name=f"Demo Company {timestamp}")
    request.session["platform_business_id"] = business.id
    request.session["platform_business_name"] = business.name
    AuditLog.objects.create(
        user=request.user,
        action="platform_enter",
        details=f"Demo business created + entered: {business.name} (id={business.id})",
        ip_address=_get_client_ip(request),
    )
    messages.success(request, f"Opened blank demo company: {business.name}")
    return redirect("owner_dashboard")


@_platform_admin_required
@require_POST
def platform_apply_plan_recommendations(request):
    """Bulk-apply plan recommendations based on current crew counts."""
    businesses = Business.objects.all().annotate(
        crew_users=models.Count("users", filter=Q(users__role="crew", users__is_active=True), distinct=True),
    )
    to_pro = [b for b in businesses if b.subscription_plan_tier == "solo" and b.crew_users > 1]

    updated = 0
    for b in to_pro:
        b.subscription_plan_tier = "core"
        b.save(update_fields=["subscription_plan_tier", "updated_at"])
        updated += 1

    AuditLog.objects.create(
        user=request.user,
        action="platform_enter",
        details=f"Bulk plan recommendation apply: updated={updated} (to_pro={len(to_pro)})",
        ip_address=_get_client_ip(request),
    )
    messages.success(request, f"Applied pricing recommendations to {updated} business(es).")
    return redirect("platform_home")


@_platform_admin_required
@require_POST
def platform_set_plan(request, business_id):
    """Platform admin override for business plan tier (Solo/Pro)."""
    business = get_object_or_404(Business, pk=business_id)
    plan = (request.POST.get("plan_tier") or "").strip().lower()
    if plan not in {"solo", "core"}:
        messages.error(request, "Invalid plan tier.")
        return redirect("platform_home")

    old_plan = business.subscription_plan_tier
    business.subscription_plan_tier = plan
    business.save(update_fields=["subscription_plan_tier", "updated_at"])

    AuditLog.objects.create(
        user=request.user,
        action="platform_enter",
        details=f"Plan override: {business.name} (id={business.id}) {old_plan} -> {plan}",
        ip_address=_get_client_ip(request),
    )
    messages.success(request, f"Updated {business.name} plan to {business.get_subscription_plan_tier_display()}.")
    return redirect("platform_home")


@_platform_admin_required
@require_POST
def platform_toggle_free_access(request, business_id):
    """Platform admin: toggle complimentary access override for a business."""
    business = get_object_or_404(Business, pk=business_id)
    business.complimentary_access_enabled = not business.complimentary_access_enabled
    business.save(update_fields=["complimentary_access_enabled", "updated_at"])

    AuditLog.objects.create(
        user=request.user,
        action="platform_enter",
        details=f"Complimentary access {'ENABLED' if business.complimentary_access_enabled else 'DISABLED'} for {business.name} (id={business.id})",
        ip_address=_get_client_ip(request),
    )
    state = "enabled" if business.complimentary_access_enabled else "disabled"
    messages.success(request, f"Complimentary access {state} for {business.name}.")
    return redirect("platform_home")


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

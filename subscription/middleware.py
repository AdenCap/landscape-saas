"""Require active platform subscription for app access. Exempt login, signup, subscription, webhook, and public pages."""
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


SOLO_ALLOWED_PREFIXES = (
    "/dashboard",
    "/jobs",
    "/clients",
    "/billing",
    "/settings",
    "/crews",
    "/employees",
    "/notifications",
    "/time",
    "/estimator",
    "/api/messages",
)

# These require Pro. Solo users get redirected.
PRO_ONLY_PREFIXES = (
    "/pricebook",
    "/equipment",
    "/agreements",
    "/checklists",
    "/inspections",
    "/fertilization",
    "/financials",
)


# Path prefixes that do not require an active subscription
SUBSCRIPTION_EXEMPT_PREFIXES = (
    "/accounts/login",
    "/accounts/logout",
    "/accounts/signup",
    "/accounts/",
    "/admin/",
    "/platform/",
    "/subscription/",
    "/dashboard/onboarding",
    "/webhooks/stripe",
    "/static/",
    "/media/",
    "/book/",
    "/api/db-check",
    "/settings/logo/",
)


def _path_exempt(path):
    if not path:
        return True
    path = path.rstrip("/") or "/"
    for prefix in SUBSCRIPTION_EXEMPT_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _invoice_pay_path(path):
    """Public invoice pay page: /billing/<id>/pay/<token>/"""
    if not path.startswith("/billing/"):
        return False
    parts = path.strip("/").split("/")
    # billing / <id> / pay / <token>
    return len(parts) >= 4 and parts[2] == "pay"


class SubscriptionRequiredMiddleware(MiddlewareMixin):
    """Redirect to subscription page if user has a business but no active subscription."""

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        path = request.path
        if _path_exempt(path) or _invoice_pay_path(path):
            return None
        # Social signup incomplete: user exists but hasn't created a business yet
        if (
            request.session.get("social_signup_pending")
            and not getattr(request.user, "business", None)
            and not path.startswith("/accounts/social/complete")
        ):
            return redirect("/accounts/social/complete/")

        # Platform admins and superusers always have full access without subscription
        if getattr(request.user, "is_platform_admin", False) or request.user.is_superuser:
            return None
        business = getattr(request.user, "business", None)
        if not business:
            return None
        if getattr(business, "has_active_subscription", lambda: False)():
            # Solo Starter: core features allowed, vertical modules require Pro
            if getattr(business, "subscription_plan_tier", "core") == "solo":
                normalized = (path.rstrip("/") or "/")
                if any(normalized == p or normalized.startswith(p + "/") for p in PRO_ONLY_PREFIXES):
                    return redirect("/subscription/status/")
            return None
        # No active subscription: redirect to subscription status page
        status_url = reverse("subscription:status")
        if path == status_url or path.startswith(status_url + "?"):
            return None
        return redirect(status_url)

"""Require active platform subscription for app access. Exempt login, signup, subscription, webhook, and public pages."""
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


# Path prefixes that do not require an active subscription
SUBSCRIPTION_EXEMPT_PREFIXES = (
    "/accounts/login",
    "/accounts/logout",
    "/accounts/signup",
    "/accounts/",
    "/admin/",
    "/platform/",
    "/subscription/",
    "/webhooks/stripe",
    "/static/",
    "/media/",
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
        # Platform admins and superusers always have full access without subscription
        if getattr(request.user, "is_platform_admin", False) or request.user.is_superuser:
            return None
        business = getattr(request.user, "business", None)
        if not business:
            return None
        if getattr(business, "has_active_subscription", lambda: False)():
            return None
        # No active subscription: redirect to subscription status page
        status_url = reverse("subscription:status")
        if path == status_url or path.startswith(status_url + "?"):
            return None
        return redirect(status_url)

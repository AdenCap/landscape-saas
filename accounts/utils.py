"""
Shared helpers for request-scoped business resolution.
Used by all apps so that platform admins (superusers) can view any business's dashboard.
"""
from django.shortcuts import get_object_or_404

from businesses.models import Business


def get_business(request):
    """
    Return the Business for this request. Used everywhere to scope data by tenant.

    - Normal users (owner/crew): returns request.user.business.
    - Platform admin (superuser): if they have "entered" a business via the platform
      admin UI, returns that Business; otherwise returns None (they should pick one).
    """
    if not request.user.is_authenticated:
        return None
    if request.user.is_superuser:
        business_id = request.session.get("platform_business_id")
        if business_id:
            try:
                return Business.objects.get(pk=business_id)
            except Business.DoesNotExist:
                request.session.pop("platform_business_id", None)
                return None
        return None
    return getattr(request.user, "business", None)

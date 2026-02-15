from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def role_required(*allowed_roles):
    """
    Restrict view to users with one of the given roles (e.g. 'owner', 'crew').
    Platform admins (superusers) who have selected a business in session are
    allowed to access owner-only views for support.
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if getattr(request.user, "role", None) in allowed_roles:
                return view_func(request, *args, **kwargs)
            # Platform admin viewing as a business can access owner-level views
            if request.user.is_superuser and request.session.get("platform_business_id"):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have access to this page.")
        return _wrapped
    return decorator

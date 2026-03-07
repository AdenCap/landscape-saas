from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404


def module_required(module_name):
    """
    Restrict view to businesses that have the given module enabled.
    Returns 404 if the module is not in business.enabled_modules.
    Must be used after @login_required or @role_required.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            business = getattr(request.user, "business", None)
            # Platform admins operating under a business context
            if business is None and request.user.is_superuser:
                from businesses.models import Business
                bid = request.session.get("platform_business_id")
                if bid:
                    business = Business.objects.filter(pk=bid).first()
            if business is None:
                raise Http404
            modules = business.enabled_modules or []
            if module_name not in modules:
                raise Http404
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


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

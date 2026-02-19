"""Simple per-IP rate limiting using Django cache. Use for login, password reset, OAuth callbacks."""
import time
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def ratelimit(key="ip", rate="10/m", method=None, block=True):
    """
    Decorator: limit requests by key (e.g. 'ip') and rate string (e.g. '10/m', '5/h').
    When exceeded and block=True, returns HttpResponse with status 429.
    """
    try:
        num, period = rate.lower().split("/")
        num = int(num)
    except (ValueError, AttributeError):
        num, period = 10, "m"
    period_seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(period, 60)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request_or_self, request=None, *args, **kwargs):
            # Support both function views (request) and class-based view dispatch (self, request)
            req = request_or_self if hasattr(request_or_self, "META") else request
            if not req:
                return view_func(request_or_self, request, *args, **kwargs)
            if method and req.method != method.upper():
                return view_func(request_or_self, request, *args, **kwargs) if request is not None else view_func(request_or_self, *args, **kwargs)
            if key == "ip":
                identifier = _get_client_ip(req)
            else:
                identifier = "unknown"
            cache_key = f"rl:{key}:{identifier}"
            now = time.time()
            window_start = now - period_seconds
            try:
                timestamps = cache.get(cache_key) or []
            except Exception:
                timestamps = []
            timestamps = [t for t in timestamps if t > window_start]
            if len(timestamps) >= num:
                if block:
                    return HttpResponse("Too many requests.", status=429)
            timestamps.append(now)
            try:
                cache.set(cache_key, timestamps, timeout=period_seconds + 10)
            except Exception:
                pass
            if request is not None:
                return view_func(request_or_self, request, *args, **kwargs)
            return view_func(request_or_self, *args, **kwargs)
        return _wrapped
    return decorator

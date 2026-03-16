"""
Security middleware: request logging, anomaly detection, and global rate limiting.

Provides:
- SecurityLoggingMiddleware: logs all auth events, API errors, and suspicious patterns
- GlobalRateLimitMiddleware: per-IP rate limits on write endpoints to prevent abuse
"""
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse

from accounts.ratelimit import _get_client_ip

security_logger = logging.getLogger("accounts.security")
request_logger = logging.getLogger("security.requests")


# ── Security Logging Middleware ──────────────────────────────────────────
class SecurityLoggingMiddleware:
    """
    Logs:
    - All 4xx/5xx responses with IP, path, user
    - Authentication-related requests (login, signup, password reset)
    - Suspicious patterns (rapid 404s, credential stuffing indicators)
    """

    # Paths that always get logged (auth-sensitive)
    AUTH_PATHS = (
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/password_reset/",
        "/accounts/reset/",
        "/accounts/social/",
        "/accounts/2fa/",
        "/accounts/verify/",
        "/api/db-check/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        ip = _get_client_ip(request)
        path = request.path

        response = self.get_response(request)

        duration_ms = int((time.time() - start) * 1000)
        status = response.status_code
        user = getattr(request, "user", None)
        username = (user.username if user and user.is_authenticated else "anonymous")
        method = request.method

        # Always log auth-related paths
        if any(path.startswith(p) for p in self.AUTH_PATHS):
            security_logger.info(
                "auth_request ip=%s user=%s method=%s path=%s status=%d duration_ms=%d",
                ip, username, method, path, status, duration_ms,
            )

        # Log all server errors (5xx)
        if status >= 500:
            security_logger.error(
                "server_error ip=%s user=%s method=%s path=%s status=%d duration_ms=%d",
                ip, username, method, path, status, duration_ms,
            )

        # Log all client errors (4xx) except 404s on static files
        elif status >= 400 and not (status == 404 and path.startswith("/static/")):
            security_logger.warning(
                "client_error ip=%s user=%s method=%s path=%s status=%d duration_ms=%d",
                ip, username, method, path, status, duration_ms,
            )

        # Detect rapid 404s from single IP (possible scanning)
        if status == 404:
            self._track_404(ip)

        # Detect rapid auth failures from single IP (possible brute force)
        if status in (401, 403) and any(path.startswith(p) for p in self.AUTH_PATHS):
            self._track_auth_failure(ip, path)

        return response

    def _track_404(self, ip):
        """Track 404s per IP; warn if threshold exceeded (possible enumeration/scanning)."""
        cache_key = f"sec:404:{ip}"
        try:
            count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, count, timeout=300)  # 5-minute window
            if count == 50:
                security_logger.warning(
                    "suspicious_scanning ip=%s 404_count=%d window=300s "
                    "detail=Possible endpoint enumeration or vulnerability scanning",
                    ip, count,
                )
        except Exception:
            pass

    def _track_auth_failure(self, ip, path):
        """Track auth failures per IP; warn if threshold exceeded."""
        cache_key = f"sec:auth_fail:{ip}"
        try:
            count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, count, timeout=900)  # 15-minute window
            if count == 15:
                security_logger.warning(
                    "suspicious_auth_failures ip=%s failure_count=%d window=900s path=%s "
                    "detail=Possible credential stuffing or brute force attack",
                    ip, count, path,
                )
        except Exception:
            pass


# ── Global Rate Limit Middleware ─────────────────────────────────────────
class GlobalRateLimitMiddleware:
    """
    Global rate limiting for write operations (POST/PUT/PATCH/DELETE).
    Protects against automated abuse, bot scripts, and DDoS on write endpoints.

    Rate limits (per IP):
    - POST to API/data endpoints: 60 requests/minute
    - POST to AI generation endpoints: 10 requests/minute
    - General write operations: 120 requests/minute

    Does NOT rate-limit:
    - GET requests (read-only)
    - Static file requests
    - Webhook endpoints (authenticated separately)
    """

    # Tighter limits for sensitive/expensive endpoints
    TIGHT_LIMIT_PATHS = {
        "/accounts/signup/": (5, 60),        # 5 per minute
        "/accounts/login/": (10, 60),        # 10 per minute
        "/accounts/password_reset/": (5, 60), # 5 per minute
        "/api/db-check/": (5, 60),           # 5 per minute
        "/book/": (10, 60),                  # 10 per minute (public booking)
    }

    # AI/generation endpoints get tighter limits
    AI_PATHS = (
        "/estimator/",
        "/dashboard/morning-brief/",
        "/billing/estimate/",
    )

    # Exempt from rate limiting
    EXEMPT_PATHS = (
        "/webhooks/",
        "/static/",
        "/media/",
        "/admin/",
    )

    # General write limit
    GENERAL_WRITE_LIMIT = 120  # per minute
    AI_WRITE_LIMIT = 10  # per minute

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only rate-limit write methods
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return self.get_response(request)

        path = request.path

        # Skip exempt paths
        if any(path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        ip = _get_client_ip(request)

        # Check tight-limit paths first
        for prefix, (limit, window) in self.TIGHT_LIMIT_PATHS.items():
            if path.startswith(prefix):
                if self._is_over_limit(ip, f"rl:tight:{prefix}", limit, window):
                    security_logger.warning(
                        "rate_limited ip=%s path=%s limit=%d/%ds",
                        ip, path, limit, window,
                    )
                    return self._rate_limit_response(request)
                return self.get_response(request)

        # Check AI paths
        if any(path.startswith(p) for p in self.AI_PATHS):
            if self._is_over_limit(ip, "rl:ai", self.AI_WRITE_LIMIT, 60):
                security_logger.warning(
                    "rate_limited ip=%s path=%s limit=%d/60s type=ai",
                    ip, path, self.AI_WRITE_LIMIT,
                )
                return self._rate_limit_response(request)
            return self.get_response(request)

        # General write limit
        if self._is_over_limit(ip, "rl:write", self.GENERAL_WRITE_LIMIT, 60):
            security_logger.warning(
                "rate_limited ip=%s path=%s limit=%d/60s type=general",
                ip, path, self.GENERAL_WRITE_LIMIT,
            )
            return self._rate_limit_response(request)

        return self.get_response(request)

    def _is_over_limit(self, ip, prefix, limit, window_seconds):
        """Check if IP has exceeded the rate limit. Returns True if over limit."""
        cache_key = f"{prefix}:{ip}"
        try:
            now = time.time()
            timestamps = cache.get(cache_key) or []
            cutoff = now - window_seconds
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= limit:
                return True
            timestamps.append(now)
            cache.set(cache_key, timestamps, timeout=window_seconds + 10)
        except Exception:
            pass  # fail-open: don't block on cache errors
        return False

    def _rate_limit_response(self, request):
        """Return appropriate 429 response based on request type."""
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse(
                {"error": "Too many requests. Please try again later."},
                status=429,
            )
        return HttpResponse(
            "Too many requests. Please slow down and try again in a minute.",
            status=429,
            content_type="text/plain",
        )

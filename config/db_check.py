"""
Verify which database the app is using. Visit: /api/db-check/?key=YOUR_SECRET
Set DB_CHECK_SECRET in env to YOUR_SECRET (must be at least 32 chars in production).
Disabled by default in production unless DB_CHECK_ENABLED=1.
"""
import hmac
import logging
import os

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache

logger = logging.getLogger("accounts.security")


@require_GET
@csrf_exempt
@never_cache
def db_check(request):
    # Disable this diagnostic endpoint in production by default.
    if not settings.DEBUG and os.environ.get("DB_CHECK_ENABLED", "0").lower() not in ("1", "true", "yes"):
        return HttpResponse("Not Found", status=404)

    secret = os.environ.get("DB_CHECK_SECRET", "").strip()
    key = (request.GET.get("key") or "").strip()

    # Require a secret and enforce minimum length in production
    if not secret:
        return HttpResponse("Forbidden", status=403)
    if not settings.DEBUG and len(secret) < 32:
        logger.error("DB_CHECK_SECRET is too short (< 32 chars). Refusing request.")
        return HttpResponse("Forbidden", status=403)
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(key, secret):
        return HttpResponse("Forbidden", status=403)

    db = settings.DATABASES["default"]
    engine = db.get("ENGINE", "")
    if "postgresql" in engine:
        try:
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            status = "OK"
        except Exception:
            status = "Connection error"
        # Only expose engine type and connection status — no hostnames, DB names, or env vars
        body = f"Database: PostgreSQL\nConnection: {status}"
    else:
        body = "Database: SQLite\nNote: Data will NOT persist across redeploys."

    return HttpResponse(body, content_type="text/plain; charset=utf-8")

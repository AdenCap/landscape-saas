"""
Verify which database the app is using. Visit: /api/db-check/?key=YOUR_SECRET
Set DB_CHECK_SECRET in env to YOUR_SECRET. When using SQLite, shows which env vars are visible at runtime.
"""
import os
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache


def _env_set(name):
    raw = os.environ.get(name, "").strip()
    return "set" if raw and (raw.startswith("postgres://") or raw.startswith("postgresql://")) else "not set"


@require_GET
@csrf_exempt
@never_cache
def db_check(request):
    # Disable this diagnostic endpoint in production by default.
    if not settings.DEBUG and os.environ.get("DB_CHECK_ENABLED", "0").lower() not in ("1", "true", "yes"):
        return HttpResponse("Not Found", status=404)

    secret = os.environ.get("DB_CHECK_SECRET", "").strip()
    key = (request.GET.get("key") or "").strip()
    if not secret or key != secret:
        return HttpResponse("Forbidden", status=403)
    db = settings.DATABASES["default"]
    engine = db.get("ENGINE", "")
    if "postgresql" in engine:
        host = db.get("HOST", "?")
        name = db.get("NAME", "?")
        try:
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            status = "OK"
        except Exception as e:
            status = f"Connection error: {e}"
        body = f"Database: PostgreSQL\nHost: {host}\nName: {name}\nConnection: {status}"
    else:
        path = db.get("NAME", "?")
        body = (
            f"Database: SQLite\nPath: {path}\n\n"
            "Data will NOT persist across redeploys.\n\n"
            "Env vars visible to this app at runtime:\n"
            f"  PG_URL: {_env_set('PG_URL')}\n"
            f"  POSTGRES_URL: {_env_set('POSTGRES_URL')}\n"
            f"  DATABASE_URL: {_env_set('DATABASE_URL')}\n"
            "If all show 'not set', add PG_URL or POSTGRES_URL to the *web service* component with scope *Run Time* (not Build)."
        )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")

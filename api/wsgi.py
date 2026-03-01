"""
Vercel serverless entry point.

Exposes the Django WSGI application as `app` so Vercel's Python runtime
can serve it. All routes are sent here via vercel.json.
"""
import os
import sys
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()

# Check database persistence on startup
try:
    from config.database_check import check_database_persistence
    is_safe, warning = check_database_persistence()
    if warning:
        logger = logging.getLogger(__name__)
        logger.critical(warning)
        # Also print to stderr so it shows in Vercel logs
        print(warning, file=sys.stderr)
except Exception:
    # Don't fail startup if check fails
    pass

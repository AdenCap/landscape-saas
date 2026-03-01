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
    logger = logging.getLogger(__name__)
    from config.database_check import check_database_persistence
    is_safe, warning = check_database_persistence()
    if warning:
        logger.critical(warning)
        # Also print to stderr so it shows in Vercel logs
        print(warning, file=sys.stderr)
    
    # Try to test database connection
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
        logger.info("Database connection test successful")
    except Exception as db_error:
        logger.error(f"Database connection test failed: {db_error}")
        print(f"Database connection error: {db_error}", file=sys.stderr)
except Exception as e:
    # Don't fail startup if check fails, but log it
    import traceback
    logger = logging.getLogger(__name__)
    logger.error(f"Error during database check: {e}")
    logger.error(traceback.format_exc())
    print(f"Database check error: {e}", file=sys.stderr)

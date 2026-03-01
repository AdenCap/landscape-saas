"""
WSGI config for config project.

This module must define a callable named ``application`` so Gunicorn can run:
  gunicorn config.wsgi:application

See: https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""
import os
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application

# This is the WSGI application object Gunicorn looks for (config.wsgi:application).
application = get_wsgi_application()

# Check database persistence on startup
try:
    import logging
    logger = logging.getLogger(__name__)
    from config.database_check import check_database_persistence
    is_safe, warning = check_database_persistence()
    if warning:
        logger.critical(warning)
        # Also print to stderr so it shows in logs
        import sys
        print(warning, file=sys.stderr)
    
    # Try to test database connection
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
        logger.info("Database connection test successful")
    except Exception as db_error:
        logger.error(f"Database connection test failed: {db_error}")
        import sys
        print(f"Database connection error: {db_error}", file=sys.stderr)
except Exception as e:
    # Don't fail startup if check fails, but log it
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    logger.error(f"Error during database check: {e}")
    logger.error(traceback.format_exc())

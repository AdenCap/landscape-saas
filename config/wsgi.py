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
    from config.database_check import check_database_persistence
    is_safe, warning = check_database_persistence()
    if warning:
        logger = logging.getLogger(__name__)
        logger.critical(warning)
        # Also print to stderr so it shows in logs
        import sys
        print(warning, file=sys.stderr)
except Exception:
    # Don't fail startup if check fails
    pass

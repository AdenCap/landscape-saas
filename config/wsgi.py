"""
WSGI config for config project.

This module must define a callable named ``application`` so Gunicorn can run:
  gunicorn config.wsgi:application

See: https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application

# This is the WSGI application object Gunicorn looks for (config.wsgi:application).
application = get_wsgi_application()

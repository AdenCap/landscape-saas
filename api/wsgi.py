"""
Vercel serverless entry point.

Exposes the Django WSGI application as `app` so Vercel's Python runtime
can serve it. All routes are sent here via vercel.json.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()

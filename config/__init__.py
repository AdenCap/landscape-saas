# Python package for Django project config (required for config.wsgi to be importable).

from .celery import app as celery_app

__all__ = ("celery_app",)

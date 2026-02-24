"""
AppConfig for dashboard app with an explicit path to avoid "duplicate app paths".
Django can otherwise detect the app in multiple locations (e.g. different cwd or symlinks).
"""
import os

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
    label = "dashboard"
    # Resolve duplicate app path: pin this app to a single filesystem location.
    path = os.path.dirname(os.path.abspath(__file__))

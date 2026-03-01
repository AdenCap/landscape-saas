"""
Stripe Connect V2 integration app configuration.
"""
import os
from django.apps import AppConfig


class StripeConnectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stripe_connect"
    label = "stripe_connect"
    path = os.path.dirname(os.path.abspath(__file__))

"""
Webhook URL patterns for Stripe Connect.
"""
from django.urls import path
from . import webhook_views

urlpatterns = [
    path("", webhook_views.stripe_connect_webhook, name="stripe_connect_webhook"),
]

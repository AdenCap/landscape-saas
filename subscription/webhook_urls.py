"""Webhook URL at /webhooks/stripe/ (no app prefix) for Stripe Dashboard."""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.stripe_webhook, name="stripe_webhook"),
]

from django.apps import AppConfig


class StripeConnectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stripe_connect'
    verbose_name = 'Stripe Connect'

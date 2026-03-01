"""
Admin configuration for Stripe Connect models.
"""
from django.contrib import admin
from .models import ConnectedAccountProduct, ConnectedAccountSubscription


@admin.register(ConnectedAccountProduct)
class ConnectedAccountProductAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "price_amount", "currency", "active", "created_at"]
    list_filter = ["active", "currency", "created_at"]
    search_fields = ["name", "description", "business__name"]
    readonly_fields = ["stripe_product_id", "stripe_price_id", "created_at", "updated_at"]


@admin.register(ConnectedAccountSubscription)
class ConnectedAccountSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["business", "status", "current_period_end", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["business__name", "stripe_subscription_id"]
    readonly_fields = ["stripe_subscription_id", "created_at", "updated_at"]

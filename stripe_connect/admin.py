"""
Admin interface for Stripe Connect models.
"""
from django.contrib import admin
from .models import ConnectedAccount, ConnectedProduct, ConnectedSubscription, ConnectWebhookEvent


@admin.register(ConnectedAccount)
class ConnectedAccountAdmin(admin.ModelAdmin):
    list_display = ('business', 'account_id', 'display_name', 'contact_email', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('business__name', 'account_id', 'display_name', 'contact_email')
    readonly_fields = ('account_id', 'created_at', 'updated_at')


@admin.register(ConnectedProduct)
class ConnectedProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'connected_account', 'price_dollars', 'currency', 'active', 'created_at')
    list_filter = ('active', 'currency', 'created_at')
    search_fields = ('name', 'description', 'stripe_product_id')
    readonly_fields = ('stripe_product_id', 'stripe_price_id', 'created_at', 'updated_at')


@admin.register(ConnectedSubscription)
class ConnectedSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('connected_account', 'status', 'price_id', 'current_period_end', 'cancel_at_period_end', 'created_at')
    list_filter = ('status', 'cancel_at_period_end', 'created_at')
    search_fields = ('stripe_subscription_id', 'connected_account__business__name')
    readonly_fields = ('stripe_subscription_id', 'created_at', 'updated_at')


@admin.register(ConnectWebhookEvent)
class ConnectWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'processed', 'created_at', 'processed_at')
    list_filter = ('processed', 'event_type', 'created_at')
    search_fields = ('event_id', 'event_type')
    readonly_fields = ('event_id', 'event_type', 'created_at', 'processed_at')

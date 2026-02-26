from django.contrib import admin
from .models import CustomerPortalAccess


@admin.register(CustomerPortalAccess)
class CustomerPortalAccessAdmin(admin.ModelAdmin):
    list_display = ['customer', 'is_active', 'created_at', 'last_login']
    list_filter = ['is_active', 'created_at']
    search_fields = ['customer__name', 'customer__email', 'access_token']
    readonly_fields = ['access_token', 'created_at', 'last_login']

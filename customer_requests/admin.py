from django.contrib import admin
from .models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'request_type', 'status', 'created_at']
    list_filter = ['request_type', 'status', 'created_at']
    search_fields = ['name', 'email', 'phone', 'address']
    readonly_fields = ['created_at', 'updated_at', 'reviewed_at']

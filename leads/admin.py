from django.contrib import admin
from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'source', 'status', 'created_at']
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['name', 'email', 'phone', 'address']
    readonly_fields = ['created_at', 'updated_at', 'converted_at']

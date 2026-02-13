from django.contrib import admin
from .models import ServiceTemplate, PropertyServiceRate

@admin.register(ServiceTemplate)
class ServiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "default_unit", "default_rate", "active")
    list_filter = ("business", "active", "default_unit")
    search_fields = ("name",)

@admin.register(PropertyServiceRate)
class PropertyServiceRateAdmin(admin.ModelAdmin):
    list_display = ("property", "service", "override_rate")
    list_filter = ("service",)
    search_fields = ("property__address", "service__name")

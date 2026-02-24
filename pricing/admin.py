from django.contrib import admin
from .models import ServiceTemplate, PropertyServiceRate

@admin.register(ServiceTemplate)
class ServiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "default_unit", "default_rate", "active")
    list_filter = ("business", "active", "default_unit")
    search_fields = ("name", "business__name")
    ordering = ("business__name", "name")


@admin.register(PropertyServiceRate)
class PropertyServiceRateAdmin(admin.ModelAdmin):
    list_display = ("property", "get_business", "service", "override_rate")
    list_filter = ("service__business", "service")
    search_fields = ("property__address", "service__name", "property__customer__business__name")
    ordering = ("property__customer__business__name", "property__address")

    @admin.display(description='Company')
    def get_business(self, obj):
        if obj.property_id and obj.property.customer_id:
            return obj.property.customer.business
        return '—'

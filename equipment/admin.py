from django.contrib import admin
from .models import Equipment, EquipmentMaintenance, EquipmentUsage


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'equipment_type', 'is_active', 'last_maintenance_date', 'next_maintenance_date']
    list_filter = ['equipment_type', 'is_active']
    search_fields = ['name', 'make', 'model', 'serial_number']


@admin.register(EquipmentMaintenance)
class EquipmentMaintenanceAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'maintenance_date', 'maintenance_type', 'cost']
    list_filter = ['maintenance_date', 'maintenance_type']
    search_fields = ['equipment__name', 'maintenance_type']


@admin.register(EquipmentUsage)
class EquipmentUsageAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'usage_date', 'hours_used', 'miles_driven', 'fuel_cost']
    list_filter = ['usage_date']
    search_fields = ['equipment__name']

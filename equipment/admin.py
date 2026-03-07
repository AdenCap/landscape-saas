from django.contrib import admin
from .models import Equipment, EquipmentServiceLog


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ["__str__", "business", "customer", "equipment_type", "serial_number", "is_active"]
    list_filter = ["business", "equipment_type", "is_active"]
    search_fields = ["make", "model_name", "serial_number"]


@admin.register(EquipmentServiceLog)
class EquipmentServiceLogAdmin(admin.ModelAdmin):
    list_display = ["equipment", "service_type", "technician", "date"]
    list_filter = ["service_type"]

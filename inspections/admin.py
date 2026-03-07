from django.contrib import admin
from .models import InspectionTemplate, Inspection


@admin.register(InspectionTemplate)
class InspectionTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "is_active"]
    list_filter = ["business", "is_active"]


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "business", "inspector", "status", "completed_at"]
    list_filter = ["business", "status"]

from django.contrib import admin
from .models import ChecklistTemplate, ChecklistTemplateItem, JobChecklist, JobChecklistItem


class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 1


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "is_default", "is_active"]
    list_filter = ["business", "is_default", "is_active"]
    inlines = [ChecklistTemplateItemInline]


class JobChecklistItemInline(admin.TabularInline):
    model = JobChecklistItem
    extra = 0


@admin.register(JobChecklist)
class JobChecklistAdmin(admin.ModelAdmin):
    list_display = ["__str__", "completed_by", "completed_at"]
    inlines = [JobChecklistItemInline]

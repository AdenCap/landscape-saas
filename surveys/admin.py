from django.contrib import admin
from .models import Survey


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ['customer', 'job', 'overall_satisfaction', 'completed_at']
    list_filter = ['overall_satisfaction', 'completed_at']
    search_fields = ['customer__name']
    readonly_fields = ['completed_at']

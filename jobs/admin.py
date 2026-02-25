from django.contrib import admin
from .models import Job, JobServiceItem, Crew, RecurringJob, JobIssue, JobIssuePhoto, JobCompletionPhoto, JobAssignmentLog, Meeting, JobTemplate


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id', 'property', 'scheduled_date', 'status', 'assigned_to', 'assigned_crew']
    list_filter = ['status', 'scheduled_date', 'assigned_crew']
    search_fields = ['property__address', 'property__customer__name', 'notes']
    readonly_fields = ['created_at']


@admin.register(JobTemplate)
class JobTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'crew_leader']
    list_filter = ['business']
    search_fields = ['name']


@admin.register(RecurringJob)
class RecurringJobAdmin(admin.ModelAdmin):
    list_display = ['property', 'frequency', 'next_date', 'is_active']
    list_filter = ['frequency', 'is_active', 'next_date']
    search_fields = ['property__address']


@admin.register(JobIssue)
class JobIssueAdmin(admin.ModelAdmin):
    list_display = ['job', 'issue_type', 'status', 'reported_by', 'created_at']
    list_filter = ['issue_type', 'status', 'created_at']
    search_fields = ['description', 'job__property__address']


@admin.register(JobCompletionPhoto)
class JobCompletionPhotoAdmin(admin.ModelAdmin):
    list_display = ['job', 'uploaded_by', 'captured_at']
    list_filter = ['captured_at']
    search_fields = ['job__property__address']

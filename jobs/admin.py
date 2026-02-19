from django.contrib import admin
from .models import Job, Meeting, RecurringJob


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('property', 'scheduled_date', 'status', 'assigned_to')
    list_filter = ('status', 'scheduled_date')
    search_fields = ('property__address',)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'business', 'scheduled_at', 'customer', 'reminder_sent_at')
    list_filter = ('business',)
    search_fields = ('title', 'notes')
    date_hierarchy = 'scheduled_at'


@admin.register(RecurringJob)
class RecurringJobAdmin(admin.ModelAdmin):
    list_display = ('property', 'frequency', 'start_date', 'active')

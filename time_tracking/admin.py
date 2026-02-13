from django.contrib import admin
from .models import TimeEntry


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'clock_in', 'clock_out', 'duration_display')
    list_filter = ('user', 'clock_in')
    search_fields = ('user__username',)
    ordering = ('-clock_in',)
    readonly_fields = ('clock_in', 'clock_out')

from django.contrib import admin
from .models import TimeEntry


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_business', 'clock_in', 'clock_out', 'duration_display')
    list_filter = ('user__business', 'clock_in')
    search_fields = ('user__username', 'user__business__name')
    ordering = ('user__business__name', '-clock_in')
    readonly_fields = ('clock_in', 'clock_out')
    raw_id_fields = ('user',)

    @admin.display(description='Company')
    def get_business(self, obj):
        return obj.user.business if obj.user_id else '—'

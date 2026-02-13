from django.contrib import admin
from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('property', 'scheduled_date', 'status', 'assigned_to')
    list_filter = ('status', 'scheduled_date')
    search_fields = ('property__address',)


from .models import Job, RecurringJob


@admin.register(RecurringJob)
class RecurringJobAdmin(admin.ModelAdmin):
    list_display = ('property', 'frequency', 'start_date', 'active')

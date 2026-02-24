from django.contrib import admin
from .models import Job, Meeting, RecurringJob, Crew


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'crew_leader', 'color')
    list_filter = ('business',)
    search_fields = ('name', 'business__name')
    ordering = ('business__name', 'name')
    filter_horizontal = ('members',)
    raw_id_fields = ('crew_leader',)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'property', 'get_business', 'scheduled_date', 'status', 'assigned_to', 'assigned_crew')
    list_filter = ('property__customer__business', 'status', 'scheduled_date')
    search_fields = ('property__address', 'property__customer__name', 'property__customer__business__name')
    raw_id_fields = ('assigned_to', 'assigned_crew')
    ordering = ('property__customer__business__name', '-scheduled_date')
    date_hierarchy = 'scheduled_date'

    @admin.display(description='Company')
    def get_business(self, obj):
        if obj.property_id and obj.property.customer_id:
            return obj.property.customer.business
        return '—'


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'business', 'scheduled_at', 'customer', 'location', 'reminder_sent_at')
    list_filter = ('business',)
    search_fields = ('title', 'notes', 'business__name')
    date_hierarchy = 'scheduled_at'
    ordering = ('business__name', 'scheduled_at')
    raw_id_fields = ('customer', 'created_by')


@admin.register(RecurringJob)
class RecurringJobAdmin(admin.ModelAdmin):
    list_display = ('property', 'get_business', 'frequency', 'start_date', 'active', 'assigned_to', 'assigned_crew')
    list_filter = ('property__customer__business', 'frequency', 'active')
    search_fields = ('property__address', 'property__customer__business__name')
    raw_id_fields = ('assigned_to', 'assigned_crew')
    ordering = ('property__customer__business__name', 'property__address')

    @admin.display(description='Company')
    def get_business(self, obj):
        if obj.property_id and obj.property.customer_id:
            return obj.property.customer.business
        return '—'

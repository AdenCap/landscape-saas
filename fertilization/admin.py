from django.contrib import admin

from .models import (
    CustomerProgramEnrollment,
    FertilizationProgram,
    ProgramRound,
    ScheduledRound,
)


class ProgramRoundInline(admin.TabularInline):
    model = ProgramRound
    extra = 0
    fields = (
        'round_number',
        'name',
        'target_month_start',
        'target_month_end',
        'default_rate_override',
    )


class ScheduledRoundInline(admin.TabularInline):
    model = ScheduledRound
    extra = 0
    fields = (
        'round_number',
        'scheduled_date',
        'status',
        'price',
        'material_cost',
    )
    raw_id_fields = ('job', 'application')


@admin.register(FertilizationProgram)
class FertilizationProgramAdmin(admin.ModelAdmin):
    inlines = [ProgramRoundInline]
    list_display = ('name', 'business', 'grass_type', 'is_active', 'num_rounds')
    list_filter = ('business', 'grass_type', 'is_active')
    search_fields = ('name',)
    raw_id_fields = ('business',)


@admin.register(CustomerProgramEnrollment)
class CustomerProgramEnrollmentAdmin(admin.ModelAdmin):
    inlines = [ScheduledRoundInline]
    list_display = ('property', 'program', 'year', 'status', 'pricing_method')
    list_filter = ('business', 'year', 'status', 'program')
    raw_id_fields = ('business', 'property', 'program')


@admin.register(ScheduledRound)
class ScheduledRoundAdmin(admin.ModelAdmin):
    list_display = (
        'enrollment',
        'round_number',
        'scheduled_date',
        'status',
        'price',
        'material_cost',
    )
    list_filter = ('status', 'scheduled_date')
    raw_id_fields = ('enrollment', 'round_template', 'job', 'application')

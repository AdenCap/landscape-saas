from django.contrib import admin
from django.utils.html import format_html
from accounts.models import User
from .models import Business


class UserInline(admin.TabularInline):
    """View and edit employees for this business. To add new employees, use Users → Add user."""

    model = User
    extra = 0
    show_change_link = True
    fields = ('username', 'first_name', 'last_name', 'email', 'role', 'is_active')
    ordering = ('username',)
    verbose_name = "employee"
    verbose_name_plural = "employees (add new via Users → Add user)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('business')


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'from_email', 'contact_email', 'contact_phone', 'employee_count', 'created_at')
    list_filter = ()
    search_fields = ('name', 'contact_email', 'from_email', 'email_smtp_user')
    ordering = ('name',)
    inlines = [UserInline]

    fieldsets = (
        ('Company', {
            'fields': ('name', 'logo'),
            'description': 'Deleting this company will permanently delete all associated users, customers, properties, jobs, crews, invoices, estimates, time entries, and other data. Use with caution.',
        }),
        ('Email / SMTP (sending estimates)', {
            'fields': ('email_smtp_user', 'email_smtp_password', 'from_email', 'contact_email', 'contact_phone'),
        }),
        ('Invoicing', {
            'fields': ('auto_invoice', 'default_invoice_due_days', 'venmo_username', 'zelle_email_or_phone', 'cashapp_cashtag'),
        }),
        ('Invoice reminders', {
            'fields': ('invoice_reminder_enabled', 'invoice_reminder_days'),
        }),
        ('Estimates', {
            'fields': ('estimate_follow_up_days',),
        }),
        ('Jobs', {
            'fields': ('require_completion_photo',),
        }),
        ('Growing season (fertilization)', {
            'fields': ('growing_season_start_month', 'growing_season_end_month'),
        }),
        ('Payroll (dashboard balance)', {
            'fields': ('pay_frequency', 'pay_period_days', 'pay_specific_days', 'next_pay_date'),
        }),
        ('Stripe – subscription & Connect', {
            'fields': (
                'stripe_customer_id', 'stripe_subscription_id', 'subscription_status',
                'subscription_current_period_end', 'stripe_connect_account_id',
                'stripe_connect_charges_enabled', 'stripe_connect_application_fee_percent',
            ),
            'description': 'Subscription: business pays platform. Connect: business accepts card payments. Application fee %: platform fee on their invoice payments (blank = use global default).',
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Employees')
    def employee_count(self, obj):
        count = obj.users.count()
        return format_html('<b>{}</b>', count) if count else '0'
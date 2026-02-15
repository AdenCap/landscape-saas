from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, AuditLog, Notification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for Users with easy employee (crew) login creation."""

    list_display = ('username', 'email', 'get_full_name', 'business', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'business')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        (_('Address'), {'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code')}),
        (_('Business & Role'), {
            'fields': ('business', 'role', 'hourly_rate'),
            'description': 'Assign this user to a business and set their role. Crew = employee with field access. Hourly rate is used for labor cost in timesheets.',
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Groups'), {'fields': ('groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        (_('Personal info (optional)'), {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'email', 'phone'),
        }),
        (_('Create employee login'), {
            'classes': ('wide',),
            'fields': ('business', 'role', 'hourly_rate'),
            'description': 'Select the business and set role to Crew for field employees. Hourly rate is used for labor cost in timesheets.',
        }),
    )

    def get_full_name(self, obj):
        name = obj.get_full_name().strip()
        return name or '—'

    get_full_name.short_description = 'Name'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "from_user", "to_user", "message_preview", "read_at")
    list_filter = ("business", "read_at")
    search_fields = ("message", "from_user__username", "to_user__username")
    readonly_fields = ("business", "from_user", "to_user", "message", "created_at", "read_at")
    date_hierarchy = "created_at"

    def message_preview(self, obj):
        return (obj.message[:60] + "…") if len(obj.message) > 60 else obj.message

    message_preview.short_description = "Message"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "user", "details", "ip_address")
    list_filter = ("action",)
    search_fields = ("details", "user__username")
    readonly_fields = ("user", "action", "details", "ip_address", "created_at")
    date_hierarchy = "created_at"

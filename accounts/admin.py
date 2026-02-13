from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


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
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Business & Role'), {
            'fields': ('business', 'role'),
            'description': 'Assign this user to a business and set their role. Crew = employee with field access.',
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
            'fields': ('first_name', 'last_name', 'email'),
        }),
        (_('Create employee login'), {
            'classes': ('wide',),
            'fields': ('business', 'role'),
            'description': 'Select the business and set role to Crew for field employees. Employees use this login to access their daily schedule.',
        }),
    )

    def get_full_name(self, obj):
        name = obj.get_full_name().strip()
        return name or '—'

    get_full_name.short_description = 'Name'

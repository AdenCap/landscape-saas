from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'business', 'role', 'is_staff', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('business', 'role')}),
    )

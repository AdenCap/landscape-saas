from django.contrib import admin
from django.utils.html import format_html
from accounts.models import User
from .models import Business


class UserInline(admin.TabularInline):
    """View and edit employees for this business. To add new employees, use Users → Add user."""

    model = User
    extra = 0
    show_change_link = True
    fields = ('username', 'first_name', 'last_name', 'role', 'is_active')
    ordering = ('username',)
    verbose_name = "employee"
    verbose_name_plural = "employees (add new via Users → Add user)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('business')


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'employee_count', 'created_at')
    inlines = [UserInline]

    @admin.display(description='Employees')
    def employee_count(self, obj):
        count = obj.users.filter(role='crew').count()
        return format_html('<b>{}</b>', count) if count else '0'
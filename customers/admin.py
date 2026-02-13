from django.contrib import admin
from .models import Customer, Property


class PropertyInline(admin.TabularInline):
    model = Property
    extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'phone')
    inlines = [PropertyInline]


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('address', 'customer')

from django.contrib import admin
from .models import Customer, Property, Contract


class PropertyInline(admin.TabularInline):
    model = Property
    extra = 1


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'phone', 'email', 'city')
    list_filter = ('business',)
    search_fields = ('name', 'email', 'phone', 'city', 'address_line1')
    inlines = [PropertyInline, ContractInline]
    fieldsets = (
        (None, {'fields': ('business', 'name')}),
        ('Contact', {'fields': ('phone', 'alt_phone', 'email')}),
        ('Address', {'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code')}),
        ('Notes', {'fields': ('notes',)}),
    )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('address', 'customer', 'gate_code', 'has_dog')
    search_fields = ('address', 'customer__name')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('customer', 'contract_type', 'status', 'start_date', 'end_date', 'amount')
    list_filter = ('status', 'contract_type')

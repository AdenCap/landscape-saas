from django.contrib import admin
from .models import Customer, Property, Contract, ClientMessage


class PropertyInline(admin.TabularInline):
    model = Property
    extra = 1


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0


class ClientMessageInline(admin.TabularInline):
    model = ClientMessage
    extra = 0
    readonly_fields = ("channel", "direction", "subject", "body", "to_address", "created_at", "created_by")
    can_delete = True
    show_change_link = True


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'phone', 'email', 'communication_preference', 'city')
    list_filter = ('business', 'communication_preference')
    search_fields = ('name', 'email', 'phone', 'city', 'address_line1')
    inlines = [PropertyInline, ContractInline, ClientMessageInline]
    fieldsets = (
        (None, {'fields': ('business', 'name')}),
        ('Contact', {'fields': ('phone', 'alt_phone', 'email', 'communication_preference')}),
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


@admin.register(ClientMessage)
class ClientMessageAdmin(admin.ModelAdmin):
    list_display = ('customer', 'channel', 'direction', 'subject', 'to_address', 'created_at', 'created_by')
    list_filter = ('channel', 'direction')
    search_fields = ('customer__name', 'body', 'subject', 'to_address')
    readonly_fields = ('created_at',)

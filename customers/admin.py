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
    search_fields = ('name', 'email', 'phone', 'city', 'address_line1', 'business__name')
    ordering = ('business__name', 'name')
    inlines = [PropertyInline, ContractInline, ClientMessageInline]
    fieldsets = (
        (None, {'fields': ('business', 'name')}),
        ('Contact', {'fields': ('phone', 'alt_phone', 'email', 'communication_preference')}),
        ('Address', {'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code')}),
        ('Notes', {'fields': ('notes',)}),
    )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('address', 'customer', 'get_business', 'gate_code', 'has_dog')
    list_filter = ('customer__business', 'has_dog')
    search_fields = ('address', 'customer__name', 'customer__business__name')
    ordering = ('customer__business__name', 'customer__name', 'address')

    @admin.display(description='Company')
    def get_business(self, obj):
        return obj.customer.business if obj.customer_id else '—'


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('customer', 'get_business', 'contract_type', 'status', 'start_date', 'end_date', 'amount')
    list_filter = ('customer__business', 'status', 'contract_type')
    search_fields = ('customer__name', 'customer__business__name')
    ordering = ('customer__business__name', 'customer__name', '-created_at')

    @admin.display(description='Company')
    def get_business(self, obj):
        return obj.customer.business if obj.customer_id else '—'


@admin.register(ClientMessage)
class ClientMessageAdmin(admin.ModelAdmin):
    list_display = ('customer', 'get_business', 'channel', 'direction', 'subject', 'to_address', 'created_at', 'created_by')
    list_filter = ('customer__business', 'channel', 'direction')
    search_fields = ('customer__name', 'body', 'subject', 'to_address', 'customer__business__name')
    readonly_fields = ('created_at',)
    ordering = ('customer__business__name', '-created_at')

    @admin.display(description='Company')
    def get_business(self, obj):
        return obj.customer.business if obj.customer_id else '—'

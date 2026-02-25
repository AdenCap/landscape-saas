from django.contrib import admin
from .models import InventoryItem, InventoryTransaction, PurchaseOrder, PurchaseOrderItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'current_quantity', 'unit', 'is_active']
    list_filter = ['is_active', 'unit']
    search_fields = ['name', 'sku']


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ['inventory_item', 'transaction_type', 'quantity', 'cost', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['inventory_item__name']


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'supplier', 'order_date', 'status', 'total_cost']
    list_filter = ['status', 'order_date']
    search_fields = ['supplier']
    inlines = [PurchaseOrderItemInline]

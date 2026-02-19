from django.contrib import admin
from .models import Invoice, InvoiceLineItem, InvoiceAuditLog, Estimate, EstimateLineItem, EstimateImage


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    fields = ['description', 'quantity', 'material_cost', 'labor_cost']
    extra = 1


class InvoiceAuditLogInline(admin.TabularInline):
    model = InvoiceAuditLog
    extra = 0
    readonly_fields = ("action", "user", "created_at", "details")
    can_delete = False
    ordering = ["-created_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "total", "approved_at", "approved_by")
    inlines = [InvoiceLineItemInline, InvoiceAuditLogInline]


class EstimateLineItemInline(admin.TabularInline):
    model = EstimateLineItem
    fields = ['description', 'quantity', 'unit', 'material_cost', 'labor_cost', 'is_addon', 'order']
    extra = 1


class EstimateImageInline(admin.TabularInline):
    model = EstimateImage
    extra = 0


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'title', 'status', 'valid_until')
    list_filter = ('status',)
    inlines = [EstimateLineItemInline, EstimateImageInline]

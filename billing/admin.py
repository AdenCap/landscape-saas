from django.contrib import admin
from .models import Invoice, InvoiceLineItem, Estimate, EstimateLineItem, EstimateImage


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'status', 'total')
    inlines = [InvoiceLineItemInline]


class EstimateLineItemInline(admin.TabularInline):
    model = EstimateLineItem
    extra = 1


class EstimateImageInline(admin.TabularInline):
    model = EstimateImage
    extra = 0


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'title', 'status', 'valid_until')
    list_filter = ('status',)
    inlines = [EstimateLineItemInline, EstimateImageInline]

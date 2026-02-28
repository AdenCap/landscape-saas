from django.contrib import admin
from .models import Invoice, InvoiceLineItem, InvoiceAuditLog, Estimate, EstimateLineItem, EstimateImage, DocumentTemplate


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
    list_display = ("id", "business", "customer", "status", "total", "issue_date", "due_date", "approved_at", "approved_by")
    list_filter = ("business", "status")
    search_fields = ("customer__name", "customer__business__name")
    ordering = ("business__name", "-issue_date")
    inlines = [InvoiceLineItemInline, InvoiceAuditLogInline]
    raw_id_fields = ("customer", "approved_by")


class EstimateLineItemInline(admin.TabularInline):
    model = EstimateLineItem
    fields = ['description', 'quantity', 'unit', 'material_cost', 'labor_cost', 'is_addon', 'order']
    extra = 1


class EstimateImageInline(admin.TabularInline):
    model = EstimateImage
    extra = 0


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'customer', 'title', 'status', 'valid_until')
    list_filter = ('business', 'status')
    search_fields = ('customer__name', 'title', 'customer__business__name')
    ordering = ('business__name', '-id')
    inlines = [EstimateLineItemInline, EstimateImageInline]
    raw_id_fields = ('customer',)


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "doc_type", "template_key", "is_default")
    list_filter = ("doc_type", "business")
    search_fields = ("name", "business__name")
    raw_id_fields = ("business",)

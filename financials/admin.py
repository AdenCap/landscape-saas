from django.contrib import admin
from .models import Receipt, RevenueCategory


@admin.register(RevenueCategory)
class RevenueCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "sort_order")
    list_filter = ("business",)
    search_fields = ("name", "business__name")
    ordering = ("business__name", "sort_order", "name")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("vendor", "receipt_date", "amount", "category", "business", "job", "uploaded_by", "created_at")
    list_filter = ("business", "receipt_date", "category")
    search_fields = ("vendor", "description", "business__name")
    raw_id_fields = ("job", "uploaded_by")
    ordering = ("business__name", "-receipt_date")

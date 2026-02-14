from django.contrib import admin
from .models import Receipt, RevenueCategory


@admin.register(RevenueCategory)
class RevenueCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "sort_order")
    list_filter = ("business",)


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("vendor", "receipt_date", "amount", "category", "job", "uploaded_by", "created_at")
    list_filter = ("category", "receipt_date")
    search_fields = ("vendor", "description")
    raw_id_fields = ("job", "uploaded_by")

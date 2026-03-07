from django.contrib import admin
from .models import PricebookCategory, PricebookItem


@admin.register(PricebookCategory)
class PricebookCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "parent", "sort_order", "is_active"]
    list_filter = ["business", "is_active"]


@admin.register(PricebookItem)
class PricebookItemAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "category", "flat_rate_price", "material_cost", "is_active"]
    list_filter = ["business", "category", "is_active"]
    search_fields = ["name", "sku", "part_number"]

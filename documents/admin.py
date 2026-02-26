from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'document_type', 'customer', 'is_visible_to_customer', 'created_at']
    list_filter = ['document_type', 'is_visible_to_customer', 'created_at']
    search_fields = ['title', 'description', 'customer__name']
    readonly_fields = ['created_at']

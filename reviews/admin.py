from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['customer', 'job', 'rating', 'is_public', 'created_at']
    list_filter = ['rating', 'is_public', 'created_at']
    search_fields = ['customer__name', 'comment']
    readonly_fields = ['created_at']

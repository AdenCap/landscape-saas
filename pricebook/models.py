from django.db import models
from businesses.models import Business


class PricebookCategory(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="pricebook_categories")
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "pricebook categories"

    def __str__(self):
        return self.name


class PricebookItem(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="pricebook_items")
    category = models.ForeignKey(
        PricebookCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=50, blank=True, verbose_name="SKU")
    flat_rate_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Flat rate to charge customer for this item/service.",
    )
    material_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Internal cost for parts/materials.",
    )
    labor_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Estimated labor time in minutes.",
    )
    manufacturer = models.CharField(max_length=100, blank=True)
    part_number = models.CharField(max_length=100, blank=True)
    warranty_info = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def margin(self):
        if self.flat_rate_price and self.material_cost:
            return self.flat_rate_price - self.material_cost
        return None

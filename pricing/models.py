# pricing/models.py
from django.db import models
from decimal import Decimal
from businesses.models import Business
from customers.models import Property

class ServiceTemplate(models.Model):
    UNIT_CHOICES = [
        ("visit", "Per visit"),
        ("yard", "Per yard"),
        ("hour", "Per hour"),
        ("item", "Per item"),
        ("sqft", "Per sq ft"),
    ]

    PRICING_METHOD_CHOICES = [
        ("flat", "Flat rate"),
        ("per_sqft", "Per square foot"),
        ("per_yard", "Per yard"),
        ("per_hour", "Per hour"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="service_templates")
    name = models.CharField(max_length=120)
    default_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="visit")
    default_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Base price (flat rate per visit, per yard, per hour, etc.)")
    pricing_method = models.CharField(max_length=20, choices=PRICING_METHOD_CHOICES, default="flat",
        help_text="How this service is priced")
    rate_per_sqft = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True,
        help_text="Price per square foot (for sqft-based pricing like mowing)")
    min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Minimum charge regardless of calculation")
    pricing_notes = models.TextField(blank=True,
        help_text="Internal notes about pricing for this service")
    active = models.BooleanField(default=True)
    revenue_category = models.ForeignKey(
        "financials.RevenueCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_templates",
        help_text="Used for revenue breakdown in Financials (e.g. Mowing, Fertilizing).",
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def suggested_price_for_property(self, prop):
        """Calculate the suggested price based on pricing method and property data."""
        if self.pricing_method == 'per_sqft' and self.rate_per_sqft and prop.yard_sqft:
            price = self.rate_per_sqft * prop.yard_sqft
            if self.min_price and price < self.min_price:
                return self.min_price
            return price
        return self.default_rate

    def pricing_display(self):
        """Human-readable pricing summary."""
        if self.pricing_method == 'per_sqft' and self.rate_per_sqft:
            display = f"${self.rate_per_sqft}/sqft"
            if self.min_price:
                display += f" (min ${self.min_price})"
            return display
        if self.pricing_method == 'per_yard':
            return f"${self.default_rate}/yard"
        if self.pricing_method == 'per_hour':
            return f"${self.default_rate}/hr"
        return f"${self.default_rate}/visit" if self.default_rate else "—"


class PropertyServiceRate(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="service_rates")
    service = models.ForeignKey(ServiceTemplate, on_delete=models.CASCADE, related_name="property_rates")

    override_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("property", "service")

    def __str__(self):
        return f"{self.property} - {self.service}"

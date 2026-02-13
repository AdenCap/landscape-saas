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
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="service_templates")
    name = models.CharField(max_length=120)
    default_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="visit")
    default_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PropertyServiceRate(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="service_rates")
    service = models.ForeignKey(ServiceTemplate, on_delete=models.CASCADE, related_name="property_rates")

    override_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("property", "service")

    def __str__(self):
        return f"{self.property} - {self.service}"

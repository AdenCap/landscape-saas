from django.db import models
from decimal import Decimal
from pricing.models import ServiceTemplate

class JobServiceItem(models.Model):
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="pricing_service_items")
    service = models.ForeignKey(ServiceTemplate, on_delete=models.PROTECT, related_name="pricing_jobserviceitem_set")

    description = models.CharField(max_length=255, blank=True)  # optional override label
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))

    # Snapshot pricing used for this job (copied from property override or template at time of adding)
    unit = models.CharField(max_length=20, default="visit")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.job} - {self.service.name}"
    

def get_effective_rate(property_obj, service_template):
    override = property_obj.service_rates.filter(service=service_template).first()
    if override and override.override_rate is not None:
        return service_template.default_unit, Decimal(str(override.override_rate))
    return service_template.default_unit, Decimal(str(service_template.default_rate))

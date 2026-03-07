from django.conf import settings
from django.db import models
from businesses.models import Business


class Equipment(models.Model):
    EQUIPMENT_TYPE_CHOICES = [
        ("furnace", "Furnace"),
        ("ac_unit", "Air Conditioner"),
        ("heat_pump", "Heat Pump"),
        ("boiler", "Boiler"),
        ("water_heater", "Water Heater"),
        ("thermostat", "Thermostat"),
        ("ductwork", "Ductwork"),
        ("mini_split", "Mini Split"),
        ("panel", "Electrical Panel"),
        ("generator", "Generator"),
        ("sump_pump", "Sump Pump"),
        ("water_softener", "Water Softener"),
        ("other", "Other"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="equipment")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="equipment"
    )
    service_property = models.ForeignKey(
        "customers.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="equipment",
        db_column="property_id",
    )
    equipment_type = models.CharField(max_length=30, choices=EQUIPMENT_TYPE_CHOICES, default="other")
    make = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    install_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    last_service_date = models.DateField(null=True, blank=True)
    next_service_due = models.DateField(null=True, blank=True)
    location_in_property = models.CharField(
        max_length=100, blank=True, help_text="e.g. Basement, Attic, Garage"
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer", "equipment_type", "make"]
        verbose_name_plural = "equipment"

    def __str__(self):
        parts = [self.get_equipment_type_display(), self.make, self.model_name]
        return " ".join(p for p in parts if p)

    @property
    def warranty_active(self):
        if self.warranty_expiry:
            from django.utils import timezone
            return self.warranty_expiry >= timezone.localdate()
        return False


class EquipmentServiceLog(models.Model):
    SERVICE_TYPE_CHOICES = [
        ("maintenance", "Maintenance"),
        ("repair", "Repair"),
        ("installation", "Installation"),
        ("inspection", "Inspection"),
        ("replacement", "Replacement"),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="service_logs")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="equipment_service_logs"
    )
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default="maintenance")
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    parts_used = models.JSONField(default=list, blank=True, help_text="List of parts/materials used.")
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.get_service_type_display()} on {self.equipment} ({self.date})"

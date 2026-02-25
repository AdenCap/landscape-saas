"""Equipment & Vehicle Tracking: Track equipment, vehicles, and maintenance."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from jobs.models import Job
from decimal import Decimal


class Equipment(models.Model):
    """Equipment or vehicle owned by the business."""
    TYPE_CHOICES = [
        ('mower', 'Lawn Mower'),
        ('truck', 'Truck'),
        ('trailer', 'Trailer'),
        ('blower', 'Blower'),
        ('trimmer', 'Trimmer'),
        ('edger', 'Edger'),
        ('fertilizer_spreader', 'Fertilizer Spreader'),
        ('vehicle', 'Vehicle'),
        ('other', 'Other'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='equipment'
    )
    name = models.CharField(max_length=255, help_text="e.g. 'John Deere Mower #1' or 'Ford F-150'")
    equipment_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='other')
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Maintenance
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    maintenance_interval_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days between maintenance (e.g. 90 for quarterly)"
    )
    
    # Usage tracking
    total_hours = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), help_text="Total hours of use")
    total_miles = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), help_text="Total miles (for vehicles)")
    
    is_active = models.BooleanField(default=True, help_text="Is this equipment currently in use?")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Equipment'
    
    def __str__(self):
        return self.name


class EquipmentMaintenance(models.Model):
    """Maintenance record for equipment."""
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='maintenance_records'
    )
    maintenance_date = models.DateField()
    maintenance_type = models.CharField(
        max_length=100,
        help_text="e.g. 'Oil Change', 'Tire Replacement', 'Blade Sharpening'"
    )
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    notes = models.TextField(blank=True)
    performed_by = models.CharField(max_length=255, blank=True, help_text="Who performed the maintenance")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-maintenance_date']
    
    def __str__(self):
        return f"{self.equipment.name} - {self.maintenance_type} ({self.maintenance_date})"


class EquipmentUsage(models.Model):
    """Track equipment usage per job."""
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='equipment_used',
        null=True,
        blank=True
    )
    usage_date = models.DateField()
    hours_used = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    miles_driven = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    fuel_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-usage_date']
    
    def __str__(self):
        return f"{self.equipment.name} - {self.usage_date}"

from django.db import models
from customers.models import Property
from decimal import Decimal


class PropertyEstimate(models.Model):
    """Stores analysis results from property estimator (grass, mulch, trees, etc.)"""
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='property_estimates'
    )
    total_area_sqft = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='User-provided total property area for scale calibration'
    )
    grass_sqft = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pavement_sqft = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Sidewalks, parking, driveways (snow removal)')
    mulch_bed_sqft = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tree_count = models.PositiveIntegerField(default=0)
    bush_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Estimate for {self.property.address}"


class PropertyEstimateImage(models.Model):
    """Uploaded image for property analysis, with optional enhancement and segmentation overlay."""
    estimate = models.ForeignKey(
        PropertyEstimate,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='property_estimates/%Y/%m/')
    enhanced_image = models.ImageField(upload_to='property_estimates/%Y/%m/', null=True, blank=True)
    segmentation_overlay = models.ImageField(upload_to='property_estimates/%Y/%m/', null=True, blank=True)
    pixel_scale = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Sq ft per pixel (from total_area_sqft / total_pixels)'
    )
    raw_grass_pixels = models.BigIntegerField(null=True, blank=True)
    raw_pavement_pixels = models.BigIntegerField(null=True, blank=True)
    raw_mulch_pixels = models.BigIntegerField(null=True, blank=True)
    raw_tree_count = models.PositiveIntegerField(null=True, blank=True)
    raw_bush_count = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

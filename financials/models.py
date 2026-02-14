from django.db import models
from django.conf import settings
from businesses.models import Business


class RevenueCategory(models.Model):
    """Owner-defined category for revenue breakdown (e.g. Mowing, Fertilizing, Mulching, Snow Removal)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="revenue_categories",
    )
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0, help_text="Order in reports (lower first)")

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = [("business", "name")]

    def __str__(self):
        return self.name


def receipt_upload_to(instance, filename):
    """Store receipts by year/month."""
    from django.utils import timezone
    d = instance.receipt_date if instance.receipt_date else timezone.now().date()
    return f"receipts/{d.year}/{d.month:02d}/{filename}"


class Receipt(models.Model):
    """Receipt/expense record for bookkeeping and job material costs."""

    CATEGORY_CHOICES = [
        ("materials", "Materials"),
        ("fuel", "Fuel"),
        ("equipment", "Equipment / Rentals"),
        ("supplies", "Supplies"),
        ("labor", "Labor / Subcontractor"),
        ("other", "Other"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    file = models.FileField(upload_to=receipt_upload_to, blank=True, null=True, help_text="Optional; you can add a material cost without a receipt.")
    receipt_date = models.DateField(help_text="Date on the receipt")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total amount (for tracking material costs and taxes)",
    )
    vendor = models.CharField(max_length=255, blank=True, help_text="Store or vendor name")
    description = models.CharField(max_length=500, blank=True)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
        help_text="Link to a specific job (e.g. materials for this job)",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-receipt_date", "-created_at"]

    def __str__(self):
        label = self.vendor or self.description or "Receipt"
        if self.amount is not None:
            return f"{label} — ${self.amount} ({self.receipt_date})"
        return f"{label} ({self.receipt_date})"

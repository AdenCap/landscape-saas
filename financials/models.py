from django.db import models
from django.conf import settings
from django.utils import timezone
from businesses.models import Business


class SoftDeleteManager(models.Manager):
    """Generic soft-delete manager that hides deleted records by default."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        """Return queryset including soft-deleted records."""
        return super().get_queryset()

    def deleted_only(self):
        """Return only soft-deleted records."""
        return super().get_queryset().filter(deleted_at__isnull=False)


class RevenueCategory(models.Model):
    """Owner-defined category for revenue breakdown (e.g. Mowing, Fertilizing, Mulching, Snow Removal)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="revenue_categories",
    )
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0, help_text="Order in reports (lower first)")

    # Soft delete support
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this revenue category was soft-deleted. Null means active.",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_revenue_categories",
        help_text="User who soft-deleted this revenue category.",
    )

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = [("business", "name")]

    # Managers: default excludes deleted, all_objects includes them
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def __str__(self):
        return self.name

    def delete(self, using=None, keep_parents=False):
        """Soft delete: mark as deleted instead of removing the record."""
        self.deleted_at = timezone.now()
        deleting_user = getattr(self, "_deleting_user", None)
        if deleting_user and not self.deleted_by_id:
            self.deleted_by = deleting_user
        self.save(update_fields=["deleted_at", "deleted_by"])

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete this revenue category (use with caution)."""
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self):
        """Return True if this revenue category has been soft-deleted."""
        return self.deleted_at is not None


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

    # Soft delete support
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this receipt was soft-deleted. Null means active.",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_receipts",
        help_text="User who soft-deleted this receipt.",
    )

    class Meta:
        ordering = ["-receipt_date", "-created_at"]

    # Managers: default excludes deleted, all_objects includes them
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def __str__(self):
        label = self.vendor or self.description or "Receipt"
        if self.amount is not None:
            return f"{label} — ${self.amount} ({self.receipt_date})"
        return f"{label} ({self.receipt_date})"

    def delete(self, using=None, keep_parents=False):
        """Soft delete: mark as deleted instead of removing the record."""
        self.deleted_at = timezone.now()
        deleting_user = getattr(self, "_deleting_user", None)
        if deleting_user and not self.deleted_by_id:
            self.deleted_by = deleting_user
        self.save(update_fields=["deleted_at", "deleted_by"])

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete this receipt (use with caution)."""
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self):
        """Return True if this receipt has been soft-deleted."""
        return self.deleted_at is not None

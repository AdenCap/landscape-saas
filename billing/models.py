from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from businesses.models import Business
from customers.models import Customer
from jobs.models import Job


class InvoiceManager(models.Manager):
    """Custom manager that excludes soft-deleted invoices by default."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        """Return queryset including soft-deleted invoices."""
        return super().get_queryset()

    def deleted_only(self):
        """Return only soft-deleted invoices."""
        return super().get_queryset().filter(deleted_at__isnull=False)


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='invoices'
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='invoices'
    )

    jobs = models.ManyToManyField(
        Job,
        blank=True,
        related_name='invoices'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    job = models.OneToOneField(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice",
    )

    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    quickbooks_invoice_id = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text='QuickBooks Online Invoice Id after push',
    )

    payment_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        help_text="Secret token for the customer 'mark as paid' link. Set when invoice is sent.",
    )

    # Stripe payment tracking (for Connect invoice payments)
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stripe Checkout Session ID for this invoice payment",
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stripe Payment Intent ID (from checkout session)",
    )
    stripe_charge_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stripe Charge ID (from payment intent)",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the owner approved and sent this invoice (audit).",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices_approved",
        help_text="Owner who approved and sent this invoice (audit).",
    )

    last_reminder_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When a payment reminder email was last sent (for automated reminders).",
    )

    # Soft delete support
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this invoice was soft-deleted. Null means active.",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_invoices",
        help_text="User who soft-deleted this invoice.",
    )

    # Managers: default excludes deleted invoices, all_objects includes them
    objects = InvoiceManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"Invoice #{self.id} - {self.customer.name}"

    def delete(self, using=None, keep_parents=False):
        """Soft delete: mark as deleted instead of removing the record."""
        self.deleted_at = timezone.now()
        # deleted_by can be set by caller via _deleting_user attribute
        deleting_user = getattr(self, "_deleting_user", None)
        if deleting_user and not self.deleted_by_id:
            self.deleted_by = deleting_user
        self.save(update_fields=["deleted_at", "deleted_by"])

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete this invoice (use with caution)."""
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self):
        """Return True if this invoice has been soft-deleted."""
        return self.deleted_at is not None

    def recompute_totals(self):
        """Recalculate subtotal and total from line items and save. Call after adding/editing line items."""
        subtotal = sum(item.line_total for item in self.line_items.all())
        self.subtotal = subtotal
        self.total = subtotal + (self.tax or Decimal("0"))
        self.save(update_fields=["subtotal", "total"])


class Service(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='services'
    )

    name = models.CharField(max_length=100)
    default_price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (${self.default_price})"



class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='line_items'
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    revenue_category = models.ForeignKey(
        "financials.RevenueCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_line_items",
        help_text="For revenue breakdown (from service or manual).",
    )

    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # Used when importing from jobs
    material_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cost of materials for this line"
    )
    labor_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cost of labor for this line"
    )

    @property
    def line_total(self):
        if self.material_cost or self.labor_cost:
            return self.material_cost + self.labor_cost
        return self.quantity * self.unit_price

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.recompute_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.recompute_totals()


class InvoiceAuditLog(models.Model):
    """Audit trail for invoice actions: created, approved_sent, sent, paid, void, line_items_edited."""
    ACTION_CHOICES = [
        ("created", "Created"),
        ("approved_sent", "Approved & sent"),
        ("sent", "Sent"),
        ("paid", "Marked paid"),
        ("void", "Voided"),
        ("line_items_edited", "Line items edited"),
        ("dates_updated", "Dates updated"),
    ]
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_audit_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True, help_text="Optional extra context (e.g. line count).")

    class Meta:
        ordering = ["-created_at"]


class Estimate(models.Model):
    """Professional estimates for customers, with line items, add-ons, and images."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='estimates'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='estimates'
    )

    title = models.CharField(max_length=255, default='Field Ops Service Estimate')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    view_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_follow_up_at = models.DateTimeField(null=True, blank=True, help_text="When a follow-up email was last sent")

    def __str__(self):
        return f"Estimate #{self.id} - {self.customer.name}"

    def total(self):
        return sum(item.line_total for item in self.line_items.all())

    def base_total(self):
        """Total excluding add-ons."""
        return sum(
            item.line_total for item in self.line_items.filter(is_addon=False)
        )

    def addons_total(self):
        """Total of add-on items only."""
        return sum(
            item.line_total for item in self.line_items.filter(is_addon=True)
        )


class EstimateLineItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('standard', 'Standard'),
        ('fertilizing', 'Fertilizing'),
        ('mulch', 'Mulch'),
        ('mowing', 'Mowing'),
    ]

    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        default='standard',
        help_text='Service type for estimator options'
    )
    fertilizing_config = models.JSONField(
        null=True,
        blank=True,
        help_text='Stores fertilizing calculator inputs when item_type=fertilizing'
    )
    mulch_config = models.JSONField(
        null=True,
        blank=True,
        help_text='Stores mulch calculator inputs when item_type=mulch'
    )
    mowing_config = models.JSONField(
        null=True,
        blank=True,
        help_text='Stores mowing calculator inputs when item_type=mowing'
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=50, default='ea')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    material_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cost of materials for this line"
    )
    labor_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cost of labor for this line"
    )
    total_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="If set, this amount is used as the line total instead of materials + labor."
    )
    is_addon = models.BooleanField(default=False, verbose_name='Optional')

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    @property
    def line_total(self):
        if self.total_override is not None:
            return self.total_override
        if self.material_cost or self.labor_cost:
            return self.material_cost + self.labor_cost
        return self.quantity * self.unit_price


class EstimateImage(models.Model):
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='estimates/%Y/%m/')
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']


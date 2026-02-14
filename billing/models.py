from django.db import models
from businesses.models import Business
from customers.models import Customer
from jobs.models import Job


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

    def __str__(self):
        return f"Invoice #{self.id} - {self.customer.name}"


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

    title = models.CharField(max_length=255, default='Landscape Service Estimate')
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
    is_addon = models.BooleanField(default=False, verbose_name='Optional')

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    @property
    def line_total(self):
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


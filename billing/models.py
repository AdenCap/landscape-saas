from django.db import models
from businesses.models import Business
from customers.models import Customer
from jobs.models import Job


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
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
        max_length=10,
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

    def __str__(self):
        return f"Invoice #{self.id} - {self.customer.name}"
    
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")


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
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def line_total(self):
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

    def __str__(self):
        return f"Estimate #{self.id} - {self.customer.name}"

    def total(self):
        return sum(item.line_total() for item in self.line_items.all())

    def base_total(self):
        """Total excluding add-ons."""
        return sum(
            item.line_total() for item in self.line_items.filter(is_addon=False)
        )

    def addons_total(self):
        """Total of add-on items only."""
        return sum(
            item.line_total() for item in self.line_items.filter(is_addon=True)
        )


class EstimateLineItem(models.Model):
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=50, default='ea')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_addon = models.BooleanField(default=False, verbose_name='Optional add-on')

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def line_total(self):
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


from decimal import Decimal
from django.db import models
from django.conf import settings
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

    custom_field_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Values for company-defined custom fields. Keys match DocumentTemplate custom_fields.",
    )

    def __str__(self):
        return f"Invoice #{self.id} - {self.customer.name}"

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

    title = models.CharField(max_length=255, default='Tradevo Service Estimate')
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

    custom_field_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Values for company-defined custom fields (e.g. PO number, license #). Keys match DocumentTemplate custom_fields.",
    )

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


class DocumentTemplate(models.Model):
    """Per-business customizable templates for estimates and invoices. Companies choose a base style and customize colors, header, footer, terms; they can also define custom fields that appear on every document."""
    DOC_TYPE_CHOICES = [
        ("estimate", "Estimate"),
        ("invoice", "Invoice"),
    ]
    BUILTIN_KEYS = ["professional", "minimal", "modern"]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="document_templates",
    )
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    name = models.CharField(max_length=100, help_text="e.g. Professional, Minimal")
    template_key = models.CharField(
        max_length=50,
        blank=True,
        help_text="Built-in template key (professional, minimal, modern) or leave blank for custom.",
    )
    is_default = models.BooleanField(
        default=True,
        help_text="Use this template when generating documents of this type.",
    )

    # Customization (applied when rendering)
    primary_color = models.CharField(max_length=7, default="#22c55e", help_text="Hex color for headers and accents")
    header_text = models.TextField(
        blank=True,
        help_text="Optional text or HTML shown at the top of the document (e.g. tagline, license number).",
    )
    footer_text = models.TextField(
        blank=True,
        help_text="Optional text or HTML shown at the bottom (e.g. thank you, payment terms).",
    )
    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Terms and conditions shown on the document.",
    )

    # Custom fields: list of {"key": "po_number", "label": "PO Number", "type": "text"|"number"|"date"|"textarea", "required": false}
    custom_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="List of custom fields to show on every document. Each: {key, label, type, required}.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return f"{self.get_doc_type_display()}: {self.name} ({self.business.name})"

    @classmethod
    def get_default_for_business(cls, business, doc_type):
        """Return the default template for this business and doc_type, or None."""
        return (
            cls.objects.filter(business=business, doc_type=doc_type, is_default=True)
            .order_by("-updated_at")
            .first()
        )

    @classmethod
    def get_or_create_default(cls, business, doc_type, template_key="professional"):
        """Return the default template, creating one from the built-in if none exists."""
        default = cls.get_default_for_business(business, doc_type)
        if default:
            return default
        return cls.objects.create(
            business=business,
            doc_type=doc_type,
            name=template_key.replace("_", " ").title(),
            template_key=template_key,
            is_default=True,
        )


class GoogleMapsApiUsage(models.Model):
    """Track Google Maps API usage to enforce limits and prevent overages."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='google_maps_api_usage',
        null=True,
        blank=True,
        help_text="If set, tracks usage per business. If null, tracks global usage."
    )
    
    date = models.DateField(
        db_index=True,
        help_text="Date of API usage"
    )
    
    request_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of API requests made on this date"
    )
    
    request_type = models.CharField(
        max_length=50,
        choices=[
            ('directions', 'Directions API'),
            ('geocoding', 'Geocoding API'),
            ('javascript', 'Maps JavaScript API'),
        ],
        default='directions',
        help_text="Type of API request"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['business', 'date', 'request_type']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['business', 'date', 'request_type']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        business_name = self.business.name if self.business else "Global"
        return f"{business_name} - {self.date} - {self.request_type}: {self.request_count}"
    
    @classmethod
    def increment_usage(cls, business=None, request_type='directions', date=None):
        """Increment usage counter for a given business/date/type."""
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        
        usage, created = cls.objects.get_or_create(
            business=business,
            date=date,
            request_type=request_type,
            defaults={'request_count': 0}
        )
        usage.request_count += 1
        usage.save(update_fields=['request_count', 'updated_at'])
        return usage
    
    @classmethod
    def get_usage_today(cls, business=None, request_type='directions'):
        """Get today's usage count."""
        from django.utils import timezone
        today = timezone.now().date()
        try:
            usage = cls.objects.get(
                business=business,
                date=today,
                request_type=request_type
            )
            return usage.request_count
        except cls.DoesNotExist:
            return 0
    
    @classmethod
    def get_usage_this_month(cls, business=None, request_type='directions'):
        """Get this month's total usage count."""
        from django.utils import timezone
        from datetime import date
        from django.db.models import Sum
        today = timezone.now().date()
        first_of_month = date(today.year, today.month, 1)
        
        return cls.objects.filter(
            business=business,
            date__gte=first_of_month,
            request_type=request_type
        ).aggregate(
            total=Sum('request_count')
        )['total'] or 0


class FertilizerProduct(models.Model):
    """Business-specific catalog of fertilizer products with pricing."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='fertilizer_products'
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Product name (e.g. 'Scotts Turf Builder 32-0-4')"
    )
    
    pricing_type = models.CharField(
        max_length=20,
        choices=[
            ('per_pound', 'Per pound'),
            ('per_bag', 'Per bag'),
        ],
        default='per_pound',
        help_text="How this product is priced"
    )
    
    # Per pound pricing
    cost_per_pound = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per pound (if pricing_type = per_pound)"
    )
    
    # Per bag pricing
    cost_per_bag = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per bag (if pricing_type = per_bag)"
    )
    
    lbs_per_bag = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Pounds per bag (if pricing_type = per_bag)"
    )
    
    active = models.BooleanField(
        default=True,
        help_text="Show in product selection dropdowns"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about this product"
    )

    # NPK Analysis
    nitrogen_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Nitrogen percentage from product label (e.g., 32.00 for 32-0-4)"
    )
    phosphorus_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Phosphorus percentage from product label"
    )
    potassium_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Potassium percentage from product label"
    )

    # Application rate
    application_rate = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Recommended lbs per 1,000 sq ft"
    )

    # Product type
    product_type = models.CharField(
        max_length=20,
        choices=[('granular', 'Granular'), ('liquid', 'Liquid')],
        default='granular',
        help_text="Affects unit display in calculators"
    )

    # EPA registration
    epa_registration_number = models.CharField(
        max_length=50, blank=True,
        help_text="EPA registration number for compliance tracking"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['business', 'name']]

    def __str__(self):
        return f"{self.name} ({self.business.name})"

    @property
    def npk_display(self):
        """Return NPK string like '32-0-4' or empty string."""
        if self.nitrogen_pct is not None:
            n = int(self.nitrogen_pct) if self.nitrogen_pct == int(self.nitrogen_pct) else self.nitrogen_pct
            p = int(self.phosphorus_pct) if self.phosphorus_pct and self.phosphorus_pct == int(self.phosphorus_pct) else (self.phosphorus_pct or 0)
            k = int(self.potassium_pct) if self.potassium_pct and self.potassium_pct == int(self.potassium_pct) else (self.potassium_pct or 0)
            return f"{n}-{p}-{k}"
        return ""
    
    def calculate_cost(self, pounds):
        """Calculate material cost for given pounds."""
        from decimal import Decimal, ROUND_CEILING
        pounds = Decimal(str(pounds))
        
        if self.pricing_type == 'per_bag':
            if not self.lbs_per_bag or self.lbs_per_bag <= 0:
                return Decimal('0')
            if not self.cost_per_bag:
                return Decimal('0')
            bags = (pounds / self.lbs_per_bag).quantize(Decimal('1'), rounding=ROUND_CEILING)
            return bags * self.cost_per_bag
        else:
            if not self.cost_per_pound:
                return Decimal('0')
            return pounds * self.cost_per_pound
    
    def get_cost_per_pound_equivalent(self):
        """Get effective cost per pound (useful for comparison)."""
        from decimal import Decimal
        if self.pricing_type == 'per_pound':
            return self.cost_per_pound or Decimal('0')
        else:
            if not self.lbs_per_bag or self.lbs_per_bag <= 0 or not self.cost_per_bag:
                return Decimal('0')
            return (self.cost_per_bag / self.lbs_per_bag)


# Save built-in before the ForeignKey field named 'property' shadows it in the class body
_python_property = property


class FertilizerApplication(models.Model):
    """Tracks fertilizer applications to properties with product, date, and amount."""
    WEATHER_CHOICES = [
        ('clear', 'Clear'),
        ('partly_cloudy', 'Partly Cloudy'),
        ('cloudy', 'Cloudy'),
        ('overcast', 'Overcast'),
        ('light_rain', 'Light Rain'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='fertilizer_applications'
    )
    
    property = models.ForeignKey(
        "customers.Property",
        on_delete=models.CASCADE,
        related_name='fertilizer_applications'
    )
    
    product = models.ForeignKey(
        FertilizerProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applications',
        help_text="Product used (null if product was deleted)"
    )
    
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fertilizer_applications',
        help_text="Job where this was applied (optional)"
    )
    
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fertilizer_applications',
        help_text="Estimate that led to this application (optional)"
    )
    
    application_date = models.DateField(
        help_text="Date fertilizer was applied"
    )
    
    pounds_used = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total pounds of fertilizer applied"
    )
    
    square_feet = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Square footage treated"
    )
    
    lbs_per_1000_sqft = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Application rate (lbs per 1,000 sq ft)"
    )
    
    material_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Cost of materials (calculated from product)"
    )
    
    charge_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount charged to customer (for profit calculation)"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about this application"
    )

    # Weather at time of application
    weather_temp_f = models.SmallIntegerField(
        null=True, blank=True,
        help_text="Temperature (°F) at time of application"
    )
    weather_wind_mph = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text="Wind speed (mph) at time of application"
    )
    weather_conditions = models.CharField(
        max_length=20, choices=WEATHER_CHOICES, blank=True,
        help_text="Weather conditions at time of application"
    )
    applied_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fertilizer_applications_applied',
        help_text="Technician who applied the product"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-application_date', '-id']
        indexes = [
            models.Index(fields=['property', 'application_date']),
            models.Index(fields=['business', 'application_date']),
        ]
    
    def __str__(self):
        product_name = self.product.name if self.product else "Unknown Product"
        return f"{product_name} - {self.property.address} - {self.application_date}"
    
    @_python_property
    def profit(self):
        """Calculate profit (charge_amount - material_cost)."""
        if self.charge_amount is None:
            return None
        return self.charge_amount - self.material_cost

    @_python_property
    def profit_margin(self):
        """Calculate profit margin percentage."""
        if self.charge_amount is None or self.charge_amount == 0:
            return None
        profit = self.profit
        if profit is None:
            return None
        return (profit / self.charge_amount) * 100


from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from businesses.models import Business


class Customer(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='customers'
    )

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    alt_phone = models.CharField(max_length=20, blank=True, verbose_name='Alternate phone')
    email = models.EmailField(blank=True)

    COMMUNICATION_PREFERENCE_CHOICES = [
        ("", "— Not set —"),
        ("email", "Email"),
        ("sms", "Text (SMS)"),
        ("both", "Email and Text"),
    ]
    communication_preference = models.CharField(
        max_length=10,
        choices=COMMUNICATION_PREFERENCE_CHOICES,
        default="",
        blank=True,
        help_text="How this client prefers to be contacted.",
    )

    # Billing / mailing address (properties have service addresses)
    address_line1 = models.CharField(max_length=255, blank=True, verbose_name='Address')
    address_line2 = models.CharField(max_length=255, blank=True, verbose_name='Address line 2')
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='ZIP / Postal code')

    notes = models.TextField(blank=True)

    GOOGLE_REVIEW_STATUS_CHOICES = [
        ("never_asked", "Never asked"),
        ("asked", "Asked"),
        ("reviewed", "Reviewed"),
        ("opted_out", "Opted out"),
    ]
    google_review_status = models.CharField(
        max_length=20,
        choices=GOOGLE_REVIEW_STATUS_CHOICES,
        default="never_asked",
        help_text="Tracks Google review outreach so clients are not repeatedly prompted.",
    )
    google_review_requested_at = models.DateTimeField(null=True, blank=True)
    google_review_completed_at = models.DateTimeField(null=True, blank=True)
    google_review_attempts = models.PositiveSmallIntegerField(default=0)
    google_review_last_prompt_at = models.DateTimeField(null=True, blank=True)

    INVOICE_FREQUENCY_CHOICES = [
        ("", "Ask each time (choose when job is completed)"),
        ("per_service", "Per service — invoice when each job is completed"),
        ("monthly", "Monthly — add completed jobs to a monthly invoice"),
    ]
    invoice_frequency = models.CharField(
        max_length=20,
        choices=INVOICE_FREQUENCY_CHOICES,
        default="",
        blank=True,
        help_text="When to send invoices for this client. Leave blank to choose per job.",
    )
    monthly_invoice_send_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="For monthly clients: day of month to send the invoice (1–28). E.g. 1 = 1st, 15 = 15th. Leave blank to send manually.",
    )
    invoice_due_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text="Override due date for this client: days from issue date (e.g. 15 = Net 15). Leave blank to use business default.",
    )

    # Card on file (Stripe)
    stripe_customer_id = models.CharField(
        max_length=100, blank=True,
        help_text="Stripe Customer ID on the connected account (for card-on-file payments)"
    )
    stripe_payment_method_id = models.CharField(
        max_length=100, blank=True,
        help_text="Stripe PaymentMethod ID for saved card"
    )
    card_last4 = models.CharField(max_length=4, blank=True, help_text="Last 4 digits of saved card")
    card_brand = models.CharField(max_length=20, blank=True, help_text="Card brand (visa, mastercard, etc.)")
    auto_charge = models.BooleanField(
        default=False,
        help_text="Automatically charge saved card when invoice is sent"
    )
    auto_charge_completed_jobs = models.BooleanField(
        default=False,
        help_text="Automatically charge the saved card when a per-service job invoice is sent after completion.",
    )
    auto_charge_monthly_invoices = models.BooleanField(
        default=False,
        help_text="Automatically charge the saved card when a monthly invoice is sent.",
    )

    def should_auto_charge_invoice(self, invoice):
        """Return whether this customer's saved card should be charged for the invoice."""
        if not (self.stripe_customer_id and self.stripe_payment_method_id):
            return False
        if getattr(invoice, "job_id", None):
            return bool(self.auto_charge_completed_jobs or self.auto_charge)
        if getattr(invoice, "period_start", None) and getattr(invoice, "period_end", None):
            return bool(self.auto_charge_monthly_invoices or self.auto_charge)
        return bool(self.auto_charge)

    # Customer Portal access
    portal_access_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Secure token for customer portal access (auto-generated)"
    )
    portal_enabled = models.BooleanField(
        default=True,
        help_text="Allow customer to access their portal"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.portal_access_token:
            import secrets
            self.portal_access_token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        parts = [
            self.address_line1,
            self.address_line2,
            f"{self.city}, {self.state} {self.postal_code}".strip(", ") if (self.city or self.state or self.postal_code) else None,
        ]
        return ", ".join(p for p in parts if p) or "—"

    def can_receive_review_prompt(self, max_attempts=2):
        if self.google_review_status in {"reviewed", "opted_out"}:
            return False
        return self.google_review_attempts < max_attempts


class Contract(models.Model):
    """Service agreements / contracts with customers."""
    TYPE_CHOICES = [
        ('monthly', 'Monthly Maintenance'),
        ('seasonal', 'Seasonal'),
        ('one_time', 'One-time'),
        ('biweekly', 'Bi-weekly'),
        ('custom', 'Custom'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='contracts'
    )
    contract_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='monthly')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Contract value (optional)')
    notes = models.TextField(blank=True)

    BILLING_FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annual", "Semi-Annual"),
        ("annual", "Annual"),
        ("one_time", "One-Time"),
    ]
    billing_frequency = models.CharField(
        max_length=20, choices=BILLING_FREQUENCY_CHOICES, default="monthly", blank=True,
    )
    prepaid = models.BooleanField(
        default=False,
        help_text="Client paid upfront — skip auto-invoicing for covered services.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.name} - {self.get_contract_type_display()} ({self.status})"

    @property
    def line_items_total(self):
        return sum(li.line_total for li in self.line_items.all())


class ContractLineItem(models.Model):
    """Individual service included in a contract."""
    FREQUENCY_CHOICES = [
        ("per_visit", "Per Visit"),
        ("weekly", "Weekly"),
        ("biweekly", "Bi-Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("seasonal", "Seasonal"),
        ("annual", "Annual"),
        ("as_needed", "As Needed"),
    ]

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="line_items")
    service_name = models.CharField(max_length=200, help_text="e.g. Mowing, Mulch, Spring Cleanup")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="per_visit")
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    times_expected = models.PositiveSmallIntegerField(null=True, blank=True, help_text="How many times per year")
    times_completed = models.PositiveSmallIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.service_name} — {self.contract}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def progress_display(self):
        if self.times_expected:
            return f"{self.times_completed}/{self.times_expected}"
        return ""


class Property(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="properties",
    )

    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    notes = models.TextField(blank=True)

    gate_code = models.CharField(max_length=50, blank=True)
    has_dog = models.BooleanField(default=False)

    # Yard / lot square footage — used for fertilization product quantity
    # calculations and per-sqft pricing. Optional because not every client
    # needs lawn services.
    yard_sqft = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Yard sq ft",
        help_text="Lawn square footage. Used to auto-calculate fertilizer quantities and per-sqft pricing.",
    )

    # Saved polygon coordinates from the satellite measurement tool.
    # Stored as JSON: [[{lat, lng}, ...], ...] — one list per polygon.
    lawn_polygons = models.JSONField(
        null=True,
        blank=True,
        help_text="Saved polygon coordinates from satellite measurement tool.",
    )

    # Fertilization / seasonal program: number of applications per year (e.g. 4). Used for "schedule fertilization" to suggest dates and group with other clients.
    fertilization_services_per_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="For fertilization programs: how many applications per year (e.g. 4). Enables smart scheduling with other fertilization clients.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.address


class ClientMessage(models.Model):
    """Stores all client communications (email and SMS) for history under the client profile."""
    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_CHOICES = [(CHANNEL_EMAIL, "Email"), (CHANNEL_SMS, "SMS")]

    DIRECTION_SENT = "sent"
    DIRECTION_RECEIVED = "received"
    DIRECTION_CHOICES = [(DIRECTION_SENT, "Sent"), (DIRECTION_RECEIVED, "Received")]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)

    subject = models.CharField(max_length=255, blank=True, help_text="Email subject; blank for SMS.")
    body = models.TextField()
    to_address = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email address or phone number the message was sent to or received from.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_client_messages",
        help_text="User who sent this message (null for received or system).",
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Received messages are unread until viewed on the client profile.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_direction_display()} {self.get_channel_display()} to {self.customer.name} at {self.created_at}"

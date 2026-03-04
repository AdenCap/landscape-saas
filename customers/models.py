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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.name} - {self.get_contract_type_display()} ({self.status})"


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

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from businesses.models import Business


class CustomerManager(models.Manager):
    """Custom manager that excludes soft-deleted customers by default."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        """Return queryset including soft-deleted customers."""
        return super().get_queryset()

    def deleted_only(self):
        """Return only soft-deleted customers."""
        return super().get_queryset().filter(deleted_at__isnull=False)


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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete support
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this customer was soft-deleted. Null means active.",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_customers",
        help_text="User who soft-deleted this customer.",
    )

    # Managers: default excludes deleted customers, all_objects includes them
    objects = CustomerManager()
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
        """Permanently delete this customer (use with caution)."""
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self):
        """Return True if this customer has been soft-deleted."""
        return self.deleted_at is not None

    @property
    def full_address(self):
        parts = [
            self.address_line1,
            self.address_line2,
            f"{self.city}, {self.state} {self.postal_code}".strip(", ") if (self.city or self.state or self.postal_code) else None,
        ]
        return ", ".join(p for p in parts if p) or "—"


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

import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from businesses.models import Business


class User(AbstractUser):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('manager', 'Manager'),
        ('crew', 'Crew'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,  # Owner can be null initially if needed
        blank=True
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='crew')
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Hourly cost for crew members (used for labor cost reporting)'
    )

    # Employee profile
    phone = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True, verbose_name='Address')
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='ZIP / Postal code')

    color = models.CharField(
        max_length=7,
        blank=True,
        default='',
        help_text='Hex color for calendar/route (e.g. #22c55e). Owner can customize.'
    )
    
    is_platform_admin = models.BooleanField(
        default=False,
        help_text='Platform admin access: can view platform analytics, manage businesses, and access admin features.'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def full_address(self):
        parts = [
            self.address_line1,
            self.address_line2,
            f"{self.city}, {self.state} {self.postal_code}".strip(", ") if (self.city or self.state or self.postal_code) else None,
        ]
        return ", ".join(p for p in parts if p) or ""


class EmployeeInvite(models.Model):
    """Invite token that lets an employee join a business via link."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="employee_invites",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invites",
        null=True,
        blank=True,
        help_text="The User account created for this invite.",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=10,
        choices=User.ROLE_CHOICES,
        default="crew",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)

    INVITE_EXPIRY_DAYS = 7

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite for {self.email} → {self.business.name}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(days=self.INVITE_EXPIRY_DAYS)

    @property
    def is_valid(self):
        return not self.accepted and not self.is_expired


class EmployeePayment(models.Model):
    """Record of a payment made to an employee (e.g. payroll)."""
    PAYMENT_TYPE_CHOICES = [
        ('regular', 'Regular Pay'),
        ('bonus', 'Bonus'),
        ('deduction', 'Deduction'),
        ('reimbursement', 'Reimbursement'),
    ]
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='employee_payments',
    )
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments_received',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='regular')
    paid_date = models.DateField()
    notes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    quickbooks_journal_entry_id = models.CharField(
        max_length=32, blank=True, null=True,
        help_text="QuickBooks Journal Entry Id after sync",
    )

    class Meta:
        ordering = ['-paid_date', '-created_at']

    def __str__(self):
        return f"{self.employee} – ${self.amount} on {self.paid_date}"


class TrustedDevice(models.Model):
    """Devices that have passed 2FA once; we skip 2FA on next login from this device."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True, help_text="e.g. Chrome on Mac")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} – {self.name or self.token[:8]}…"


class Notification(models.Model):
    """In-app notification from business owner to employee(s)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications_sent",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications_received",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_user} → {self.to_user}: {self.message[:50]}…"


class PushSubscription(models.Model):
    """Web Push subscription for browser notifications."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Push sub for {self.user} ({self.endpoint[:50]}...)"


class AuditLog(models.Model):
    """Security audit trail: platform admin actions, logins, etc."""
    ACTION_CHOICES = [
        ("platform_enter", "Platform admin entered business"),
        ("platform_exit", "Platform admin exited business"),
        ("admin_grant", "Granted platform admin access"),
        ("admin_revoke", "Revoked platform admin access"),
        ("login", "User login"),
        ("login_failed", "Failed login attempt"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    details = models.CharField(max_length=500, blank=True, help_text="e.g. business name, IP, reason")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} by {self.user_id} at {self.created_at}"


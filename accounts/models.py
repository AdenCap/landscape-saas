from django.contrib.auth.models import AbstractUser
from django.db import models
from businesses.models import Business


class User(AbstractUser):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
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
        help_text='Hex color for calendar/route (e.g. #3b82f6). Owner can customize.'
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


class EmployeePayment(models.Model):
    """Record of a payment made to an employee (e.g. payroll)."""
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


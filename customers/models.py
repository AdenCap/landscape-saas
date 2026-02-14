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

    # Billing / mailing address (properties have service addresses)
    address_line1 = models.CharField(max_length=255, blank=True, verbose_name='Address')
    address_line2 = models.CharField(max_length=255, blank=True, verbose_name='Address line 2')
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='ZIP / Postal code')

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

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
        related_name='properties'
    )

    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    notes = models.TextField(blank=True)

    gate_code = models.CharField(max_length=50, blank=True)
    has_dog = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.address

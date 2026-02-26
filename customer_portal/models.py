"""Customer Portal: Allow customers to log in and view their invoices, estimates, and service history."""
from django.db import models
from django.conf import settings
from customers.models import Customer
import secrets


class CustomerPortalAccess(models.Model):
    """Customer portal access - token-based login for customers."""
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='portal_access',
        help_text="The customer record this portal access is for"
    )
    access_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Secret token for customer to access their portal"
    )
    password_hash = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional password hash (if customer sets a password)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Customer Portal Access'
        verbose_name_plural = 'Customer Portal Access'
    
    def __str__(self):
        return f"{self.customer.name} Portal Access"
    
    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_or_create_for_customer(cls, customer):
        """Get or create portal access for a customer."""
        access, created = cls.objects.get_or_create(customer=customer)
        return access

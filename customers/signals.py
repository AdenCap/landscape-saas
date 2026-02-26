"""Signals for customer automation: portal access creation."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer
from customer_portal.models import CustomerPortalAccess


@receiver(post_save, sender=Customer)
def create_portal_access(sender, instance, created, **kwargs):
    """Create portal access when a customer is created."""
    if created and instance.email:
        # Create portal access for new customers
        CustomerPortalAccess.get_or_create_for_customer(instance)

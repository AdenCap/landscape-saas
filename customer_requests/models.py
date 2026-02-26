"""Customer Self-Service: Allow customers to request services and estimates."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from customers.models import Customer
from billing.models import Estimate


class ServiceRequest(models.Model):
    """Customer request for service or estimate."""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('estimate_created', 'Estimate Created'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    ]
    
    REQUEST_TYPE_CHOICES = [
        ('estimate', 'Request Estimate'),
        ('service', 'Request Service'),
        ('maintenance', 'Maintenance Request'),
        ('other', 'Other'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='service_requests'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='service_requests',
        null=True,
        blank=True,
        help_text="Customer if logged in, otherwise null for anonymous requests"
    )
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='estimate')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Contact info (for anonymous requests)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=500, help_text="Service address")
    
    # Request details
    service_description = models.TextField(help_text="What service is needed?")
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Linked records
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_requests',
        help_text="Estimate created from this request"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_requests_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.get_request_type_display()} ({self.get_status_display()})"

"""Lead Management: Track prospects from inquiry to conversion."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from customers.models import Customer


class Lead(models.Model):
    """A potential customer (prospect) before they become a customer."""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('estimate_sent', 'Estimate Sent'),
        ('negotiating', 'Negotiating'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
    ]
    
    SOURCE_CHOICES = [
        ('website', 'Website'),
        ('referral', 'Referral'),
        ('google', 'Google Search'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('yelp', 'Yelp'),
        ('nextdoor', 'Nextdoor'),
        ('phone', 'Phone Call'),
        ('walk_in', 'Walk-in'),
        ('other', 'Other'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='leads'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=500, blank=True, help_text="Service address")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='website')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    notes = models.TextField(blank=True)
    
    # Conversion tracking
    converted_customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_lead',
        help_text="Customer record if this lead was converted"
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    
    # Follow-up
    next_follow_up = models.DateTimeField(null=True, blank=True, help_text="When to follow up next")
    follow_up_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_created'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

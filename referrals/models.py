"""Referral Tracking: Track referral sources and rewards."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from customers.models import Customer


class Referral(models.Model):
    """Referral tracking: who referred whom."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('qualified', 'Qualified'),
        ('converted', 'Converted'),
        ('rewarded', 'Rewarded'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='referrals'
    )
    referrer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='referrals_made',
        help_text="Customer who made the referral"
    )
    referred_customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_by',
        help_text="Customer who was referred (if converted)"
    )
    referred_name = models.CharField(
        max_length=255,
        help_text="Name of referred person (if not yet a customer)"
    )
    referred_email = models.EmailField(blank=True)
    referred_phone = models.CharField(max_length=20, blank=True)
    
    referral_code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique referral code"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Reward tracking
    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Reward amount for referrer"
    )
    reward_paid = models.BooleanField(default=False)
    reward_paid_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.referrer.name} → {self.referred_name or self.referred_customer.name if self.referred_customer else 'Unknown'}"

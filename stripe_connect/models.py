"""
Models for Stripe Connect V2 integration.

This module handles:
- Connected account information
- Products created on connected accounts
- Subscriptions for connected accounts
- Webhook event tracking for idempotency
"""
from django.db import models
from django.conf import settings
from businesses.models import Business


class ConnectedAccount(models.Model):
    """
    Stores mapping from Business to Stripe Connect V2 account ID.
    
    V2 accounts use a single account ID (acct_xxx) that can be used
    for both merchant and customer operations.
    """
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name='connected_account',
        help_text="The business that owns this connected account"
    )
    
    # V2 account ID - this is the main identifier for the connected account
    # Format: acct_xxx
    account_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe Connect V2 account ID (acct_xxx). This ID is used for both merchant and customer operations."
    )
    
    # Account status fields (fetched from API, not stored long-term)
    # These are cached but should be verified via API when needed
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name of the connected account"
    )
    contact_email = models.EmailField(
        blank=True,
        help_text="Contact email for the connected account"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Connected Account"
        verbose_name_plural = "Connected Accounts"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.business.name} - {self.account_id}"


class ConnectedProduct(models.Model):
    """
    Products created on a connected account.
    
    These products are created using the Stripe-Account header
    pointing to the connected account.
    """
    connected_account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="The connected account that owns this product"
    )
    
    # Stripe product ID (prod_xxx)
    stripe_product_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe product ID (prod_xxx)"
    )
    
    # Stripe price ID (price_xxx) - the default price for this product
    stripe_price_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Stripe price ID (price_xxx) - default price for this product"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Product name"
    )
    description = models.TextField(
        blank=True,
        help_text="Product description"
    )
    
    # Price information (stored for quick access, but can be fetched from Stripe)
    price_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in cents (will be converted to dollars for display)"
    )
    currency = models.CharField(
        max_length=3,
        default='usd',
        help_text="Currency code (e.g., 'usd')"
    )
    
    active = models.BooleanField(
        default=True,
        help_text="Whether the product is active in Stripe"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Connected Product"
        verbose_name_plural = "Connected Products"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.connected_account.business.name}"
    
    @property
    def price_dollars(self):
        """Convert price from cents to dollars for display."""
        return self.price_amount / 100


class ConnectedSubscription(models.Model):
    """
    Subscriptions for connected accounts.
    
    These subscriptions are created at the platform level but
    charge the connected account (using customer_account parameter).
    """
    connected_account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        help_text="The connected account that has this subscription"
    )
    
    # Stripe subscription ID (sub_xxx)
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe subscription ID (sub_xxx)"
    )
    
    # Subscription status (active, trialing, canceled, etc.)
    status = models.CharField(
        max_length=50,
        help_text="Subscription status from Stripe"
    )
    
    # Price ID that this subscription is for
    price_id = models.CharField(
        max_length=255,
        help_text="Stripe price ID for this subscription"
    )
    
    # Current period information
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of current billing period"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of current billing period"
    )
    
    # Cancellation information
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Whether subscription will cancel at period end"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Connected Subscription"
        verbose_name_plural = "Connected Subscriptions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.connected_account.business.name} - {self.status}"


class ConnectWebhookEvent(models.Model):
    """
    Track Stripe Connect webhook events for idempotency.
    
    Prevents processing the same event multiple times.
    """
    event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe event ID (evt_xxx or thin event ID)"
    )
    
    event_type = models.CharField(
        max_length=255,
        help_text="Event type (e.g., 'v2.core.account[requirements].updated')"
    )
    
    processed = models.BooleanField(
        default=False,
        help_text="Whether this event has been processed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this event was processed"
    )
    
    class Meta:
        verbose_name = "Connect Webhook Event"
        verbose_name_plural = "Connect Webhook Events"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} - {self.event_id}"

"""
Models for Stripe Connect V2 integration.
"""
from django.db import models
from businesses.models import Business


class ConnectedAccountProduct(models.Model):
    """
    Store products created on connected accounts.
    This is optional - you can also fetch products directly from Stripe.
    Storing locally allows for faster queries and custom metadata.
    """
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="stripe_products",
        help_text="The business (connected account) that owns this product"
    )
    stripe_product_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe Product ID (prod_...)"
    )
    stripe_price_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Stripe Price ID (price_...)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Product name"
    )
    description = models.TextField(
        blank=True,
        help_text="Product description"
    )
    price_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in dollars (e.g. 29.99)"
    )
    currency = models.CharField(
        max_length=3,
        default="usd",
        help_text="Currency code (e.g. usd)"
    )
    active = models.BooleanField(
        default=True,
        help_text="Whether the product is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "active"]),
        ]

    def __str__(self):
        return f"{self.name} - ${self.price_amount} ({self.business.name})"


class ConnectedAccountSubscription(models.Model):
    """
    Track subscriptions for connected accounts (when they subscribe to your platform).
    """
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="connect_subscriptions",
        help_text="The connected account (business) with this subscription"
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe Subscription ID (sub_...)"
    )
    status = models.CharField(
        max_length=32,
        choices=[
            ("active", "Active"),
            ("trialing", "Trialing"),
            ("past_due", "Past due"),
            ("canceled", "Canceled"),
            ("unpaid", "Unpaid"),
        ],
        help_text="Current subscription status"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current billing period ends"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name} - {self.status} ({self.stripe_subscription_id})"

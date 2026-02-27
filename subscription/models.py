"""Models for Stripe webhook event tracking and idempotency."""
from django.db import models
from django.utils import timezone


class StripeWebhookEvent(models.Model):
    """
    Track Stripe webhook events for idempotency.
    Prevents duplicate processing of the same event.
    """
    event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe event ID (evt_...)",
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Event type (e.g., checkout.session.completed)",
    )
    processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this event has been successfully processed",
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the event was processed",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if processing failed",
    )
    raw_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Full event data (for debugging)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_id"]),
            models.Index(fields=["event_type", "processed"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"

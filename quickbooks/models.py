from django.db import models
from django.conf import settings
from businesses.models import Business


class QuickBooksErrorLog(models.Model):
    """Stored errors from QuickBooks sync (push invoice, payroll) for owner visibility."""
    ACTION_CHOICES = [
        ("push_invoice", "Push invoice"),
        ("sync_payroll", "Sync payroll"),
        ("oauth", "OAuth"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="quickbooks_error_logs")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    reference_id = models.CharField(max_length=64, blank=True, help_text="e.g. invoice id or payment id")
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class QuickBooksConnection(models.Model):
    """Per-business QuickBooks Online OAuth connection."""
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name='quickbooks_connection',
    )
    realm_id = models.CharField(max_length=32, help_text='QuickBooks company ID')
    access_token = models.CharField(max_length=512)
    refresh_token = models.CharField(max_length=512)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'QuickBooks connection'
        verbose_name_plural = 'QuickBooks connections'

    def __str__(self):
        return f"QuickBooks – {self.business.name}"

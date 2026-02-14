from django.db import models
from businesses.models import Business


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

"""Document Storage: Centralized document management for customers, contracts, photos, etc."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from customers.models import Customer
from jobs.models import Job
from billing.models import Invoice, Estimate


class Document(models.Model):
    """Document file stored for a customer, job, invoice, etc."""
    DOCUMENT_TYPE_CHOICES = [
        ('contract', 'Contract'),
        ('photo', 'Photo'),
        ('permit', 'Permit'),
        ('invoice', 'Invoice'),
        ('estimate', 'Estimate'),
        ('receipt', 'Receipt'),
        ('warranty', 'Warranty'),
        ('other', 'Other'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default='other')
    title = models.CharField(max_length=255, help_text="Document title/name")
    file = models.FileField(upload_to='documents/%Y/%m/')
    description = models.TextField(blank=True)
    
    # Links to related records
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    
    # Access control
    is_visible_to_customer = models.BooleanField(
        default=False,
        help_text="Can customer view this document in their portal?"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def file_size(self):
        """Get file size in bytes."""
        try:
            return self.file.size
        except:
            return 0

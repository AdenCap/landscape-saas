from django.db import models


class Business(models.Model):
    name = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    AUTO_INVOICE_CHOICES = [
    ('auto', 'Automatically create invoices'),
    ('manual', 'Manually create invoices'),
    ]

    auto_invoice = models.CharField(
        max_length=10,
        choices=AUTO_INVOICE_CHOICES,
        default='manual'
    )



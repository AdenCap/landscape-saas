from django.db import models


class Business(models.Model):
    name = models.CharField(max_length=255)

    logo = models.ImageField(
        upload_to="business_logos/%Y/",
        blank=True,
        null=True,
        help_text="Logo shown on invoices, estimates, and emails sent to clients",
    )

    # Communication / branding - used when sending estimates and contacting clients
    from_email = models.EmailField(
        blank=True,
        help_text="Email address estimates and messages are sent from (e.g. info@yourbusiness.com)"
    )
    contact_email = models.EmailField(
        blank=True,
        help_text="Email clients can use to reach you (shown in estimates/emails)"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number clients can use to reach you (shown in estimates/emails)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_from_email(self):
        """Email to send from; falls back to display format with business name."""
        if self.from_email:
            return f"{self.name} <{self.from_email}>"
        return None

    AUTO_INVOICE_CHOICES = [
    ('auto', 'Automatically create invoices'),
    ('manual', 'Manually create invoices'),
    ]

    auto_invoice = models.CharField(
        max_length=10,
        choices=AUTO_INVOICE_CHOICES,
        default='manual'
    )



from django.db import models


class Business(models.Model):
    name = models.CharField(max_length=255)

    logo = models.ImageField(
        upload_to="business_logos/%Y/",
        blank=True,
        null=True,
        help_text="Logo shown on invoices, estimates, and emails sent to clients",
    )

    # Gmail / SMTP - owner connects their Gmail in Settings to send estimates
    email_smtp_user = models.EmailField(
        blank=True,
        help_text="Gmail address for sending estimates (e.g. your.business@gmail.com)",
    )
    email_smtp_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="Gmail App Password (not your normal password)",
    )

    # Communication / branding - used when sending estimates and contacting clients
    from_email = models.EmailField(
        blank=True,
        help_text="Email address estimates are sent from (use same as Gmail above)",
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
        """Email to send from; uses from_email or email_smtp_user."""
        addr = self.from_email or self.email_smtp_user
        if addr:
            return f"{self.name} <{addr}>"
        return None

    def get_smtp_connection(self):
        """Return Django SMTP connection using this business's Gmail config, or None if not configured."""
        if not self.email_smtp_user or not self.email_smtp_password:
            return None
        from django.core.mail import get_connection
        return get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host="smtp.gmail.com",
            port=587,
            username=self.email_smtp_user,
            password=self.email_smtp_password,
            use_tls=True,
        )

    AUTO_INVOICE_CHOICES = [
    ('auto', 'Automatically create invoices'),
    ('manual', 'Manually create invoices'),
    ]

    auto_invoice = models.CharField(
        max_length=10,
        choices=AUTO_INVOICE_CHOICES,
        default='manual'
    )

    estimate_follow_up_days = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text="Send automatic follow-up X days after estimate sent (0 = manual only)",
    )



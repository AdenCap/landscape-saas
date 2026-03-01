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
        from .email_credentials import decrypt_password
        password = decrypt_password(self.email_smtp_password)
        return get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host="smtp.gmail.com",
            port=587,
            username=self.email_smtp_user,
            password=password,
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

    require_completion_photo = models.BooleanField(
        default=False,
        help_text="If set, crew must upload at least one completion photo before marking the job complete.",
    )

    # Payment reminders for sent/unpaid invoices
    invoice_reminder_enabled = models.BooleanField(
        default=False,
        help_text="Send automatic payment reminder emails for overdue invoices.",
    )
    invoice_reminder_days = models.CharField(
        max_length=64,
        blank=True,
        default="7,14,21",
        help_text="Comma-separated days after due date to send reminders (e.g. 7,14,21).",
    )

    estimate_follow_up_days = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text="Send automatic follow-up X days after estimate sent (0 = manual only)",
    )

    # Payment methods — shown on invoices so customers can pay via Venmo, Zelle, or Cash App
    venmo_username = models.CharField(
        max_length=64,
        blank=True,
        help_text="Your Venmo username (e.g. @YourBusiness). Shown on invoices.",
    )
    zelle_email_or_phone = models.CharField(
        max_length=128,
        blank=True,
        help_text="Email or phone number for Zelle. Shown on invoices.",
    )
    cashapp_cashtag = models.CharField(
        max_length=32,
        blank=True,
        help_text="Cash App $cashtag (e.g. $YourBusiness). Shown on invoices.",
    )

    # Customizable email content (leave blank to use defaults)
    invoice_email_subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Subject line when sending invoices by email. Use {{invoice_id}}, {{customer_name}}, {{business_name}}. Leave blank for default.",
    )
    invoice_email_intro = models.TextField(
        blank=True,
        help_text="Opening line in the invoice email (e.g. “Hi {{customer_name}}, please find your invoice below.”). Leave blank for default.",
    )
    invoice_email_closing = models.TextField(
        blank=True,
        help_text="Closing line before your contact info (e.g. “Thank you for your business.”). Leave blank for default.",
    )
    estimate_email_subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Subject line when sending estimates. Use {{title}}, {{customer_name}}, {{business_name}}. Leave blank for default.",
    )
    estimate_email_intro = models.TextField(
        blank=True,
        help_text="Opening line in the estimate email. Leave blank for default.",
    )
    estimate_email_closing = models.TextField(
        blank=True,
        help_text="Closing line in the estimate email. Leave blank for default.",
    )
    estimate_followup_email_subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Subject line for estimate follow-up emails. Leave blank for default.",
    )
    estimate_followup_email_intro = models.TextField(
        blank=True,
        help_text="Opening line in the estimate follow-up email. Leave blank for default.",
    )

    # Default due date for new invoices: X days from issue date (e.g. 30 = Net 30)
    default_invoice_due_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Default number of days from issue date until invoice is due (e.g. 30 for Net 30). Leave blank for no default.",
    )

    # Growing season for fertilization scheduling (month numbers 1–12)
    growing_season_start_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=3,
        help_text="First month of growing season for fertilization scheduling (1=Jan … 12=Dec). Default 3 = March.",
    )
    growing_season_end_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=10,
        help_text="Last month of growing season (1–12). Default 10 = October.",
    )

    # Payroll schedule — used for dashboard "Payroll balance" (amount due next pay period)
    PAY_FREQUENCY_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Every 2 weeks"),
        ("semimonthly", "Twice a month (e.g. 1st & 15th)"),
        ("monthly", "Monthly"),
        ("custom", "Custom (number of days)"),
        ("custom_dates", "Specific dates (e.g. 1st & 15th)"),
    ]
    pay_frequency = models.CharField(
        max_length=20,
        choices=PAY_FREQUENCY_CHOICES,
        blank=True,
        help_text="How often you run payroll. Set in Financials to show payroll balance on the dashboard.",
    )
    pay_period_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="When pay frequency is Custom: number of days in each pay period (e.g. 10 for every 10 days).",
    )
    # When pay_frequency is custom_dates: list of day-of-month (1-31), e.g. [1, 15] for 1st and 15th
    pay_specific_days = models.JSONField(
        null=True,
        blank=True,
        help_text="When pay frequency is Specific dates: list of day-of-month numbers, e.g. [1, 15] for 1st and 15th.",
    )
    next_pay_date = models.DateField(
        null=True,
        blank=True,
        help_text="Next date you will run payroll. Used with pay frequency to compute payroll balance.",
    )

    # --- Platform subscription (Business pays you for software access) ---
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Customer ID for this business (platform subscription).",
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Subscription ID (recurring payment to platform).",
    )
    subscription_status = models.CharField(
        max_length=32,
        blank=True,
        choices=[
            ("", "No subscription"),
            ("active", "Active"),
            ("trialing", "Trialing"),
            ("past_due", "Past due"),
            ("canceled", "Canceled"),
            ("unpaid", "Unpaid"),
        ],
        default="",
        help_text="Current subscription status; active or trialing = can use the app.",
    )
    subscription_current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current billing period ends (from Stripe).",
    )

    # --- Stripe Connect (Business accepts payments from their clients) ---
    stripe_connect_account_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Connect account ID so this business can accept invoice payments.",
    )
    stripe_connect_charges_enabled = models.BooleanField(
        default=False,
        help_text="Whether the connected account can accept charges (set by webhook).",
    )
    stripe_connect_application_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Platform fee % on invoice card payments for this business. Leave blank to use the global default (STRIPE_CONNECT_APPLICATION_FEE_PERCENT). Set to 0 to give this business no application fee.",
    )
    subscription_is_free = models.BooleanField(
        default=False,
        help_text="If True, this business has free access to the platform (no subscription required). Use this for partners, beta testers, or special cases.",
    )

    def has_active_subscription(self):
        """
        True if this business can use the app (active or trialing subscription).
        
        Also returns True if subscription_is_free is True (manually granted free access).
        """
        if getattr(self, "subscription_is_free", False):
            return True
        return self.subscription_status in ("active", "trialing")

    def can_accept_stripe_payments(self):
        """True if this business has connected Stripe and can accept card payments for invoices."""
        return bool(self.stripe_connect_account_id and self.stripe_connect_charges_enabled)



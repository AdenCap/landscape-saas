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

    onboarding_completed = models.BooleanField(
        default=False,
        help_text="Whether initial onboarding flow has been completed for this business.",
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was marked complete.",
    )

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

    DEFAULT_INVOICE_AUTOMATION_CHOICES = [
        ("", "Ask each time (owner chooses per completed job)"),
        ("per_service", "Per service (create invoice when each job is completed)"),
        ("monthly", "Monthly batching (group completed jobs into monthly invoice)"),
    ]
    default_invoice_automation_mode = models.CharField(
        max_length=20,
        choices=DEFAULT_INVOICE_AUTOMATION_CHOICES,
        blank=True,
        default="",
        help_text="Default behavior when a customer does not have invoice frequency set.",
    )

    AUTO_SEND_BEHAVIOR_CHOICES = [
        ("draft", "Create draft invoice (owner reviews before send)"),
        ("send", "Automatically approve & send immediately"),
    ]
    auto_invoice_send_behavior = models.CharField(
        max_length=10,
        choices=AUTO_SEND_BEHAVIOR_CHOICES,
        default="draft",
        help_text="For automated per-service invoices: draft-only (recommended) or auto-send.",
    )

    default_monthly_invoice_send_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Default day (1-28) to send monthly invoices when customer-level day is not set.",
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
    invoice_reminder_require_owner_approval = models.BooleanField(
        default=True,
        help_text="If enabled, automatic reminder jobs require owner-triggered run (safer mode).",
    )

    estimate_follow_up_days = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text="Send automatic follow-up X days after estimate sent (0 = manual only)",
    )
    estimate_follow_up_cadence_days = models.CharField(
        max_length=64,
        blank=True,
        default="3,7,14",
        help_text="Follow-up cadence days after estimate sent (comma-separated).",
    )
    quote_upsell_suggestions = models.TextField(
        blank=True,
        default="Seasonal fertilizer program\nMulch refresh\nIrrigation tune-up",
        help_text="Optional upsells to include in follow-up nudges (one per line).",
    )

    google_review_requests_enabled = models.BooleanField(
        default=False,
        help_text="Automatically email clients a Google review request after payment.",
    )
    google_review_link = models.URLField(
        blank=True,
        help_text="Your direct Google review link (Place review URL).",
    )
    google_review_request_delay_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text="Hours after payment before first review request is sent.",
    )
    google_review_followup_days = models.PositiveSmallIntegerField(
        default=7,
        help_text="Days between follow-up review requests when client has not responded.",
    )
    google_review_max_attempts = models.PositiveSmallIntegerField(
        default=2,
        help_text="Maximum total review emails per client.",
    )
    google_review_sms_enabled = models.BooleanField(
        default=False,
        help_text="Also send review requests via SMS when client phone is available.",
    )
    google_review_sms_template = models.TextField(
        blank=True,
        help_text="Optional SMS template. Use {{customer_name}}, {{business_name}}, {{review_link}}.",
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

    # Timezone — all times in the app display in this timezone
    US_TIMEZONE_CHOICES = [
        ("America/New_York", "Eastern"),
        ("America/Chicago", "Central"),
        ("America/Denver", "Mountain"),
        ("America/Los_Angeles", "Pacific"),
        ("America/Anchorage", "Alaska"),
        ("Pacific/Honolulu", "Hawaii"),
    ]
    timezone = models.CharField(
        max_length=50,
        choices=US_TIMEZONE_CHOICES,
        default="America/New_York",
        help_text="All times in the app display in this timezone.",
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
    subscription_plan_tier = models.CharField(
        max_length=20,
        choices=[("solo", "Solo Starter"), ("core", "Pro All-Access")],
        default="core",
        help_text="Current plan tier for packaging and billing display.",
    )
    complimentary_access_enabled = models.BooleanField(
        default=False,
        help_text="If enabled by platform admin, this business can access the app without an active paid subscription.",
    )
    plan_crew_soft_cap_override = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional per-business soft cap override for crew users before growth recommendation.",
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
        help_text="Platform fee % on invoice card payments for this business. Leave blank to use the global default (STRIPE_CONNECT_APPLICATION_FEE_PERCENT).",
    )

    def has_active_subscription(self):
        """True if this business can use the app (active/trialing or complimentary override)."""
        return self.subscription_status in ("active", "trialing") or self.complimentary_access_enabled

    def can_accept_stripe_payments(self):
        """True if this business has connected Stripe and can accept card payments for invoices."""
        return bool(self.stripe_connect_account_id and self.stripe_connect_charges_enabled)

    def crew_soft_cap(self, default_cap=12):
        return self.plan_crew_soft_cap_override or default_cap

    def is_growth_tier(self):
        return self.subscription_plan_tier == "growth"



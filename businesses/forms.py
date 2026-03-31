from django import forms
from .models import Business
from .email_credentials import encrypt_password


class BusinessSettingsForm(forms.ModelForm):
    email_smtp_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Leave blank to keep current", "autocomplete": "new-password"}),
        label="Gmail App Password",
        help_text="Create one at myaccount.google.com/apppasswords (requires 2-Step Verification). Stored encrypted.",
    )
    class Meta:
        model = Business
        fields = [
            "name",
            "logo",
            "timezone",
            "business_type",
            "business_subtype",
            "email_smtp_user",
            "email_smtp_password",
            "from_email",
            "contact_email",
            "contact_phone",
            "shop_address",
            "require_completion_photo",
            "default_invoice_automation_mode",
            "auto_invoice_send_behavior",
            "default_monthly_invoice_send_day",
            "invoice_reminder_enabled",
            "invoice_reminder_days",
            "invoice_reminder_require_owner_approval",
            "estimate_follow_up_days",
            "estimate_follow_up_cadence_days",
            "quote_upsell_suggestions",
            "google_review_requests_enabled",
            "google_review_link",
            "google_review_request_delay_hours",
            "google_review_followup_days",
            "google_review_max_attempts",
            "google_review_sms_enabled",
            "google_review_sms_template",
            "default_invoice_due_days",
            "default_estimate_valid_days",
            "growing_season_start_month",
            "growing_season_end_month",
            "default_fert_price_per_sqft",
            "venmo_username",
            "zelle_email_or_phone",
            "cashapp_cashtag",
            "paypal_link",
            "invoice_email_subject",
            "invoice_email_intro",
            "invoice_email_closing",
            "estimate_email_subject",
            "estimate_email_intro",
            "estimate_email_closing",
            "estimate_followup_email_subject",
            "estimate_followup_email_intro",
            # Client notifications
            "notify_job_scheduled",
            "notify_crew_en_route",
            "notify_job_completed",
            "notify_include_completion_photos",
            # Notification templates
            "template_job_scheduled",
            "template_crew_en_route",
            "template_job_completed",
        ]
        labels = {
            "timezone": "Business timezone",
            "venmo_username": "Venmo handle",
            "zelle_email_or_phone": "Zelle (email or phone)",
            "cashapp_cashtag": "Cash App handle",
            "notify_job_scheduled": "Job scheduled",
            "notify_crew_en_route": "Crew on the way",
            "notify_job_completed": "Job completed",
            "notify_include_completion_photos": "Include completion photos",
            "template_job_scheduled": "Scheduled notification",
            "template_crew_en_route": "En-route notification",
            "template_job_completed": "Completed notification",
        }
        help_texts = {
            "timezone": "All dates and times across the app display in this timezone.",
            "require_completion_photo": "If enabled, crew must upload at least one completion photo before marking a job complete.",
            "default_invoice_automation_mode": "Default invoice automation when a customer-level invoice setting is not set.",
            "auto_invoice_send_behavior": "For per-service automation, choose whether to create draft invoices or send immediately.",
            "default_monthly_invoice_send_day": "Default monthly send day (1-28) when customer-level send day is blank.",
            "invoice_reminder_enabled": "Send automatic payment reminder emails for overdue invoices (run the send_invoice_reminders command daily, e.g. via cron).",
            "invoice_reminder_days": "Days after due date to send reminders, comma-separated (e.g. 7,14,21).",
            "invoice_reminder_require_owner_approval": "If enabled, reminders only send when owner triggers from Command Center.",
            "email_smtp_user": "Your Gmail address for sending estimates to clients.",
            "from_email": "Shown as the sender; use the same Gmail address as above.",
            "contact_email": "Shown to clients so they can reach you.",
            "contact_phone": "Shown to clients so they can call you.",
            "estimate_follow_up_days": "Auto-send follow-up X days after estimate sent (legacy single-day setting; use cadence below).",
            "estimate_follow_up_cadence_days": "Comma-separated cadence days (e.g. 3,7,14).",
            "quote_upsell_suggestions": "Shown in quote follow-up nudges; one upsell per line.",
            "google_review_requests_enabled": "Automatically request Google reviews from paid clients.",
            "google_review_link": "Direct URL where clients can leave a Google review.",
            "google_review_request_delay_hours": "Wait this many hours after payment before first review ask.",
            "google_review_followup_days": "Days to wait before one follow-up review ask.",
            "google_review_max_attempts": "Maximum number of review request emails per client.",
            "google_review_sms_enabled": "If enabled, sends review request SMS when phone exists and Twilio is configured.",
            "google_review_sms_template": "Custom SMS body. Leave blank for default template.",
            "default_invoice_due_days": "New invoices will be due this many days after the issue date (e.g. 30 for Net 30). Leave blank for no default.",
            "default_estimate_valid_days": "New estimates will be valid for this many days (default 30). Shown on the estimate form — you can override per estimate.",
            "growing_season_start_month": "First month of growing season for fertilization scheduling (1–12). Default 3 = March.",
            "growing_season_end_month": "Last month of growing season (1–12). Default 10 = October.",
            "venmo_username": "e.g. @YourBusiness — shown at the bottom of every sent invoice.",
            "zelle_email_or_phone": "Email or phone — shown at the bottom of every sent invoice.",
            "cashapp_cashtag": "e.g. $YourBusiness — shown at the bottom of every sent invoice.",
            "invoice_email_subject": "Leave blank for: Invoice #{{invoice_id}} from {{business_name}}",
            "invoice_email_intro": "e.g. Hi {{customer_name}}, please find your invoice below.",
            "invoice_email_closing": "e.g. Thank you for your business.",
            "estimate_email_subject": "Leave blank for: {{title}} – {{business_name}}",
            "estimate_email_intro": "Optional greeting before the estimate summary.",
            "estimate_email_closing": "Optional sign-off.",
            "estimate_followup_email_subject": "Leave blank for: Reminder: {{title}} – {{business_name}}",
            "estimate_followup_email_intro": "Optional intro for follow-up emails.",
            "notify_job_scheduled": "Text or email client when a job is put on the calendar.",
            "notify_crew_en_route": "Text or email client when crew taps 'On My Way'.",
            "notify_job_completed": "Text or email client when a job is marked complete.",
            "notify_include_completion_photos": "Attach completion photos in the job-completed email.",
            "template_job_scheduled": "Variables: {{customer_name}}, {{service_list}}, {{business_name}}, {{scheduled_date}}, {{scheduled_time}}",
            "template_crew_en_route": "Variables: {{customer_name}}, {{service_list}}, {{business_name}}, {{crew_name}}",
            "template_job_completed": "Variables: {{customer_name}}, {{service_list}}, {{business_name}}",
        }
        widgets = {
            "email_smtp_password": forms.PasswordInput(
                render_value=False,
                attrs={"placeholder": "Leave blank to keep current", "autocomplete": "new-password"},
            ),
            "default_invoice_due_days": forms.NumberInput(attrs={"min": 0, "max": 365, "placeholder": "e.g. 30"}),
            "google_review_request_delay_hours": forms.NumberInput(attrs={"min": 0, "max": 720}),
            "google_review_followup_days": forms.NumberInput(attrs={"min": 1, "max": 90}),
            "google_review_max_attempts": forms.NumberInput(attrs={"min": 1, "max": 10}),
            "google_review_sms_template": forms.Textarea(attrs={"rows": 2, "placeholder": "Hi {{customer_name}}, if you have 30 seconds we'd love your review: {{review_link}}"}),
            "default_monthly_invoice_send_day": forms.NumberInput(attrs={"min": 1, "max": 28, "placeholder": "e.g. 1 or 15"}),
            "growing_season_start_month": forms.NumberInput(attrs={"min": 1, "max": 12, "placeholder": "3"}),
            "growing_season_end_month": forms.NumberInput(attrs={"min": 1, "max": 12, "placeholder": "10"}),
            "invoice_email_intro": forms.Textarea(attrs={"rows": 2, "placeholder": "Hi {{customer_name}}, please find your invoice below."}),
            "invoice_email_closing": forms.Textarea(attrs={"rows": 2, "placeholder": "Thank you for your business."}),
            "estimate_email_intro": forms.Textarea(attrs={"rows": 2}),
            "estimate_email_closing": forms.Textarea(attrs={"rows": 2}),
            "estimate_followup_email_intro": forms.Textarea(attrs={"rows": 2}),
            "template_job_scheduled": forms.Textarea(attrs={"rows": 2, "placeholder": "Hi {{customer_name}}, your {{service_list}} is scheduled for {{scheduled_date}}."}),
            "template_crew_en_route": forms.Textarea(attrs={"rows": 2, "placeholder": "Hi {{customer_name}}, our crew is heading to your property now for {{service_list}}."}),
            "template_job_completed": forms.Textarea(attrs={"rows": 2, "placeholder": "Hi {{customer_name}}, your {{service_list}} is complete! Thank you for choosing {{business_name}}."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.email_smtp_password:
                self.fields["email_smtp_password"].widget.attrs["placeholder"] = "•••••••• (saved)"

    def save(self, commit=True):
        # Capture the existing password BEFORE super().save() overwrites it with
        # the empty submitted value (PasswordInput sends "" when left blank).
        existing_password = (
            self.instance.email_smtp_password
            if self.instance and self.instance.pk
            else ""
        )
        obj = super().save(commit=False)
        password = self.cleaned_data.get("email_smtp_password")
        if password:
            # New password entered — encrypt and store it
            obj.email_smtp_password = encrypt_password(password)
        else:
            # Field left blank — preserve the existing encrypted password
            obj.email_smtp_password = existing_password
        if commit:
            obj.save()
        return obj

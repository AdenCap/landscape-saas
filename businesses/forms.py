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
            "email_smtp_user",
            "email_smtp_password",
            "from_email",
            "contact_email",
            "contact_phone",
            "estimate_follow_up_days",
            "default_invoice_due_days",
            "growing_season_start_month",
            "growing_season_end_month",
            "venmo_username",
            "zelle_email_or_phone",
            "cashapp_cashtag",
        ]
        labels = {
            "venmo_username": "Venmo handle",
            "zelle_email_or_phone": "Zelle (email or phone)",
            "cashapp_cashtag": "Cash App handle",
        }
        help_texts = {
            "email_smtp_user": "Your Gmail address for sending estimates to clients.",
            "from_email": "Shown as the sender; use the same Gmail address as above.",
            "contact_email": "Shown to clients so they can reach you.",
            "contact_phone": "Shown to clients so they can call you.",
            "estimate_follow_up_days": "Auto-send follow-up X days after estimate sent (0 = you send manually).",
            "default_invoice_due_days": "New invoices will be due this many days after the issue date (e.g. 30 for Net 30). Leave blank for no default.",
            "growing_season_start_month": "First month of growing season for fertilization scheduling (1–12). Default 3 = March.",
            "growing_season_end_month": "Last month of growing season (1–12). Default 10 = October.",
            "venmo_username": "e.g. @YourBusiness — shown at the bottom of every sent invoice.",
            "zelle_email_or_phone": "Email or phone — shown at the bottom of every sent invoice.",
            "cashapp_cashtag": "e.g. $YourBusiness — shown at the bottom of every sent invoice.",
        }
        widgets = {
            "email_smtp_password": forms.PasswordInput(
                render_value=False,
                attrs={"placeholder": "Leave blank to keep current", "autocomplete": "new-password"},
            ),
            "default_invoice_due_days": forms.NumberInput(attrs={"min": 0, "max": 365, "placeholder": "e.g. 30"}),
            "growing_season_start_month": forms.NumberInput(attrs={"min": 1, "max": 12, "placeholder": "3"}),
            "growing_season_end_month": forms.NumberInput(attrs={"min": 1, "max": 12, "placeholder": "10"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.email_smtp_password:
            self.fields["email_smtp_password"].widget.attrs["placeholder"] = "•••••••• (saved)"

    def save(self, commit=True):
        obj = super().save(commit=False)
        password = self.cleaned_data.get("email_smtp_password")
        if password:
            obj.email_smtp_password = encrypt_password(password)
        if commit:
            obj.save()
        return obj

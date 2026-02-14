from django import forms
from .models import Business


class BusinessSettingsForm(forms.ModelForm):
    email_smtp_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Leave blank to keep current", "autocomplete": "new-password"}),
        label="Gmail App Password",
        help_text="Get one at myaccount.google.com/apppasswords (requires 2-Step Verification)",
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
        ]
        help_texts = {
            "email_smtp_user": "Your Gmail address for sending estimates to clients.",
            "from_email": "Shown as the sender; use the same Gmail address as above.",
            "contact_email": "Shown to clients so they can reach you.",
            "contact_phone": "Shown to clients so they can call you.",
        }
        widgets = {
            "email_smtp_password": forms.PasswordInput(
                render_value=False,
                attrs={"placeholder": "Leave blank to keep current", "autocomplete": "new-password"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.email_smtp_password:
            self.fields["email_smtp_password"].widget.attrs["placeholder"] = "•••••••• (saved)"

    def save(self, commit=True):
        obj = super().save(commit=False)
        password = self.cleaned_data.get("email_smtp_password")
        if password:
            obj.email_smtp_password = password
        if commit:
            obj.save()
        return obj

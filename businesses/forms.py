from django import forms
from .models import Business


class BusinessSettingsForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['name', 'logo', 'from_email', 'contact_email', 'contact_phone']
        help_texts = {
            'from_email': 'Estimates and other emails will be sent from this address.',
            'contact_email': 'Shown to clients so they can reach you.',
            'contact_phone': 'Shown to clients so they can call you.',
        }

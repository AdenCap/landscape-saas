from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from accounts.models import EmployeePayment

User = get_user_model()


class EmployeeForm(forms.ModelForm):
    """Form for editing employee profile (name, contact, address, role, pay)."""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'role', 'hourly_rate', 'color', 'is_active',
        ]
        widgets = {
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class EmployeeCreateForm(UserCreationForm):
    """Form for creating a new employee with login credentials."""
    class Meta:
        model = User
        fields = [
            'username', 'password1', 'password2',
            'first_name', 'last_name', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'role', 'hourly_rate',
        ]
        widgets = {
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class EmployeePasswordForm(forms.Form):
    """Form for owner to set/reset employee password."""
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        min_length=8,
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password1')
        p2 = cleaned_data.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match.")
        return cleaned_data


class EmployeePaymentForm(forms.ModelForm):
    """Form to record a payment made to an employee."""
    class Meta:
        model = EmployeePayment
        fields = ['amount', 'paid_date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'paid_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes (e.g. pay period)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'paid_date' in self.fields:
            self.fields['paid_date'].initial = timezone.localdate()

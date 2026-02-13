from django import forms
from .models import Customer, Property, Contract


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'phone', 'alt_phone', 'email',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Internal notes about this client...'}),
        }


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['address', 'notes', 'gate_code', 'has_dog']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ['contract_type', 'status', 'start_date', 'end_date', 'amount', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

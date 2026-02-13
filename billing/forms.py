from django import forms
from decimal import Decimal

from .models import Estimate, EstimateLineItem, EstimateImage
from customers.models import Customer


class EstimateForm(forms.ModelForm):
    class Meta:
        model = Estimate
        fields = ['customer', 'title', 'valid_until', 'notes']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields['customer'].queryset = Customer.objects.filter(business=business).order_by('name')


class EstimateLineItemForm(forms.ModelForm):
    class Meta:
        model = EstimateLineItem
        fields = ['description', 'quantity', 'unit', 'unit_price', 'is_addon', 'order']
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class EstimateImageForm(forms.ModelForm):
    class Meta:
        model = EstimateImage
        fields = ['image', 'caption', 'order']

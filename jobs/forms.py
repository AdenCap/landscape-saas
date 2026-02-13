from django import forms
from decimal import Decimal
from pricing.models import ServiceTemplate

class AddJobServiceItemForm(forms.Form):
    service = forms.ModelChoiceField(queryset=ServiceTemplate.objects.none())
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, initial=Decimal("1.00"), min_value=0)

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields["service"].queryset = ServiceTemplate.objects.filter(business=business, active=True).order_by("name")

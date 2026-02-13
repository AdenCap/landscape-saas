from django import forms
from decimal import Decimal
from pricing.models import ServiceTemplate
from customers.models import Property
from accounts.models import User


class AddJobServiceItemForm(forms.Form):
    service = forms.ModelChoiceField(queryset=ServiceTemplate.objects.none())
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, initial=Decimal("1.00"), min_value=0)

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields["service"].queryset = ServiceTemplate.objects.filter(business=business, active=True).order_by("name")


class CreateJobForm(forms.Form):
    """Landscaping job creation form with service selection."""
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        label="Property / Lawn",
        help_text="Select the customer property for this job",
    )
    scheduled_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="When should this work be done?",
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Assigned Crew",
        help_text="Crew member to perform the work",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Gate codes, dog on premises, special instructions, access notes..."}),
        help_text="Property access, hazards, or special instructions",
    )

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields["property"].queryset = Property.objects.filter(
                customer__business=business
            ).select_related("customer").order_by("address")
            self.fields["assigned_to"].queryset = User.objects.filter(
                business=business, role="crew"
            ).order_by("username")

    def clean_scheduled_date(self):
        from django.utils import timezone
        date = self.cleaned_data["scheduled_date"]
        if date and date < timezone.localdate():
            raise forms.ValidationError("Scheduled date cannot be in the past.")
        return date


class JobServiceInlineForm(forms.Form):
    """Inline form for adding a service to a new job."""
    service = forms.ModelChoiceField(queryset=ServiceTemplate.objects.none())
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, initial=Decimal("1.00"), min_value=Decimal("0.01"))

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields["service"].queryset = ServiceTemplate.objects.filter(
                business=business, active=True
            ).order_by("name")


def get_job_service_formset(business, extra=2):
    """Build formset for job services - at least 1 required."""
    from django.forms import formset_factory

    class ServiceFormWithBusiness(JobServiceInlineForm):
        def __init__(self, *args, **kwargs):
            kwargs["business"] = business
            super().__init__(*args, **kwargs)

    return formset_factory(
        ServiceFormWithBusiness,
        extra=extra,
        min_num=1,
        validate_min=True,
    )


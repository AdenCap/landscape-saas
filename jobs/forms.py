from django import forms
from decimal import Decimal
from pricing.models import ServiceTemplate
from customers.models import Customer, Property
from accounts.models import User
from .models import Crew


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
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        label="Client",
        help_text="Select the client for this job",
    )
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        label="Property / Address",
        help_text="Select the property (after choosing a client)",
    )
    scheduled_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="When should this work be done? Leave empty for unscheduled.",
    )
    scheduled_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
        help_text="Optional start time (for week/day calendar view)",
    )
    assignee_type = forms.ChoiceField(
        choices=[('', '— Unassigned —'), ('crew', 'Crew'), ('employee', 'Employee / Owner')],
        required=False,
        label="Assign to",
        widget=forms.RadioSelect(attrs={'class': 'assignee-type-radio'}),
    )
    assigned_crew = forms.ModelChoiceField(
        queryset=Crew.objects.none(),
        required=False,
        label="Crew",
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Employee",
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
            self.fields["customer"].queryset = Customer.objects.filter(
                business=business
            ).order_by("name")
            # Property queryset set in clean; initial empty for client-first flow
            self.fields["property"].queryset = Property.objects.none()
            self.fields["assigned_crew"].queryset = Crew.objects.filter(business=business).order_by("name")
            self.fields["assigned_to"].queryset = User.objects.filter(
                business=business, role__in=["crew", "owner"]
            ).order_by("first_name", "username")

        # On POST: restrict property to selected customer's properties
        if args and hasattr(args[0], "get"):
            customer_id = args[0].get("customer")
            if customer_id and business:
                self.fields["property"].queryset = Property.objects.filter(
                    customer_id=customer_id, customer__business=business
                ).order_by("address")


    def clean_scheduled_date(self):
        from django.utils import timezone
        date = self.cleaned_data.get("scheduled_date")
        if date and date < timezone.localdate():
            raise forms.ValidationError("Scheduled date cannot be in the past.")
        return date

    def clean_property(self):
        customer = self.cleaned_data.get("customer")
        property_obj = self.cleaned_data.get("property")
        if customer and property_obj and property_obj.customer_id != customer.id:
            raise forms.ValidationError("Property must belong to the selected client.")
        return property_obj


class JobServiceInlineForm(forms.Form):
    """Inline form for adding a service to a new job."""
    service = forms.ModelChoiceField(queryset=ServiceTemplate.objects.none(), required=False)
    service_name = forms.CharField(required=False, max_length=120, widget=forms.TextInput(attrs={"placeholder": "Type service name (e.g. Mowing, Mulching)...", "list": "services-datalist"}))
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, initial=Decimal("1.00"), min_value=Decimal("0.01"))

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        self._business = business
        if business:
            self.fields["service"].queryset = ServiceTemplate.objects.filter(
                business=business, active=True
            ).order_by("name")

    def clean(self):
        data = super().clean()
        service = data.get("service")
        service_name = (data.get("service_name") or "").strip()
        if not service and service_name:
            business = self._business
            if business:
                existing = ServiceTemplate.objects.filter(business=business, name__iexact=service_name).first()
                data["service"] = existing or ServiceTemplate.objects.create(business=business, name=service_name, active=True)
        return data


def get_job_service_formset(business, extra=2):
    """Build formset for job services - at least 1 required."""
    from django.forms import BaseFormSet, formset_factory

    class JobServiceFormSet(BaseFormSet):
        def clean(self):
            super().clean()
            if any(self.errors):
                return
            has_service = any(
                f.cleaned_data.get("service")
                for f in self.forms
                if f.cleaned_data
            )
            if not has_service:
                raise forms.ValidationError("Add at least one service (type or select from the list).")

    class ServiceFormWithBusiness(JobServiceInlineForm):
        def __init__(self, *args, **kwargs):
            kwargs["business"] = business
            super().__init__(*args, **kwargs)

    return formset_factory(
        ServiceFormWithBusiness,
        extra=extra,
        min_num=1,
        validate_min=True,
        formset=JobServiceFormSet,
    )


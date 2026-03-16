from django import forms
from decimal import Decimal
from pricing.models import ServiceTemplate
from customers.models import Customer, Property
from accounts.models import User
from .models import Crew, JobIssue, Meeting


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
        label="Primary Employee",
    )
    assigned_employees = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Employees",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'employee-checkbox-list'}),
        help_text="Select one or more employees for this job",
    )
    color = forms.CharField(
        required=False,
        max_length=7,
        label="Job color",
        help_text="Optional. Leave empty to use crew/employee default.",
        widget=forms.TextInput(attrs={"placeholder": "#22c55e", "pattern": "^#?[0-9A-Fa-f]{3,6}$"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Gate codes, dog on premises, special instructions, access notes..."}),
        help_text="Property access, hazards, or special instructions",
    )

    REPEAT_CHOICES = [
        ("", "One-time (do not repeat)"),
        ("weekly", "Weekly"),
        ("biweekly", "Bi-Weekly"),
        ("monthly", "Monthly"),
        ("custom", "Custom (every N days)"),
    ]
    repeat_frequency = forms.ChoiceField(
        choices=REPEAT_CHOICES,
        required=False,
        label="Repeat",
        help_text="Create a recurring schedule; future occurrences will be generated automatically.",
        widget=forms.Select(attrs={"id": "id_repeat_frequency"}),
    )
    custom_interval_days = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        label="Every N days",
        help_text="When Custom is selected: repeat every this many days.",
        widget=forms.NumberInput(attrs={"placeholder": "e.g. 10", "min": 1, "max": 365}),
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
            emp_qs = User.objects.filter(
                business=business, role__in=["crew", "owner"]
            ).order_by("first_name", "username")
            self.fields["assigned_to"].queryset = emp_qs
            self.fields["assigned_employees"].queryset = emp_qs

        # On POST: restrict property to selected customer's properties
        if args and hasattr(args[0], "get"):
            customer_id = args[0].get("customer")
            if customer_id and business:
                self.fields["property"].queryset = Property.objects.filter(
                    customer_id=customer_id, customer__business=business
                ).order_by("address")


    def clean_property(self):
        customer = self.cleaned_data.get("customer")
        property_obj = self.cleaned_data.get("property")
        if customer and property_obj and property_obj.customer_id != customer.id:
            raise forms.ValidationError("Property must belong to the selected client.")
        return property_obj

    def clean(self):
        data = super().clean()
        freq = data.get("repeat_frequency")
        custom_days = data.get("custom_interval_days")
        sched_date = data.get("scheduled_date")
        if freq == "custom" and (custom_days is None or custom_days < 1):
            self.add_error("custom_interval_days", "Enter how many days between repeats (e.g. 10).")
        if freq and not sched_date:
            self.add_error("scheduled_date", "A start date is required when the job repeats.")
        return data


class JobServiceInlineForm(forms.Form):
    """Inline form for adding a service to a new job."""
    service = forms.ModelChoiceField(queryset=ServiceTemplate.objects.none(), required=False)
    service_name = forms.CharField(required=False, max_length=120, widget=forms.TextInput(attrs={"placeholder": "Type service name (e.g. Mowing, Mulching)...", "list": "services-datalist"}))
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, initial=Decimal("1.00"), min_value=Decimal("0.01"))
    unit_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        widget=forms.NumberInput(attrs={"placeholder": "Price (optional)", "step": "0.01"}),
    )

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


def get_job_service_formset(business, extra=0):
    """Build formset for job services - starts with 1, add more via + button."""
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
        max_num=50,
        validate_min=True,
        formset=JobServiceFormSet,
    )


class ReportIssueForm(forms.Form):
    """Crew reports an issue on a job (type, description, optional photo)."""
    issue_type = forms.ChoiceField(
        choices=JobIssue.TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "Describe the issue..."}),
        required=True,
    )
    photo = forms.ImageField(required=False, help_text="Optional photo")


class MeetingForm(forms.ModelForm):
    """Owner creates/edits a meeting (e.g. client meeting) for the schedule."""
    scheduled_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Date",
    )
    scheduled_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        label="Time",
        help_text="Leave empty for all-day.",
    )

    class Meta:
        model = Meeting
        fields = (
            "title",
            "scheduled_date",
            "scheduled_time",
            "duration_minutes",
            "customer",
            "location",
            "notes",
            "reminder_hours_before",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Client walkthrough – Smith", "class": "form-control"}),
            "duration_minutes": forms.NumberInput(attrs={"min": 15, "max": 480, "step": 15, "class": "form-control"}),
            "location": forms.TextInput(attrs={"placeholder": "Address or place name", "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Agenda, prep notes...", "class": "form-control"}),
            "reminder_hours_before": forms.NumberInput(attrs={"min": 0, "max": 168, "class": "form-control"}),
            "customer": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self._business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self._business:
            self.fields["customer"].queryset = self._business.customers.order_by("name")
        self.fields["customer"].required = False
        if self.instance and self.instance.pk and getattr(self.instance, "scheduled_at", None):
            from django.utils import timezone
            dt = self.instance.scheduled_at
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            self.initial.setdefault("scheduled_date", dt.date())
            self.initial.setdefault("scheduled_time", dt.time())

    def clean(self):
        data = super().clean()
        from datetime import datetime
        from django.utils import timezone
        d = data.get("scheduled_date")
        t = data.get("scheduled_time")
        if d and t:
            dt = timezone.make_aware(datetime.combine(d, t))
            if dt < timezone.now():
                self.add_error("scheduled_date", "Meeting cannot be in the past.")
        return data

    def save(self, commit=True):
        from django.utils import timezone
        from datetime import datetime
        meeting = super().save(commit=False)
        d = self.cleaned_data.get("scheduled_date")
        t = self.cleaned_data.get("scheduled_time")
        if d:
            if t:
                meeting.scheduled_at = timezone.make_aware(datetime.combine(d, t))
            else:
                meeting.scheduled_at = timezone.make_aware(datetime.combine(d, datetime.min.time()))
        if commit:
            meeting.save()
        return meeting


from django import forms
from businesses.models import Business
from .models import Receipt


class PayScheduleForm(forms.ModelForm):
    """Pay frequency and next pay date for dashboard payroll balance."""
    pay_specific_days_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. 1, 15",
            "id": "id_pay_specific_days_input",
        }),
        help_text="Day(s) of month (1–31), comma-separated. Used when Specific dates is selected.",
    )

    class Meta:
        model = Business
        fields = ["pay_frequency", "pay_period_days", "next_pay_date"]
        widgets = {
            "pay_frequency": forms.Select(attrs={"class": "form-control", "id": "id_pay_frequency"}),
            "pay_period_days": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 90, "placeholder": "e.g. 10"}),
            "next_pay_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            raw_days = getattr(self.instance, "pay_specific_days", None)
            if raw_days and isinstance(raw_days, list):
                self.fields["pay_specific_days_input"].initial = ", ".join(str(d) for d in raw_days)

    def clean(self):
        data = super().clean()
        freq = data.get("pay_frequency")
        if freq == "custom":
            days = data.get("pay_period_days")
            if not days or days < 1 or days > 365:
                self.add_error("pay_period_days", "Enter a number of days between 1 and 365 when using Custom.")
        elif freq == "custom_dates":
            raw = (data.get("pay_specific_days_input") or "").strip()
            if not raw:
                self.add_error("pay_specific_days_input", "Enter at least one day of the month (1–31) when using Specific dates.")
            else:
                try:
                    parsed = [int(x.strip()) for x in raw.split(",") if x.strip()]
                    if not parsed or any(d < 1 or d > 31 for d in parsed):
                        self.add_error("pay_specific_days_input", "Enter comma-separated days between 1 and 31 (e.g. 1, 15).")
                    else:
                        data["pay_specific_days_parsed"] = sorted(set(parsed))
                except ValueError:
                    self.add_error("pay_specific_days_input", "Use numbers only, comma-separated (e.g. 1, 15).")
        return data


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ["file", "receipt_date", "amount", "vendor", "description", "category", "job"]
        widgets = {
            "receipt_date": forms.DateInput(attrs={"type": "date"}),
            "job": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, business=None, initial_job=None, for_job=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].required = False
        if for_job is not None:
            # Upload from job page: hide job field, view will set it
            self.fields.pop("job", None)
        elif business is not None:
            from jobs.models import Job
            self.fields["job"].queryset = Job.objects.filter(
                property__customer__business=business
            ).select_related("property", "property__customer").order_by("-scheduled_date")
            self.fields["job"].label = "Link to job (optional)"
        if initial_job is not None:
            self.fields["job"].initial = initial_job

    def clean(self):
        data = super().clean()
        if data.get("file") is None and (data.get("amount") is None and not (data.get("vendor") or data.get("description"))):
            raise forms.ValidationError("Either upload a receipt file or enter an amount and/or description.")
        return data

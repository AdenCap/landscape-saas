from django import forms
from .models import Receipt


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

from django import forms
from django.forms import modelformset_factory

from .models import TimeOffRequest, EmployeeSchedule


class TimeOffRequestForm(forms.ModelForm):
    """Form for employees to submit a time off request."""

    class Meta:
        model = TimeOffRequest
        fields = ("start_date", "end_date", "request_type", "notes")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "request_type": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional notes"}),
        }

    def clean(self):
        data = super().clean()
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("End date must be on or after start date.")
        return data


class EmployeeScheduleSlotForm(forms.ModelForm):
    """Single day slot for schedule (used in formset)."""

    class Meta:
        model = EmployeeSchedule
        fields = ("day_of_week", "start_time", "end_time")
        widgets = {
            "day_of_week": forms.HiddenInput(),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }


EmployeeScheduleFormSet = modelformset_factory(
    EmployeeSchedule,
    form=EmployeeScheduleSlotForm,
    extra=0,
    can_delete=False,
    max_num=7,
)

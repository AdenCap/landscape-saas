from django import forms
from django.forms import modelformset_factory

from .models import TimeOffRequest, EmployeeSchedule, TimeEntry


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


class TimeEntryEditForm(forms.Form):
    """Owner adjusts clock-in and clock-out times for a time entry."""
    clock_in_date = forms.DateField(label="Clock-in date", widget=forms.DateInput(attrs={"type": "date"}))
    clock_in_time = forms.TimeField(label="Clock-in time", widget=forms.TimeInput(attrs={"type": "time"}))
    clock_out_date = forms.DateField(label="Clock-out date", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    clock_out_time = forms.TimeField(label="Clock-out time", required=False, widget=forms.TimeInput(attrs={"type": "time"}))

    def __init__(self, *args, **kwargs):
        self.entry = kwargs.pop("entry", None)
        super().__init__(*args, **kwargs)
        if self.entry:
            if self.entry.clock_in:
                self.initial.setdefault("clock_in_date", self.entry.clock_in.date())
                self.initial.setdefault("clock_in_time", self.entry.clock_in.time())
            if self.entry.clock_out:
                self.initial.setdefault("clock_out_date", self.entry.clock_out.date())
                self.initial.setdefault("clock_out_time", self.entry.clock_out.time())

    def clean(self):
        from django.utils import timezone
        from datetime import datetime
        data = super().clean()
        ci_date = data.get("clock_in_date")
        ci_time = data.get("clock_in_time")
        co_date = data.get("clock_out_date")
        co_time = data.get("clock_out_time")
        if ci_date and ci_time:
            data["_clock_in"] = timezone.make_aware(datetime.combine(ci_date, ci_time))
        if co_date and co_time:
            data["_clock_out"] = timezone.make_aware(datetime.combine(co_date, co_time))
        elif co_date or co_time:
            self.add_error("clock_out_date", "Enter both clock-out date and time, or leave both empty for an open entry.")
        if data.get("_clock_in") and data.get("_clock_out"):
            if data["_clock_out"] <= data["_clock_in"]:
                self.add_error("clock_out_time", "Clock-out must be after clock-in.")
        return data


EmployeeScheduleFormSet = modelformset_factory(
    EmployeeSchedule,
    form=EmployeeScheduleSlotForm,
    extra=0,
    can_delete=False,
    max_num=7,
)

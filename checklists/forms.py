from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import ChecklistTemplate, ChecklistTemplateItem


class ChecklistTemplateForm(forms.ModelForm):
    class Meta:
        model = ChecklistTemplate
        fields = ["name", "description", "is_default"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Spring Cleanup Checklist"}),
            "description": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional description for your team"}),
        }


class ChecklistTemplateItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistTemplateItem
        fields = ["label", "section", "requires_photo", "sort_order"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Task name"}),
            "section": forms.TextInput(attrs={"placeholder": "Section (e.g. Cleanup)"}),
            "sort_order": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["label"].required = False
        self.fields["section"].required = False


class BaseChecklistItemFormSet(BaseInlineFormSet):
    def save(self, commit=True):
        instances = []
        for form in self.forms:
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                if form.instance.pk:
                    form.instance.delete()
                continue
            # Skip new empty rows
            if not form.instance.pk:
                label = (form.cleaned_data.get("label") or "").strip()
                if not label:
                    continue
            instances.append(form.save(commit=True))
        return instances


ChecklistTemplateItemFormSet = inlineformset_factory(
    ChecklistTemplate,
    ChecklistTemplateItem,
    form=ChecklistTemplateItemForm,
    formset=BaseChecklistItemFormSet,
    extra=1,
    can_delete=True,
)

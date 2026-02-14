from django import forms
from .models import Crew


class CrewForm(forms.ModelForm):
    class Meta:
        model = Crew
        fields = ['name', 'crew_leader', 'members', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Green Team'}),
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            from accounts.models import User
            crew_users = User.objects.filter(business=business, role='crew').order_by('first_name', 'username')
            self.fields['crew_leader'].queryset = crew_users
            self.fields['members'].queryset = crew_users
            self.fields['members'].widget = forms.CheckboxSelectMultiple()
        # Ensure color defaults to valid hex if empty
        if self.instance and not self.instance.color:
            self.initial['color'] = '#3b82f6'
        elif not self.initial.get('color'):
            self.initial['color'] = '#3b82f6'

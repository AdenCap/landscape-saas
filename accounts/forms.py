from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from accounts.models import EmployeePayment
from businesses.models import Business

User = get_user_model()


class SignUpForm(UserCreationForm):
    """Public signup: create a business and an owner user. Email required for password reset."""
    business_name = forms.CharField(
        max_length=255,
        label="Business name",
        help_text="Your company or business name.",
    )
    business_subtype = forms.ChoiceField(
        required=False,
        label="Specialization",
        choices=[("", "— Select (optional) —")],
    )
    email = forms.EmailField(
        required=True,
        label="Email",
        help_text="Required. We use this to send you a link if you forget your password.",
    )

    class Meta:
        model = User
        fields = [
            "business_name",
            "business_subtype",
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        ]

    # Subtype choices per business type
    SUBTYPE_MAP = {
        "landscaping": [
            ("", "— Select (optional) —"),
            ("lawn_care", "Lawn Care Only"),
            ("full_service", "Full-Service Landscaping"),
        ],
        "hvac": [
            ("", "— Select (optional) —"),
            ("residential_hvac", "Residential HVAC"),
            ("commercial_hvac", "Commercial HVAC"),
            ("both_hvac", "Residential & Commercial"),
        ],
        "plumbing": [
            ("", "— Select (optional) —"),
            ("residential_plumbing", "Residential Plumbing"),
            ("commercial_plumbing", "Commercial Plumbing"),
            ("both_plumbing", "Residential & Commercial"),
        ],
        "electrical": [
            ("", "— Select (optional) —"),
            ("residential_electrical", "Residential Electrical"),
            ("commercial_electrical", "Commercial Electrical"),
            ("both_electrical", "Residential & Commercial"),
        ],
        "cleaning": [
            ("", "— Select (optional) —"),
            ("residential_cleaning", "Residential Cleaning"),
            ("commercial_cleaning", "Commercial Cleaning"),
            ("both_cleaning", "Residential & Commercial"),
        ],
        "general": [
            ("", "— Select (optional) —"),
            ("general", "General"),
        ],
    }

    def __init__(self, *args, business_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._business_type = business_type or "landscaping"
        choices = self.SUBTYPE_MAP.get(self._business_type, self.SUBTYPE_MAP["general"])
        self.fields["business_subtype"].choices = choices


class SocialSignupCompleteForm(forms.Form):
    """Collects business details for users who signed up via social auth."""
    business_name = forms.CharField(
        max_length=255,
        label="Business name",
        help_text="Your company or business name.",
    )
    business_type = forms.ChoiceField(
        choices=Business.BUSINESS_TYPE_CHOICES,
        label="Business type",
    )


class EmployeeForm(forms.ModelForm):
    """Form for editing employee profile (name, contact, address, role, pay)."""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'role', 'hourly_rate', 'color', 'is_active',
        ]
        widgets = {
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class EmployeeCreateForm(UserCreationForm):
    """Form for creating a new employee with login credentials."""
    class Meta:
        model = User
        fields = [
            'username', 'password1', 'password2',
            'first_name', 'last_name', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'role', 'hourly_rate',
        ]
        widgets = {
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class EmployeePasswordForm(forms.Form):
    """Form for owner to set/reset employee password.
    Runs the new password through Django's AUTH_PASSWORD_VALIDATORS
    (Argon2, min 10 chars, common password check, numeric check).
    """
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user  # Optional: pass the target user for similarity checks

    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        if password:
            from django.contrib.auth.password_validation import validate_password
            validate_password(password, user=self._user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password1')
        p2 = cleaned_data.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match.")
        return cleaned_data


class EmployeePaymentForm(forms.ModelForm):
    """Form to record a payment made to an employee."""
    class Meta:
        model = EmployeePayment
        fields = ['amount', 'payment_type', 'paid_date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'payment_type': forms.Select(),
            'paid_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes (e.g. pay period)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'paid_date' in self.fields:
            self.fields['paid_date'].initial = timezone.localdate()


class SendNotificationForm(forms.Form):
    """Owner sends a notification to selected employees and/or crews (multi-select)."""
    send_to_all = forms.BooleanField(
        required=False,
        label="All employees",
        help_text="Send to everyone in your business (overrides individual selections below).",
    )
    employees = forms.MultipleChoiceField(
        required=False,
        label="Employees",
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more employees.",
    )
    crews = forms.MultipleChoiceField(
        required=False,
        label="Crews",
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more crews (every member receives the notification).",
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Type your message…"}),
        max_length=2000,
    )

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business:
            emp_list = User.objects.filter(business=business).order_by("first_name", "last_name", "username")
            self.fields["employees"].choices = [(str(u.id), u.get_full_name() or u.username) for u in emp_list]
            from jobs.models import Crew
            crew_list = Crew.objects.filter(business=business).order_by("name")
            self.fields["crews"].choices = [(str(c.id), c.name) for c in crew_list]

    def clean(self):
        cleaned_data = super().clean()
        send_to_all = cleaned_data.get("send_to_all")
        employees = cleaned_data.get("employees") or []
        crews = cleaned_data.get("crews") or []
        if not send_to_all and not employees and not crews:
            raise forms.ValidationError("Select at least one option: All employees, specific employees, and/or crews.")
        return cleaned_data

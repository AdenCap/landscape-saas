import csv
import io
from django import forms
from .models import Customer, Property, Contract, ClientMessage


# CSV column header -> Customer model field (flexible names)
CSV_FIELD_MAP = {
    "name": "name",
    "client": "name",
    "client_name": "name",
    "customer": "name",
    "customer_name": "name",
    "full_name": "name",
    "contact_name": "name",
    "phone": "phone",
    "phone_number": "phone",
    "mobile": "phone",
    "cell": "phone",
    "alt_phone": "alt_phone",
    "alternate_phone": "alt_phone",
    "secondary_phone": "alt_phone",
    "email": "email",
    "email_address": "email",
    "address": "address_line1",
    "street": "address_line1",
    "street_address": "address_line1",
    "address_line1": "address_line1",
    "address1": "address_line1",
    "address_line2": "address_line2",
    "address2": "address_line2",
    "suite": "address_line2",
    "city": "city",
    "state": "state",
    "province": "state",
    "zip": "postal_code",
    "postal": "postal_code",
    "postal_code": "postal_code",
    "zipcode": "postal_code",
    "notes": "notes",
    "note": "notes",
}


def normalize_header(h):
    """Lowercase, strip, replace spaces with underscore."""
    return (h or "").strip().lower().replace(" ", "_")


def _clean_text(value):
    return (value or "").strip()


def _coalesce(*values):
    for v in values:
        v = _clean_text(v)
        if v:
            return v
    return ""


def parse_csv_customers(stream, business):
    """
    Parse CSV stream; first row = headers. Yield (customer, error) for each row.
    customer is a Customer instance (not saved) or None; error is a string or None.
    """
    reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", errors="replace"))
    for i, row in enumerate(reader):
        row_num = i + 2  # 1-based, +1 for header
        # Map headers to model fields
        data = {}
        normalized_row = {}
        for raw_key, value in row.items():
            key = normalize_header(raw_key)
            normalized_row[key] = _clean_text(value)
            if key in CSV_FIELD_MAP:
                field = CSV_FIELD_MAP[key]
                data[field] = _clean_text(value)

        raw_first = _clean_text(normalized_row.get("first_name"))
        raw_last = _clean_text(normalized_row.get("last_name"))
        if raw_first or raw_last:
            composed_name = (raw_first + " " + raw_last).strip()
            if composed_name and not data.get("name"):
                data["name"] = composed_name

        # Smart fallback for address if split fields are missing
        if not data.get("address_line1"):
            data["address_line1"] = _coalesce(normalized_row.get("address"), normalized_row.get("street"), normalized_row.get("street_address"))
        if not data.get("city"):
            data["city"] = _coalesce(normalized_row.get("town"), normalized_row.get("locality"))
        if not data.get("state"):
            data["state"] = _coalesce(normalized_row.get("province"), normalized_row.get("region"))
        if not data.get("postal_code"):
            data["postal_code"] = _coalesce(normalized_row.get("zip"), normalized_row.get("zipcode"), normalized_row.get("postal"), normalized_row.get("postal_code"))

        name = _clean_text(data.get("name"))
        if not name:
            yield None, f"Row {row_num}: missing name (skipped)"
            continue

        customer = Customer(
            business=business,
            name=name[:255],
            phone=_coalesce(data.get("phone"), normalized_row.get("mobile"), normalized_row.get("cell"))[:20],
            alt_phone=_coalesce(data.get("alt_phone"), normalized_row.get("secondary_phone"))[:20],
            email=_clean_text(data.get("email"))[:254],
            address_line1=_clean_text(data.get("address_line1"))[:255],
            address_line2=_clean_text(data.get("address_line2"))[:255],
            city=_clean_text(data.get("city"))[:100],
            state=_clean_text(data.get("state"))[:50],
            postal_code=_clean_text(data.get("postal_code"))[:20],
            notes=_clean_text(data.get("notes")),
        )
        # EmailField doesn't allow arbitrary strings; leave blank if invalid
        if customer.email and "@" not in customer.email:
            customer.email = ""
        yield customer, None


class CustomerImportForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file",
        help_text="Upload a CSV with columns: name, phone, email, address, city, state, zip, notes (first row = headers)",
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Update existing clients if duplicates are found",
        help_text="If checked, duplicate matches by email/phone/name+address will be updated instead of skipped.",
    )

    def clean_csv_file(self):
        data = self.cleaned_data["csv_file"]
        if not data.name.lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a .csv file.")
        if data.size > 5 * 1024 * 1024:
            raise forms.ValidationError("File must be under 5 MB.")
        return data


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'phone', 'alt_phone', 'email',
            'communication_preference',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'invoice_frequency',
            'monthly_invoice_send_day',
            'invoice_due_days',
            'notes',
        ]
        widgets = {
            'communication_preference': forms.Select(attrs={'class': 'form-select'}),
            'invoice_frequency': forms.Select(attrs={'class': 'form-select'}),
            'monthly_invoice_send_day': forms.NumberInput(attrs={'min': 1, 'max': 28, 'placeholder': 'e.g. 1 or 15'}),
            'invoice_due_days': forms.NumberInput(attrs={'min': 0, 'max': 365, 'placeholder': 'e.g. 15 or 30'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Internal notes about this client...'}),
        }

    def clean_monthly_invoice_send_day(self):
        val = self.cleaned_data.get('monthly_invoice_send_day')
        if val is not None and (val < 1 or val > 28):
            from django import forms as f
            raise f.ValidationError("Must be between 1 and 28.")
        return val

    def clean_invoice_due_days(self):
        val = self.cleaned_data.get('invoice_due_days')
        if val is not None and (val < 0 or val > 365):
            from django import forms as f
            raise f.ValidationError("Must be between 0 and 365.")
        return val


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['address', 'notes', 'gate_code', 'has_dog', 'fertilization_services_per_year']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'fertilization_services_per_year': forms.NumberInput(attrs={'min': 1, 'max': 12, 'placeholder': 'e.g. 4'}),
        }
        help_texts = {
            'fertilization_services_per_year': 'For fertilization programs: number of applications per year. Enables smart scheduling with other fertilization clients.',
        }


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ['contract_type', 'status', 'start_date', 'end_date', 'amount', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class SendMessageForm(forms.Form):
    """Form to send an email or SMS to a client from their profile."""
    channel = forms.ChoiceField(
        choices=[("email", "Email"), ("sms", "Text (SMS)")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    subject = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Subject (email only)"}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Your message..."}),
        required=True,
    )

    def clean(self):
        data = super().clean()
        channel = data.get("channel")
        if channel == "email" and not data.get("subject"):
            # Allow blank subject; we could require it for email
            pass
        return data

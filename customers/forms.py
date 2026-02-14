import csv
import io
from django import forms
from .models import Customer, Property, Contract


# CSV column header -> Customer model field (flexible names)
CSV_FIELD_MAP = {
    "name": "name",
    "phone": "phone",
    "alt_phone": "alt_phone",
    "alternate_phone": "alt_phone",
    "email": "email",
    "address": "address_line1",
    "address_line1": "address_line1",
    "address1": "address_line1",
    "address_line2": "address_line2",
    "address2": "address_line2",
    "city": "city",
    "state": "state",
    "zip": "postal_code",
    "postal_code": "postal_code",
    "zipcode": "postal_code",
    "notes": "notes",
}


def normalize_header(h):
    """Lowercase, strip, replace spaces with underscore."""
    return (h or "").strip().lower().replace(" ", "_")


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
        for raw_key, value in row.items():
            key = normalize_header(raw_key)
            if key in CSV_FIELD_MAP:
                field = CSV_FIELD_MAP[key]
                data[field] = (value or "").strip() if value is not None else ""

        name = (data.get("name") or "").strip()
        if not name:
            yield None, f"Row {row_num}: missing name (skipped)"
            continue

        customer = Customer(
            business=business,
            name=name[:255],
            phone=(data.get("phone") or "")[:20],
            alt_phone=(data.get("alt_phone") or "")[:20],
            email=(data.get("email") or "")[:254],
            address_line1=(data.get("address_line1") or "")[:255],
            address_line2=(data.get("address_line2") or "")[:255],
            city=(data.get("city") or "")[:100],
            state=(data.get("state") or "")[:50],
            postal_code=(data.get("postal_code") or "")[:20],
            notes=(data.get("notes") or "")[:],
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
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'invoice_frequency',
            'monthly_invoice_send_day',
            'notes',
        ]
        widgets = {
            'invoice_frequency': forms.Select(attrs={'class': 'form-select'}),
            'monthly_invoice_send_day': forms.NumberInput(attrs={'min': 1, 'max': 28, 'placeholder': 'e.g. 1 or 15'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Internal notes about this client...'}),
        }

    def clean_monthly_invoice_send_day(self):
        val = self.cleaned_data.get('monthly_invoice_send_day')
        if val is not None and (val < 1 or val > 28):
            from django import forms as f
            raise f.ValidationError("Must be between 1 and 28.")
        return val


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['address', 'notes', 'gate_code', 'has_dog']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
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

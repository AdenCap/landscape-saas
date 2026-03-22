from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from decimal import Decimal, ROUND_CEILING

from .models import Estimate, EstimateLineItem, EstimateImage, Invoice, InvoiceLineItem, DocumentTemplate
from customers.models import Customer, Property


class FieldCaptureForm(forms.ModelForm):
    """Quick mobile form for capturing estimate info during a site visit."""
    class Meta:
        model = Estimate
        fields = ['customer', 'property', 'title', 'site_visit_date', 'site_visit_notes']
        widgets = {
            'site_visit_date': forms.DateInput(attrs={'type': 'date'}),
            'site_visit_notes': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Measurements, conditions, access notes, special requirements...',
            }),
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. Spring cleanup, Mulch install, Lawn treatment',
            }),
        }
        labels = {
            'site_visit_date': 'Visit Date',
            'site_visit_notes': 'Site Notes',
            'title': 'Job Description',
            'property': 'Property',
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields['customer'].queryset = Customer.objects.filter(business=business).order_by('name')
        self.fields['property'].required = False
        self.fields['property'].empty_label = '-- Select property --'
        if self.data.get('customer'):
            try:
                self.fields['property'].queryset = Property.objects.filter(customer_id=int(self.data['customer']))
            except (ValueError, TypeError):
                self.fields['property'].queryset = Property.objects.none()
        elif self.initial.get('customer'):
            cid = self.initial['customer']
            if hasattr(cid, 'pk'):
                cid = cid.pk
            self.fields['property'].queryset = Property.objects.filter(customer_id=cid)
        else:
            self.fields['property'].queryset = Property.objects.none()


class EstimateForm(forms.ModelForm):
    class Meta:
        model = Estimate
        fields = ['customer', 'property', 'title', 'valid_until', 'notes', 'site_visit_date', 'site_visit_notes',
                  'deposit_required', 'deposit_type', 'deposit_amount']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'site_visit_date': forms.DateInput(attrs={'type': 'date'}),
            'site_visit_notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Measurements, conditions, access notes, special requirements...'}),
            'deposit_amount': forms.NumberInput(attrs={'placeholder': 'e.g. 500 or 50', 'step': '0.01', 'min': '0'}),
        }
        labels = {
            'site_visit_date': 'Site Visit Date',
            'site_visit_notes': 'Site Visit Notes',
            'property': 'Property',
            'deposit_required': 'Require deposit to accept',
            'deposit_type': 'Deposit type',
            'deposit_amount': 'Deposit amount',
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields['customer'].queryset = Customer.objects.filter(business=business).order_by('name')
        self.fields['property'].required = False
        self.fields['property'].empty_label = '-- Select property --'
        if self.instance and self.instance.pk and self.instance.customer_id:
            self.fields['property'].queryset = Property.objects.filter(customer=self.instance.customer)
        elif self.data.get('customer'):
            try:
                self.fields['property'].queryset = Property.objects.filter(customer_id=int(self.data['customer']))
            except (ValueError, TypeError):
                self.fields['property'].queryset = Property.objects.none()
        elif self.initial.get('customer'):
            cid = self.initial['customer']
            if hasattr(cid, 'pk'):
                cid = cid.pk
            self.fields['property'].queryset = Property.objects.filter(customer_id=cid)
        else:
            self.fields['property'].queryset = Property.objects.none()


class InvoiceLineItemForm(forms.ModelForm):
    """Owner edit of draft invoice line items: description, quantity, unit_price, material_cost, labor_cost."""
    class Meta:
        model = InvoiceLineItem
        fields = ["description", "quantity", "unit_price", "material_cost", "labor_cost"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Description", "class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"min": 1, "step": 1, "class": "form-control"}),
            "unit_price": forms.NumberInput(attrs={"min": 0, "step": "0.01", "class": "form-control"}),
            "material_cost": forms.NumberInput(attrs={"min": 0, "step": "0.01", "class": "form-control"}),
            "labor_cost": forms.NumberInput(attrs={"min": 0, "step": "0.01", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow empty rows in formset; view will only save rows with description
        self.fields["description"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_price"].required = False


InvoiceLineItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceLineItem,
    form=InvoiceLineItemForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


def _fmt_qty(d):
    """Format quantity for display: whole number if integer, else 1 decimal."""
    if d % 1 == 0:
        return str(int(d))
    return f"{float(d):.1f}".rstrip('0').rstrip('.')


def _compute_fertilizing(config):
    """Returns (description, material_cost). Bags/pounds computed from inputs."""
    if not config:
        return None, Decimal('0')
    rate = Decimal(str(config.get('lbs_per_1000') or 0))
    sqft = Decimal(str(config.get('total_sqft') or 0))
    product = str(config.get('product') or 'Fertilizer').strip() or 'Fertilizer'
    total_pounds = (rate / 1000) * sqft
    pricing = config.get('pricing_type') or 'per_pound'
    if pricing == 'per_bag':
        cost_bag = Decimal(str(config.get('cost_per_bag') or 0))
        lbs_bag = Decimal(str(config.get('lbs_per_bag') or 1)) or Decimal('1')
        if lbs_bag <= 0:
            return None, Decimal('0')
        bags = (total_pounds / lbs_bag).quantize(Decimal('1'), rounding=ROUND_CEILING)
        cost = bags * cost_bag
        desc = f"{int(bags)} bag{'s' if bags != 1 else ''} of {product} ({sqft:,.0f} sq ft)"
    else:
        cost_per_lb = Decimal(str(config.get('cost_per_pound') or 0))
        cost = total_pounds * cost_per_lb
        desc = f"{_fmt_qty(total_pounds)} lbs of {product} ({sqft:,.0f} sq ft)"
    return desc, cost


def _compute_mulch(config):
    """Cubic yards = (sqft * depth_inches) / 324. Bags or cubic yards pricing."""
    if not config:
        return None, Decimal('0')
    sqft = Decimal(str(config.get('total_sqft') or 0))
    depth = Decimal(str(config.get('depth_inches') or 3))
    product = str(config.get('product') or 'Mulch').strip() or 'Mulch'
    cubic_yards = (sqft * depth) / Decimal('324')
    yd_str = _fmt_qty(cubic_yards)
    desc = f"{yd_str} cubic yard{'s' if float(cubic_yards) != 1 else ''} of {product}"
    pricing = config.get('pricing_type') or 'per_bag'
    if pricing == 'per_bag':
        cost_bag = Decimal(str(config.get('cost_per_bag') or 0))
        cf_per_bag = Decimal(str(config.get('cf_per_bag') or 2))
        if cf_per_bag <= 0:
            return None, Decimal('0')
        cubic_ft = cubic_yards * 27
        bags = (cubic_ft / cf_per_bag).quantize(Decimal('1'), rounding=ROUND_CEILING)
        cost = bags * cost_bag
    else:
        cost_cy = Decimal(str(config.get('cost_per_cy') or 0))
        cost = cubic_yards * cost_cy
    return desc, cost


def _compute_mowing(config):
    """Material cost = cost_per_cut * number_of_cuts."""
    if not config:
        return None, Decimal('0')
    sqft = Decimal(str(config.get('total_sqft') or 0))
    cuts = Decimal(str(config.get('num_cuts') or 1))
    rate = Decimal(str(config.get('cost_per_cut') or 0))
    product = str(config.get('product') or 'Lawn Mowing').strip() or 'Lawn Mowing'
    cost = cuts * rate
    cut_str = _fmt_qty(cuts)
    desc = f"{cut_str} cut{'s' if float(cuts) != 1 else ''} of {product} ({sqft:,.0f} sq ft)"
    return desc, cost


class EstimateLineItemForm(forms.ModelForm):
    item_type = forms.ChoiceField(
        choices=[
            ('standard', 'Standard'),
            ('fertilizing', 'Fertilizing'),
            ('mulch', 'Mulch'),
            ('mowing', 'Mowing'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'item-type-select'})
    )
    # Fertilizing
    fertilizing_lbs_per_1000 = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=3, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 1 or 0.75'}))
    fertilizing_total_sqft = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 10000 or 5250.5'}))
    fertilizing_product = forms.CharField(required=False, max_length=200, widget=forms.TextInput(attrs={'placeholder': 'e.g. Scotts Turf Builder'}))
    fertilizing_pricing_type = forms.ChoiceField(required=False, choices=[('per_pound', 'Per pound'), ('per_bag', 'Per bag')], widget=forms.Select(attrs={'class': 'fertilizing-pricing-type'}))
    fertilizing_cost_per_pound = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 0.50'}))
    fertilizing_cost_per_bag = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 45'}))
    fertilizing_lbs_per_bag = forms.DecimalField(required=False, min_value=0.1, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 50 or 22.5'}))

    # Mulch
    mulch_total_sqft = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 500 or 325.5'}))
    mulch_depth_inches = forms.DecimalField(required=False, min_value=0.25, max_digits=4, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 3 or 2.5'}))
    mulch_product = forms.CharField(required=False, max_length=200, widget=forms.TextInput(attrs={'placeholder': 'e.g. Brown Mulch'}))
    mulch_pricing_type = forms.ChoiceField(required=False, choices=[('per_bag', 'Per bag'), ('per_cy', 'Per cubic yard')], widget=forms.Select(attrs={'class': 'mulch-pricing-type'}))
    mulch_cost_per_bag = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 4.50'}))
    mulch_cf_per_bag = forms.DecimalField(required=False, min_value=0.1, max_digits=5, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 2 or 1.5'}))
    mulch_cost_per_cy = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 35'}))

    # Mowing
    mowing_total_sqft = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 5000 or 4125.25'}))
    mowing_num_cuts = forms.DecimalField(required=False, min_value=0.25, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 4 or 2.5'}))
    mowing_cost_per_cut = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 35'}))
    mowing_product = forms.CharField(required=False, max_length=200, widget=forms.TextInput(attrs={'placeholder': 'e.g. Lawn Mowing'}))

    class Meta:
        model = EstimateLineItem
        fields = ['item_type', 'fertilizing_config', 'mulch_config', 'mowing_config', 'description', 'quantity', 'material_cost', 'labor_cost', 'total_override', 'is_addon', 'order']
        widgets = {
            'order': forms.HiddenInput(),
            'fertilizing_config': forms.HiddenInput(),
            'mulch_config': forms.HiddenInput(),
            'mowing_config': forms.HiddenInput(),
            'description': forms.TextInput(attrs={'placeholder': 'Description'}),
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': ''}),
            'material_cost': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': ''}),
            'labor_cost': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': ''}),
            'total_override': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': 'Auto', 'class': 'total-override-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: don't require fields so one line can be filled at a time
        self.fields['description'].required = False
        self.fields['quantity'].required = False
        self.fields['material_cost'].required = False
        self.fields['labor_cost'].required = False
        self.fields['total_override'].required = False
        # Show blank instead of 0 for number fields
        if not self.instance.pk:
            self.initial['quantity'] = None
            self.initial['material_cost'] = None
            self.initial['labor_cost'] = None
            self.initial['total_override'] = None
        else:
            if self.instance.quantity == 0:
                self.initial['quantity'] = None
            if self.instance.material_cost == 0:
                self.initial['material_cost'] = None
            if self.instance.labor_cost == 0:
                self.initial['labor_cost'] = None
            if self.instance.total_override is None:
                self.initial['total_override'] = None
        if self.instance and self.instance.fertilizing_config:
            c = self.instance.fertilizing_config
            self.fields['fertilizing_lbs_per_1000'].initial = c.get('lbs_per_1000')
            self.fields['fertilizing_total_sqft'].initial = c.get('total_sqft')
            self.fields['fertilizing_product'].initial = c.get('product')
            self.fields['fertilizing_pricing_type'].initial = c.get('pricing_type', 'per_pound')
            self.fields['fertilizing_cost_per_pound'].initial = c.get('cost_per_pound')
            self.fields['fertilizing_cost_per_bag'].initial = c.get('cost_per_bag')
            self.fields['fertilizing_lbs_per_bag'].initial = c.get('lbs_per_bag')
        if self.instance and self.instance.mulch_config:
            c = self.instance.mulch_config
            self.fields['mulch_total_sqft'].initial = c.get('total_sqft')
            self.fields['mulch_depth_inches'].initial = c.get('depth_inches', 3)
            self.fields['mulch_product'].initial = c.get('product')
            self.fields['mulch_pricing_type'].initial = c.get('pricing_type', 'per_bag')
            self.fields['mulch_cost_per_bag'].initial = c.get('cost_per_bag')
            self.fields['mulch_cf_per_bag'].initial = c.get('cf_per_bag', 2)
            self.fields['mulch_cost_per_cy'].initial = c.get('cost_per_cy')
        if self.instance and self.instance.mowing_config:
            c = self.instance.mowing_config
            self.fields['mowing_total_sqft'].initial = c.get('total_sqft')
            self.fields['mowing_num_cuts'].initial = c.get('num_cuts', 4)
            self.fields['mowing_cost_per_cut'].initial = c.get('cost_per_cut')
            self.fields['mowing_product'].initial = c.get('product')
        if self.instance and self.instance.item_type:
            self.fields['item_type'].initial = self.instance.item_type

    def clean(self):
        data = super().clean()
        item_type = data.get('item_type', 'standard')
        if item_type == 'fertilizing':
            cfg = {
                'lbs_per_1000': data.get('fertilizing_lbs_per_1000'),
                'total_sqft': data.get('fertilizing_total_sqft'),
                'product': data.get('fertilizing_product'),
                'pricing_type': data.get('fertilizing_pricing_type') or 'per_pound',
                'cost_per_pound': data.get('fertilizing_cost_per_pound'),
                'cost_per_bag': data.get('fertilizing_cost_per_bag'),
                'lbs_per_bag': data.get('fertilizing_lbs_per_bag'),
            }
            data['fertilizing_config'] = cfg
            desc, cost = _compute_fertilizing(cfg)
            if desc:
                data['description'] = desc
                data['material_cost'] = cost
                data['quantity'] = Decimal('1')
                data['unit'] = 'application'
        elif item_type == 'mulch':
            cfg = {
                'total_sqft': data.get('mulch_total_sqft'),
                'depth_inches': data.get('mulch_depth_inches') or 3,
                'product': data.get('mulch_product'),
                'pricing_type': data.get('mulch_pricing_type') or 'per_bag',
                'cost_per_bag': data.get('mulch_cost_per_bag'),
                'cf_per_bag': data.get('mulch_cf_per_bag') or 2,
                'cost_per_cy': data.get('mulch_cost_per_cy'),
            }
            data['mulch_config'] = cfg
            desc, cost = _compute_mulch(cfg)
            if desc:
                data['description'] = desc
                data['material_cost'] = cost
                data['quantity'] = Decimal('1')
                data['unit'] = 'application'
            data['fertilizing_config'] = None
        elif item_type == 'mowing':
            cfg = {
                'total_sqft': data.get('mowing_total_sqft'),
                'num_cuts': data.get('mowing_num_cuts') or 1,
                'cost_per_cut': data.get('mowing_cost_per_cut'),
                'product': data.get('mowing_product'),
            }
            data['mowing_config'] = cfg
            desc, cost = _compute_mowing(cfg)
            if desc:
                data['description'] = desc
                data['material_cost'] = cost
                data['quantity'] = data.get('mowing_num_cuts') or Decimal('1')
                data['unit'] = 'cuts'
            data['fertilizing_config'] = None
            data['mulch_config'] = None
        else:
            data['fertilizing_config'] = None
            data['mulch_config'] = None
            data['mowing_config'] = None
        # Default empty fields so model can save (formset still skips fully empty new rows)
        if data.get('quantity') is None or data.get('quantity') == '':
            data['quantity'] = Decimal('1')
        if data.get('material_cost') is None or data.get('material_cost') == '':
            data['material_cost'] = Decimal('0')
        if data.get('labor_cost') is None or data.get('labor_cost') == '':
            data['labor_cost'] = Decimal('0')
        if data.get('total_override') is None or data.get('total_override') == '':
            data['total_override'] = None
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.item_type = self.cleaned_data.get('item_type', 'standard')
        obj.fertilizing_config = self.cleaned_data.get('fertilizing_config')
        obj.mulch_config = self.cleaned_data.get('mulch_config')
        obj.mowing_config = self.cleaned_data.get('mowing_config')
        if not (obj.description or '').strip():
            obj.description = 'Line item'
        if commit:
            obj.save()
        return obj


class BaseEstimateLineItemFormSet(BaseInlineFormSet):
    """Only save new line items that have real data; skip empty rows."""

    def save(self, commit=True):
        """Save only non-empty new forms. Existing forms are saved as usual (including delete)."""
        if not commit:
            return super().save(commit=False)
        instances = []
        for form in self.forms:
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get('DELETE'):
                if form.instance.pk:
                    form.instance.delete()
                continue
            # Skip new (no pk) forms that are completely empty
            if not form.instance.pk:
                desc = (form.cleaned_data.get('description') or '').strip()
                mat = form.cleaned_data.get('material_cost')
                labor = form.cleaned_data.get('labor_cost')
                total_ov = form.cleaned_data.get('total_override')
                if mat is None:
                    mat = Decimal('0')
                if labor is None:
                    labor = Decimal('0')
                if total_ov is None or total_ov == Decimal('0'):
                    total_ov = None
                if not desc and mat == Decimal('0') and labor == Decimal('0') and total_ov is None:
                    continue
            instances.append(form.save(commit=True))
        return instances


EstimateLineItemFormSet = inlineformset_factory(
    Estimate,
    EstimateLineItem,
    form=EstimateLineItemForm,
    formset=BaseEstimateLineItemFormSet,
    extra=1,
    can_delete=True,
)


class EstimateImageForm(forms.ModelForm):
    class Meta:
        model = EstimateImage
        fields = ['image', 'caption', 'order']


class DocumentTemplateForm(forms.ModelForm):
    """Form for customizing estimate or invoice template: style, colors, header, footer, terms."""
    template_key = forms.ChoiceField(
        choices=[
            ("professional", "Professional"),
            ("minimal", "Minimal"),
            ("modern", "Modern"),
        ],
        required=False,
        help_text="Base style for the document. You can still customize colors and text below.",
    )

    class Meta:
        model = DocumentTemplate
        fields = ["template_key", "name", "primary_color", "header_text", "footer_text", "terms_and_conditions"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. My Estimate Template"}),
            "primary_color": forms.TextInput(attrs={"type": "color", "style": "height: 40px; width: 80px; padding: 2px; cursor: pointer;"}),
            "header_text": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional header (e.g. tagline, license number)"}),
            "footer_text": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional footer (e.g. thank you, payment terms)"}),
            "terms_and_conditions": forms.Textarea(attrs={"rows": 5, "placeholder": "Terms and conditions shown on the document"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template_key"].required = False
        self.fields["name"].required = False

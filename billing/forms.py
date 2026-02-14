from django import forms
from decimal import Decimal, ROUND_CEILING

from .models import Estimate, EstimateLineItem, EstimateImage
from customers.models import Customer


class EstimateForm(forms.ModelForm):
    class Meta:
        model = Estimate
        fields = ['customer', 'title', 'valid_until', 'notes']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields['customer'].queryset = Customer.objects.filter(business=business).order_by('name')


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
    else:
        cost_per_lb = Decimal(str(config.get('cost_per_pound') or 0))
        cost = total_pounds * cost_per_lb
    desc = f"Fertilizing — {product} ({sqft:,.2f} sq ft)"
    return desc, cost


def _compute_mulch(config):
    """Cubic yards = (sqft * depth_inches) / 324. Bags or cubic yards pricing."""
    if not config:
        return None, Decimal('0')
    sqft = Decimal(str(config.get('total_sqft') or 0))
    depth = Decimal(str(config.get('depth_inches') or 3))
    product = str(config.get('product') or 'Mulch').strip() or 'Mulch'
    cubic_yards = (sqft * depth) / Decimal('324')
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
    desc = f"Mulch — {product} ({sqft:,.2f} sq ft, {depth}\" depth)"
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
    desc = f"Mowing — {product} ({sqft:,.2f} sq ft, {cuts:g} cuts)"
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
        fields = ['item_type', 'fertilizing_config', 'mulch_config', 'mowing_config', 'description', 'quantity', 'unit', 'material_cost', 'labor_cost', 'is_addon', 'order']
        widgets = {
            'fertilizing_config': forms.HiddenInput(),
            'mulch_config': forms.HiddenInput(),
            'mowing_config': forms.HiddenInput(),
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': 'Qty'}),
            'material_cost': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'labor_cost': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.item_type = self.cleaned_data.get('item_type', 'standard')
        obj.fertilizing_config = self.cleaned_data.get('fertilizing_config')
        obj.mulch_config = self.cleaned_data.get('mulch_config')
        obj.mowing_config = self.cleaned_data.get('mowing_config')
        if commit:
            obj.save()
        return obj


class EstimateImageForm(forms.ModelForm):
    class Meta:
        model = EstimateImage
        fields = ['image', 'caption', 'order']

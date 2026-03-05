# Fertilization Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fertilization management hub where landscape business owners define annual programs, auto-calculate pricing from square footage + products + markup, manage customer enrollments, record applications, and generate compliance reports.

**Architecture:** New `fertilization` Django app with server-rendered tabbed hub at `/fertilization/`. Enhances existing `billing.FertilizerProduct` and `billing.FertilizerApplication` models with new fields. AJAX modals for all CRUD operations — same pattern as the Employee Management hub. Auto-pricing engine calculates material costs and suggested prices from product rates × property square footage × markup.

**Tech Stack:** Django 5.2, Python 3.12, PostgreSQL, vanilla JavaScript (fetch + modals), server-rendered templates with `{% extends "base.html" %}`.

---

## Codebase Context for Implementers

### Existing models you'll interact with:
- `billing.FertilizerProduct` (billing/models.py:562-656) — product catalog with per-pound/per-bag pricing, `calculate_cost(pounds)`, `get_cost_per_pound_equivalent()`
- `billing.FertilizerApplication` (billing/models.py:663-779) — application records with property, product, pounds_used, square_feet, lbs_per_1000_sqft, material_cost, charge_amount, profit/margin calculations
- `customers.Property` (customers/models.py:164-192) — has `fertilization_services_per_year` but NO `lawn_square_feet` field yet
- `businesses.Business` (businesses/models.py:249-260) — has `growing_season_start_month`, `growing_season_end_month`
- `jobs.Job` (jobs/models.py:46-171) — scheduled work at a property
- `pricing.ServiceTemplate` (pricing/models.py:7-31) — service catalog with default_rate and default_unit

### Existing functions:
- `_fertilization_dates_for_year(year, n_services, start_month, end_month)` in jobs/views.py:1517-1533 — spreads N dates across the growing season

### Patterns to follow:
- **Hub with tabs:** See `dashboard/templates/dashboard/employee_management.html` — uses `<nav class="emp-mgmt-tabs">` with `<a class="emp-tab" data-tab="id">` links
- **Sidebar nav:** See `templates/base.html:567-631` — uses `<a href="/path/" class="btn btn-nav {% if '/path' in request.path %}active{% endif %}"><i data-lucide="icon" class="nav-icon"></i> Label</a>`
- **AJAX modals:** The app uses `fetch()` with CSRF token from a hidden form. POST → JSON response → page reload on success.
- **View auth decorator:** `@role_required("owner", "manager")` from `accounts.decorators`
- **Get business helper:** `get_business(request)` from `dashboard.views` (returns the business for the current user/session)
- **INSTALLED_APPS:** config/settings.py:80-104

### Admin pattern:
- FertilizerProduct and FertilizerApplication are NOT yet registered in billing/admin.py — they need to be added.

---

## Task 1: Create Fertilization Django App + New Models

**Files:**
- Create: `fertilization/__init__.py`
- Create: `fertilization/apps.py`
- Create: `fertilization/models.py`
- Create: `fertilization/admin.py`
- Modify: `config/settings.py:80-104` (add to INSTALLED_APPS)

**What to build:**

Create the `fertilization` Django app with 4 models:

1. **`FertilizationProgram`** — reusable annual program template
   - `business` FK to Business (CASCADE)
   - `name` CharField(200)
   - `description` TextField, blank
   - `grass_type` CharField choices: `cool_season`, `warm_season`, `both` (default: `both`)
   - `is_active` BooleanField, default True
   - `created_at` DateTimeField auto_now_add
   - `updated_at` DateTimeField auto_now
   - Meta: ordering = `['name']`, unique_together = `[['business', 'name']]`
   - `__str__` returns `f"{self.name}"`
   - Property `num_rounds` returns `self.rounds.count()`

2. **`ProgramRound`** — one round in a program template
   - `program` FK to FertilizationProgram (CASCADE, related_name='rounds')
   - `round_number` PositiveSmallIntegerField
   - `name` CharField(100) — e.g., "Early Spring Pre-Emergent"
   - `target_month_start` PositiveSmallIntegerField (1-12, validators)
   - `target_month_end` PositiveSmallIntegerField (1-12, validators)
   - `products` M2M to `billing.FertilizerProduct`, blank=True
   - `default_rate_override` DecimalField(6,2), null/blank — overrides product's default rate
   - `crew_instructions` TextField, blank
   - Meta: ordering = `['program', 'round_number']`, unique_together = `[['program', 'round_number']]`
   - `__str__` returns `f"R{self.round_number}: {self.name}"`

3. **`CustomerProgramEnrollment`** — assigns a program to a property for a year
   - `business` FK to Business (CASCADE)
   - `property` FK to `customers.Property` (CASCADE, related_name='program_enrollments')
   - `program` FK to FertilizationProgram (PROTECT, related_name='enrollments')
   - `year` PositiveSmallIntegerField
   - `status` CharField choices: `enrolled`, `in_progress`, `completed`, `cancelled` (default: `enrolled`)
   - `pricing_method` CharField choices: `per_application`, `annual_flat`, `per_sqft` (default: `per_application`)
   - `price_per_application` DecimalField(10,2), null/blank
   - `annual_price` DecimalField(10,2), null/blank
   - `price_per_sqft` DecimalField(6,4), null/blank
   - `base_fee` DecimalField(8,2), default=0 — stop/trip charge per visit
   - `markup_pct` DecimalField(5,2), default=40
   - `notes` TextField, blank
   - `created_at` DateTimeField auto_now_add
   - Meta: ordering = `['-year', 'property__address']`, unique_together = `[['property', 'program', 'year']]`
   - `__str__` returns `f"{self.property.address} — {self.program.name} ({self.year})"`
   - Property `rounds_completed` returns count of scheduled_rounds with status='completed'
   - Property `total_rounds` returns count of all scheduled_rounds

4. **`ScheduledRound`** — actual scheduled round for an enrolled customer
   - `enrollment` FK to CustomerProgramEnrollment (CASCADE, related_name='scheduled_rounds')
   - `round_template` FK to ProgramRound (SET_NULL, null/blank, related_name='scheduled_instances')
   - `round_number` PositiveSmallIntegerField — preserved if template deleted
   - `scheduled_date` DateField
   - `status` CharField choices: `pending`, `scheduled`, `completed`, `skipped` (default: `pending`)
   - `job` FK to `jobs.Job` (SET_NULL, null/blank, related_name='fertilization_rounds')
   - `application` FK to `billing.FertilizerApplication` (SET_NULL, null/blank, related_name='scheduled_round')
   - `price` DecimalField(10,2), default=0
   - `material_cost` DecimalField(10,2), default=0
   - `notes` TextField, blank
   - Meta: ordering = `['enrollment', 'round_number']`
   - `__str__` returns `f"Round {self.round_number} — {self.enrollment.property.address} ({self.scheduled_date})"`

**Admin registrations** in `fertilization/admin.py`:
- `ProgramRoundInline` (TabularInline) for FertilizationProgram
- `ScheduledRoundInline` (TabularInline) for CustomerProgramEnrollment
- `FertilizationProgramAdmin` with inlines, list_display, list_filter, search_fields
- `CustomerProgramEnrollmentAdmin` with inlines, list_display, list_filter, raw_id_fields
- `ScheduledRoundAdmin` with list_display, list_filter, raw_id_fields

**Add to INSTALLED_APPS** in config/settings.py after `'messaging'`:
```python
'fertilization',
```

**Run:**
```bash
python manage.py makemigrations fertilization
python manage.py migrate
python manage.py check --deploy 2>&1 | head -20
```

**Commit:**
```bash
git add fertilization/ config/settings.py
git commit -m "feat(fertilization): create app with program, round, enrollment, and scheduled round models"
```

---

## Task 2: Enhance Existing Models — New Fields

**Files:**
- Modify: `billing/models.py:562-656` (FertilizerProduct — add NPK, rate, EPA fields)
- Modify: `billing/models.py:663-779` (FertilizerApplication — add weather, applied_by fields)
- Modify: `customers/models.py:164-192` (Property — add lawn_square_feet)

**What to build:**

### FertilizerProduct — add after `notes` field (around line 624):

```python
# NPK Analysis
nitrogen_pct = models.DecimalField(
    max_digits=5, decimal_places=2, null=True, blank=True,
    help_text="Nitrogen percentage from product label (e.g., 32.00 for 32-0-4)"
)
phosphorus_pct = models.DecimalField(
    max_digits=5, decimal_places=2, null=True, blank=True,
    help_text="Phosphorus percentage from product label"
)
potassium_pct = models.DecimalField(
    max_digits=5, decimal_places=2, null=True, blank=True,
    help_text="Potassium percentage from product label"
)

# Application rate
application_rate = models.DecimalField(
    max_digits=6, decimal_places=2, null=True, blank=True,
    help_text="Recommended lbs per 1,000 sq ft"
)

# Product type
product_type = models.CharField(
    max_length=20,
    choices=[('granular', 'Granular'), ('liquid', 'Liquid')],
    default='granular',
    help_text="Affects unit display in calculators"
)

# EPA registration
epa_registration_number = models.CharField(
    max_length=50, blank=True,
    help_text="EPA registration number for compliance tracking"
)
```

Also add an `npk_display` property:
```python
@property
def npk_display(self):
    """Return NPK string like '32-0-4' or empty string."""
    if self.nitrogen_pct is not None:
        n = int(self.nitrogen_pct) if self.nitrogen_pct == int(self.nitrogen_pct) else self.nitrogen_pct
        p = int(self.phosphorus_pct) if self.phosphorus_pct and self.phosphorus_pct == int(self.phosphorus_pct) else (self.phosphorus_pct or 0)
        k = int(self.potassium_pct) if self.potassium_pct and self.potassium_pct == int(self.potassium_pct) else (self.potassium_pct or 0)
        return f"{n}-{p}-{k}"
    return ""
```

### FertilizerApplication — add after `notes` field (around line 754):

```python
# Weather at time of application
WEATHER_CHOICES = [
    ('clear', 'Clear'),
    ('partly_cloudy', 'Partly Cloudy'),
    ('cloudy', 'Cloudy'),
    ('overcast', 'Overcast'),
    ('light_rain', 'Light Rain'),
]

weather_temp_f = models.SmallIntegerField(
    null=True, blank=True,
    help_text="Temperature (°F) at time of application"
)
weather_wind_mph = models.DecimalField(
    max_digits=4, decimal_places=1, null=True, blank=True,
    help_text="Wind speed (mph) at time of application"
)
weather_conditions = models.CharField(
    max_length=20, choices=WEATHER_CHOICES, blank=True,
    help_text="Weather conditions at time of application"
)
applied_by = models.ForeignKey(
    "accounts.User",
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='fertilizer_applications_applied',
    help_text="Technician who applied the product"
)
```

### Property — add after `has_dog` field (around line 179):

```python
lawn_square_feet = models.PositiveIntegerField(
    null=True, blank=True,
    help_text="Total lawn area in square feet. Used for fertilization calculations and auto-pricing."
)
```

**Run:**
```bash
python manage.py makemigrations billing customers
python manage.py migrate
python manage.py check
```

**Commit:**
```bash
git add billing/ customers/
git commit -m "feat(fertilization): add NPK, application rate, weather, and lawn sqft fields to existing models"
```

---

## Task 3: Register FertilizerProduct & FertilizerApplication in Admin

**Files:**
- Modify: `billing/admin.py` (add registrations at end of file)

**What to build:**

Add to the end of `billing/admin.py`:

```python
from .models import FertilizerProduct, FertilizerApplication

@admin.register(FertilizerProduct)
class FertilizerProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'npk_display', 'product_type', 'application_rate',
                    'pricing_type', 'cost_per_pound', 'cost_per_bag', 'active')
    list_filter = ('business', 'active', 'pricing_type', 'product_type')
    search_fields = ('name', 'business__name', 'epa_registration_number')
    raw_id_fields = ('business',)


@admin.register(FertilizerApplication)
class FertilizerApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'property', 'product', 'application_date',
                    'pounds_used', 'material_cost', 'charge_amount', 'applied_by')
    list_filter = ('business', 'application_date', 'weather_conditions')
    search_fields = ('property__address', 'product__name')
    raw_id_fields = ('business', 'property', 'product', 'job', 'estimate', 'applied_by')
    ordering = ('-application_date',)
```

**Run:**
```bash
python manage.py check
```

**Commit:**
```bash
git add billing/admin.py
git commit -m "feat(fertilization): register FertilizerProduct and FertilizerApplication in admin"
```

---

## Task 4: Auto-Pricing Engine

**Files:**
- Create: `fertilization/pricing.py`

**What to build:**

A module with pure calculation functions. No database writes — just math.

```python
"""
Auto-pricing engine for fertilization programs.

All functions are pure calculators — they take data in and return numbers.
No database writes happen here.
"""
from decimal import Decimal


def calculate_lbs_needed(application_rate, square_feet):
    """Calculate pounds of product needed for a given area.

    Args:
        application_rate: lbs per 1,000 sqft (Decimal or float)
        square_feet: total area in sqft (int or Decimal)

    Returns:
        Decimal: total pounds needed
    """
    rate = Decimal(str(application_rate))
    sqft = Decimal(str(square_feet))
    return (rate * sqft / Decimal('1000')).quantize(Decimal('0.01'))


def calculate_bags_needed(lbs_needed, lbs_per_bag):
    """Calculate whole bags needed (rounds up).

    Args:
        lbs_needed: total pounds of product needed
        lbs_per_bag: pounds per bag

    Returns:
        int: number of bags (rounded up)
    """
    from decimal import ROUND_CEILING
    lbs = Decimal(str(lbs_needed))
    per_bag = Decimal(str(lbs_per_bag))
    if per_bag <= 0:
        return 0
    return int((lbs / per_bag).quantize(Decimal('1'), rounding=ROUND_CEILING))


def calculate_round_material_cost(products_with_rates, square_feet):
    """Calculate total material cost for one round.

    Args:
        products_with_rates: list of dicts with keys:
            - product: FertilizerProduct instance
            - rate_override: Decimal or None (overrides product.application_rate)
        square_feet: property lawn area

    Returns:
        dict with:
            - total_cost: Decimal
            - product_details: list of dicts per product with lbs_needed, cost
    """
    sqft = Decimal(str(square_feet)) if square_feet else Decimal('0')
    details = []
    total = Decimal('0')

    for item in products_with_rates:
        product = item['product']
        rate = item.get('rate_override') or product.application_rate
        if not rate or sqft <= 0:
            details.append({
                'product': product,
                'lbs_needed': Decimal('0'),
                'cost': Decimal('0'),
            })
            continue

        lbs_needed = calculate_lbs_needed(rate, sqft)
        cost = product.calculate_cost(lbs_needed)
        total += cost
        details.append({
            'product': product,
            'lbs_needed': lbs_needed,
            'cost': cost,
        })

    return {
        'total_cost': total,
        'product_details': details,
    }


def calculate_program_material_cost(program, square_feet):
    """Calculate total material cost for an entire program (all rounds).

    Args:
        program: FertilizationProgram instance (with rounds prefetched)
        square_feet: property lawn area

    Returns:
        dict with:
            - total_cost: Decimal
            - round_costs: list of dicts per round with round, cost, product_details
    """
    round_costs = []
    total = Decimal('0')

    for rnd in program.rounds.prefetch_related('products').all():
        products_with_rates = [
            {'product': p, 'rate_override': rnd.default_rate_override}
            for p in rnd.products.filter(active=True)
        ]
        result = calculate_round_material_cost(products_with_rates, square_feet)
        total += result['total_cost']
        round_costs.append({
            'round': rnd,
            'cost': result['total_cost'],
            'product_details': result['product_details'],
        })

    return {
        'total_cost': total,
        'round_costs': round_costs,
    }


def calculate_suggested_price(material_cost, markup_pct, base_fee=Decimal('0')):
    """Calculate suggested price from material cost + markup + base fee.

    Args:
        material_cost: Decimal total material cost
        markup_pct: Decimal markup percentage (e.g., 40 for 40%)
        base_fee: Decimal per-visit base/stop fee

    Returns:
        Decimal: suggested price
    """
    markup = Decimal(str(markup_pct))
    base = Decimal(str(base_fee))
    cost = Decimal(str(material_cost))
    return (cost * (Decimal('1') + markup / Decimal('100')) + base).quantize(Decimal('0.01'))


def calculate_enrollment_pricing(program, square_feet, markup_pct, base_fee=Decimal('0')):
    """Calculate full enrollment pricing breakdown.

    This is the main function called during enrollment. It returns everything
    needed to show the auto-pricing preview to the business owner.

    Args:
        program: FertilizationProgram instance
        square_feet: property lawn area (int)
        markup_pct: Decimal markup percentage
        base_fee: Decimal per-visit base fee

    Returns:
        dict with:
            - total_material_cost: Decimal
            - num_rounds: int
            - cost_per_round: Decimal (average)
            - suggested_per_application: Decimal
            - suggested_annual: Decimal
            - round_breakdown: list of dicts per round
    """
    program_cost = calculate_program_material_cost(program, square_feet)
    num_rounds = len(program_cost['round_costs'])
    total_material = program_cost['total_cost']

    cost_per_round = (total_material / num_rounds).quantize(Decimal('0.01')) if num_rounds > 0 else Decimal('0')

    suggested_annual = calculate_suggested_price(total_material, markup_pct, base_fee * num_rounds)
    suggested_per_app = (suggested_annual / num_rounds).quantize(Decimal('0.01')) if num_rounds > 0 else Decimal('0')

    round_breakdown = []
    for rc in program_cost['round_costs']:
        round_price = calculate_suggested_price(rc['cost'], markup_pct, base_fee)
        round_breakdown.append({
            'round': rc['round'],
            'material_cost': rc['cost'],
            'suggested_price': round_price,
            'product_details': rc['product_details'],
        })

    return {
        'total_material_cost': total_material,
        'num_rounds': num_rounds,
        'cost_per_round': cost_per_round,
        'suggested_per_application': suggested_per_app,
        'suggested_annual': suggested_annual,
        'round_breakdown': round_breakdown,
    }
```

**Verify:**
```bash
python -c "from fertilization.pricing import calculate_lbs_needed; print(calculate_lbs_needed(3.5, 10000))"
# Should print: 35.00
```

**Commit:**
```bash
git add fertilization/pricing.py
git commit -m "feat(fertilization): add auto-pricing engine with material cost and markup calculations"
```

---

## Task 5: URL Routing + Hub View Skeleton

**Files:**
- Create: `fertilization/urls.py`
- Create: `fertilization/views.py`
- Modify: `config/urls.py` (add include)

**What to build:**

### `fertilization/urls.py`:

```python
from django.urls import path
from . import views

app_name = "fertilization"

urlpatterns = [
    # Main hub page
    path("", views.hub, name="hub"),

    # Programs CRUD (AJAX)
    path("api/programs/", views.program_list_create, name="program_list_create"),
    path("api/programs/<int:pk>/", views.program_detail, name="program_detail"),
    path("api/programs/<int:pk>/delete/", views.program_delete, name="program_delete"),
    path("api/programs/<int:pk>/duplicate/", views.program_duplicate, name="program_duplicate"),

    # Rounds CRUD (AJAX)
    path("api/rounds/<int:program_id>/", views.round_list_create, name="round_list_create"),
    path("api/rounds/<int:program_id>/<int:pk>/", views.round_update_delete, name="round_update_delete"),

    # Products CRUD (AJAX)
    path("api/products/", views.product_list_create, name="product_list_create"),
    path("api/products/<int:pk>/", views.product_detail, name="product_detail"),

    # Enrollment CRUD (AJAX)
    path("api/enrollments/", views.enrollment_list_create, name="enrollment_list_create"),
    path("api/enrollments/<int:pk>/", views.enrollment_detail, name="enrollment_detail"),
    path("api/enrollments/<int:pk>/cancel/", views.enrollment_cancel, name="enrollment_cancel"),

    # Pricing calculator (AJAX)
    path("api/calculate-pricing/", views.calculate_pricing, name="calculate_pricing"),
    path("api/calculate-product/", views.calculate_product, name="calculate_product"),
    path("api/route-calculator/", views.route_calculator, name="route_calculator"),

    # Applications CRUD (AJAX)
    path("api/applications/", views.application_list_create, name="application_list_create"),
    path("api/applications/<int:pk>/", views.application_detail, name="application_detail"),

    # Reports (downloadable)
    path("api/reports/compliance/", views.report_compliance, name="report_compliance"),
    path("api/reports/profit/", views.report_profit, name="report_profit"),
    path("api/reports/material-usage/", views.report_material_usage, name="report_material_usage"),
]
```

### `fertilization/views.py` (skeleton — hub view only for now):

```python
"""Views for the fertilization management hub."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from accounts.decorators import role_required
from dashboard.views import get_business


@role_required("owner", "manager")
def hub(request):
    """Main fertilization management hub — tabbed page."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    from billing.models import FertilizerProduct, FertilizerApplication
    from customers.models import Property, Customer
    from .models import FertilizationProgram, CustomerProgramEnrollment, ScheduledRound

    # Programs tab data
    programs = FertilizationProgram.objects.filter(
        business=business
    ).prefetch_related('rounds__products')

    # Products tab data
    products = FertilizerProduct.objects.filter(business=business).order_by('name')

    # Customers tab data
    current_year = date.today().year
    enrollments = CustomerProgramEnrollment.objects.filter(
        business=business, year=current_year
    ).select_related('property__customer', 'program').prefetch_related('scheduled_rounds')

    # Applications tab data
    recent_applications = FertilizerApplication.objects.filter(
        business=business
    ).select_related('property__customer', 'product', 'applied_by')[:50]

    # Properties for dropdowns
    properties = Property.objects.filter(
        customer__business=business
    ).select_related('customer').order_by('customer__name', 'address')

    # JSON data for JavaScript
    import json as json_mod
    products_json = json_mod.dumps([
        {
            'id': p.id,
            'name': p.name,
            'npk': p.npk_display if hasattr(p, 'npk_display') else '',
            'application_rate': str(p.application_rate) if p.application_rate else '',
            'cost_per_pound': str(p.get_cost_per_pound_equivalent()),
            'product_type': getattr(p, 'product_type', 'granular'),
            'active': p.active,
        }
        for p in products.filter(active=True)
    ])

    properties_json = json_mod.dumps([
        {
            'id': p.id,
            'address': p.address,
            'customer_name': p.customer.name,
            'lawn_sqft': p.lawn_square_feet,
        }
        for p in properties
    ])

    programs_json = json_mod.dumps([
        {
            'id': prog.id,
            'name': prog.name,
            'num_rounds': prog.rounds.count(),
            'grass_type': prog.grass_type,
        }
        for prog in programs.filter(is_active=True)
    ])

    context = {
        'programs': programs,
        'products': products,
        'enrollments': enrollments,
        'recent_applications': recent_applications,
        'properties': properties,
        'current_year': current_year,
        'products_json': products_json,
        'properties_json': properties_json,
        'programs_json': programs_json,
        'growing_season_start': business.growing_season_start_month or 3,
        'growing_season_end': business.growing_season_end_month or 10,
    }

    return render(request, "fertilization/hub.html", context)
```

### Add to `config/urls.py` (before the closing bracket, after the messaging line):

```python
path("fertilization/", include(("fertilization.urls", "fertilization"), namespace="fertilization")),
```

**Run:**
```bash
python manage.py check
python manage.py runserver 0:8000 &
# Visit /fertilization/ — should 500 because template doesn't exist yet, but URL resolves
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/fertilization/ -H "Cookie: ..."
kill %1
```

**Commit:**
```bash
git add fertilization/urls.py fertilization/views.py config/urls.py
git commit -m "feat(fertilization): add URL routing and hub view skeleton"
```

---

## Task 6: Hub HTML Template

**Files:**
- Create: `fertilization/templates/fertilization/hub.html`

**What to build:**

The main tabbed hub template following the same pattern as Employee Management. This is a large template — it includes:
- Page header
- Tab navigation (Programs, Customers, Products, Applications, Calculator, Reports)
- Tab content panels (one `<div>` per tab, shown/hidden via JS)
- Data tables for each tab
- Modal container for CRUD operations
- JavaScript for tab switching and modal management

**Template structure:**

```html
{% extends "base.html" %}
{% load static %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/fertilization.css' %}">
{% endblock %}

{% block content %}
<div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
  <div>
    <h1>Fertilization Management</h1>
    <p>Programs, products, customer enrollments, applications, and pricing — all in one place</p>
  </div>
</div>

{# CSRF token for AJAX #}
<form id="fert-csrf-form" style="display:none;">{% csrf_token %}</form>

{# ── Tab Navigation ── #}
<nav class="fert-tabs" aria-label="Sections">
  <a href="#programs" class="fert-tab active" data-tab="programs">
    <i data-lucide="clipboard-list" style="width:16px;height:16px;"></i>
    Programs
  </a>
  <a href="#customers" class="fert-tab" data-tab="customers">
    <i data-lucide="users" style="width:16px;height:16px;"></i>
    Customers
    {% if enrollments.count %}<span class="tab-badge">{{ enrollments.count }}</span>{% endif %}
  </a>
  <a href="#products" class="fert-tab" data-tab="products">
    <i data-lucide="package" style="width:16px;height:16px;"></i>
    Products
  </a>
  <a href="#applications" class="fert-tab" data-tab="applications">
    <i data-lucide="spray-can" style="width:16px;height:16px;"></i>
    Applications
  </a>
  <a href="#calculator" class="fert-tab" data-tab="calculator">
    <i data-lucide="calculator" style="width:16px;height:16px;"></i>
    Calculator
  </a>
  <a href="#reports" class="fert-tab" data-tab="reports">
    <i data-lucide="file-bar-chart" style="width:16px;height:16px;"></i>
    Reports
  </a>
</nav>

{# ══════════════════════════════════════════════════════════════ #}
{# ── PROGRAMS TAB ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-panel" id="panel-programs">
  <div class="panel-header">
    <h2>Program Templates</h2>
    <button class="btn btn-primary btn-sm" onclick="FertHub.openProgramModal()">+ New Program</button>
  </div>

  {% if programs %}
  <div class="table-responsive">
    <table class="data-table">
      <thead>
        <tr>
          <th>Program Name</th>
          <th>Rounds</th>
          <th>Grass Type</th>
          <th>Enrollments</th>
          <th>Active</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for program in programs %}
        <tr>
          <td><strong>{{ program.name }}</strong></td>
          <td>{{ program.num_rounds }}</td>
          <td>{{ program.get_grass_type_display }}</td>
          <td>{{ program.enrollments.count }}</td>
          <td>
            {% if program.is_active %}
            <span class="status-badge status-active">Active</span>
            {% else %}
            <span class="status-badge status-inactive">Inactive</span>
            {% endif %}
          </td>
          <td class="actions-cell">
            <button class="btn btn-sm" onclick="FertHub.editProgram({{ program.id }})">Edit</button>
            <button class="btn btn-sm" onclick="FertHub.duplicateProgram({{ program.id }})">Duplicate</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="empty-state">
    <i data-lucide="clipboard-list" style="width:48px;height:48px;opacity:0.3;"></i>
    <p>No fertilization programs yet.</p>
    <p>Create your first program template to get started.</p>
    <button class="btn btn-primary" onclick="FertHub.openProgramModal()">+ Create Program</button>
  </div>
  {% endif %}
</div>

{# ══════════════════════════════════════════════════════════════ #}
{# ── CUSTOMERS TAB ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-panel" id="panel-customers" style="display:none;">
  <div class="panel-header">
    <h2>Customer Enrollments — {{ current_year }}</h2>
    <button class="btn btn-primary btn-sm" onclick="FertHub.openEnrollModal()">+ Enroll Property</button>
  </div>

  {% if enrollments %}
  <div class="table-responsive">
    <table class="data-table">
      <thead>
        <tr>
          <th>Property</th>
          <th>Customer</th>
          <th>Program</th>
          <th>Sqft</th>
          <th>Price</th>
          <th>Progress</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for enrollment in enrollments %}
        <tr>
          <td>{{ enrollment.property.address }}</td>
          <td>{{ enrollment.property.customer.name }}</td>
          <td>{{ enrollment.program.name }}</td>
          <td>{{ enrollment.property.lawn_square_feet|default:"—" }}</td>
          <td>
            {% if enrollment.pricing_method == 'per_application' and enrollment.price_per_application %}
              ${{ enrollment.price_per_application }}/app
            {% elif enrollment.pricing_method == 'annual_flat' and enrollment.annual_price %}
              ${{ enrollment.annual_price }}/yr
            {% elif enrollment.pricing_method == 'per_sqft' and enrollment.price_per_sqft %}
              ${{ enrollment.price_per_sqft }}/sqft
            {% else %}
              —
            {% endif %}
          </td>
          <td>{{ enrollment.rounds_completed }}/{{ enrollment.total_rounds }}</td>
          <td>
            <span class="status-badge status-{{ enrollment.status }}">{{ enrollment.get_status_display }}</span>
          </td>
          <td class="actions-cell">
            <button class="btn btn-sm" onclick="FertHub.viewEnrollment({{ enrollment.id }})">View</button>
            {% if enrollment.status != 'cancelled' %}
            <button class="btn btn-sm btn-danger" onclick="FertHub.cancelEnrollment({{ enrollment.id }})">Cancel</button>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="empty-state">
    <i data-lucide="users" style="width:48px;height:48px;opacity:0.3;"></i>
    <p>No customer enrollments for {{ current_year }}.</p>
    <p>Enroll a property into a fertilization program to get started.</p>
    <button class="btn btn-primary" onclick="FertHub.openEnrollModal()">+ Enroll Property</button>
  </div>
  {% endif %}
</div>

{# ══════════════════════════════════════════════════════════════ #}
{# ── PRODUCTS TAB ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-panel" id="panel-products" style="display:none;">
  <div class="panel-header">
    <h2>Fertilizer Products</h2>
    <button class="btn btn-primary btn-sm" onclick="FertHub.openProductModal()">+ Add Product</button>
  </div>

  {% if products %}
  <div class="table-responsive">
    <table class="data-table">
      <thead>
        <tr>
          <th>Product Name</th>
          <th>NPK</th>
          <th>Type</th>
          <th>App Rate</th>
          <th>Cost/lb</th>
          <th>EPA #</th>
          <th>Active</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for product in products %}
        <tr>
          <td><strong>{{ product.name }}</strong></td>
          <td>{{ product.npk_display|default:"—" }}</td>
          <td>{{ product.get_product_type_display|default:"—" }}</td>
          <td>{% if product.application_rate %}{{ product.application_rate }} lbs/1k sqft{% else %}—{% endif %}</td>
          <td>${{ product.get_cost_per_pound_equivalent }}</td>
          <td>{{ product.epa_registration_number|default:"—" }}</td>
          <td>
            {% if product.active %}
            <span class="status-badge status-active">Active</span>
            {% else %}
            <span class="status-badge status-inactive">Inactive</span>
            {% endif %}
          </td>
          <td class="actions-cell">
            <button class="btn btn-sm" onclick="FertHub.editProduct({{ product.id }})">Edit</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="empty-state">
    <i data-lucide="package" style="width:48px;height:48px;opacity:0.3;"></i>
    <p>No fertilizer products yet.</p>
    <p>Add your products with NPK analysis and application rates.</p>
    <button class="btn btn-primary" onclick="FertHub.openProductModal()">+ Add Product</button>
  </div>
  {% endif %}
</div>

{# ══════════════════════════════════════════════════════════════ #}
{# ── APPLICATIONS TAB ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-panel" id="panel-applications" style="display:none;">
  <div class="panel-header">
    <h2>Application Records</h2>
    <button class="btn btn-primary btn-sm" onclick="FertHub.openApplicationModal()">+ Record Application</button>
  </div>

  {% if recent_applications %}
  <div class="table-responsive">
    <table class="data-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Property</th>
          <th>Product</th>
          <th>Amount</th>
          <th>Rate</th>
          <th>Weather</th>
          <th>Material $</th>
          <th>Charged $</th>
          <th>Profit %</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for app in recent_applications %}
        <tr>
          <td>{{ app.application_date|date:"M j, Y" }}</td>
          <td>{{ app.property.address|truncatechars:30 }}</td>
          <td>{{ app.product.name|default:"Unknown"|truncatechars:25 }}</td>
          <td>{{ app.pounds_used }} lbs</td>
          <td>{% if app.lbs_per_1000_sqft %}{{ app.lbs_per_1000_sqft }}/1k{% else %}—{% endif %}</td>
          <td>
            {% if app.weather_temp_f %}{{ app.weather_temp_f }}°F{% endif %}
            {% if app.weather_conditions %}{{ app.get_weather_conditions_display }}{% endif %}
          </td>
          <td>${{ app.material_cost }}</td>
          <td>{% if app.charge_amount %} ${{ app.charge_amount }}{% else %}—{% endif %}</td>
          <td>
            {% if app.profit_margin is not None %}
              <span class="{% if app.profit_margin >= 30 %}text-success{% elif app.profit_margin >= 15 %}text-warning{% else %}text-danger{% endif %}">
                {{ app.profit_margin|floatformat:0 }}%
              </span>
            {% else %}—{% endif %}
          </td>
          <td class="actions-cell">
            <button class="btn btn-sm" onclick="FertHub.editApplication({{ app.id }})">Edit</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="empty-state">
    <i data-lucide="spray-can" style="width:48px;height:48px;opacity:0.3;"></i>
    <p>No fertilizer applications recorded yet.</p>
    <button class="btn btn-primary" onclick="FertHub.openApplicationModal()">+ Record Application</button>
  </div>
  {% endif %}
</div>

{# ══════════════════════════════════════════════════════════════ #}
{# ── CALCULATOR TAB ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-panel" id="panel-calculator" style="display:none;">
  <div class="panel-header">
    <h2>Fertilization Calculator</h2>
  </div>

  <div class="calc-grid">
    {# Product Amount Calculator #}
    <div class="calc-card">
      <h3>Product Calculator</h3>
      <p class="calc-desc">How much product do you need?</p>
      <div class="form-group">
        <label>Lawn Area (sq ft)</label>
        <input type="number" id="calc-sqft" class="form-control" placeholder="e.g. 10000">
      </div>
      <div class="form-group">
        <label>Product</label>
        <select id="calc-product" class="form-control">
          <option value="">Select a product...</option>
        </select>
      </div>
      <div class="form-group">
        <label>Application Rate (lbs/1,000 sqft)</label>
        <input type="number" step="0.01" id="calc-rate" class="form-control" placeholder="Auto-fills from product">
      </div>
      <button class="btn btn-primary" onclick="FertHub.calculateProduct()">Calculate</button>
      <div id="calc-product-result" class="calc-result" style="display:none;"></div>
    </div>

    {# Pricing Calculator #}
    <div class="calc-card">
      <h3>Pricing Calculator</h3>
      <p class="calc-desc">Auto-price a program for a property</p>
      <div class="form-group">
        <label>Property</label>
        <select id="calc-property" class="form-control">
          <option value="">Select a property...</option>
        </select>
      </div>
      <div class="form-group">
        <label>Program</label>
        <select id="calc-program" class="form-control">
          <option value="">Select a program...</option>
        </select>
      </div>
      <div class="form-group">
        <label>Markup %</label>
        <input type="number" step="1" id="calc-markup" class="form-control" value="40">
      </div>
      <div class="form-group">
        <label>Base Fee (per visit)</label>
        <input type="number" step="0.01" id="calc-base-fee" class="form-control" value="0">
      </div>
      <button class="btn btn-primary" onclick="FertHub.calculatePricing()">Calculate Pricing</button>
      <div id="calc-pricing-result" class="calc-result" style="display:none;"></div>
    </div>
  </div>
</div>

{# ══════════════════════════════════════════════════════════════ #}
{# ── REPORTS TAB ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-panel" id="panel-reports" style="display:none;">
  <div class="panel-header">
    <h2>Reports</h2>
  </div>

  <div class="calc-grid">
    <div class="calc-card">
      <h3>Compliance Report</h3>
      <p class="calc-desc">Export application records with EPA #, weather, and applicator details.</p>
      <div class="form-group">
        <label>Date Range</label>
        <div style="display:flex;gap:8px;">
          <input type="date" id="report-comp-start" class="form-control">
          <input type="date" id="report-comp-end" class="form-control">
        </div>
      </div>
      <button class="btn btn-primary" onclick="FertHub.downloadComplianceReport()">Download CSV</button>
    </div>

    <div class="calc-card">
      <h3>Profit Report</h3>
      <p class="calc-desc">Revenue vs. material cost by program, property, or month.</p>
      <div class="form-group">
        <label>Date Range</label>
        <div style="display:flex;gap:8px;">
          <input type="date" id="report-profit-start" class="form-control">
          <input type="date" id="report-profit-end" class="form-control">
        </div>
      </div>
      <button class="btn btn-primary" onclick="FertHub.downloadProfitReport()">Download CSV</button>
    </div>

    <div class="calc-card">
      <h3>Material Usage Report</h3>
      <p class="calc-desc">Product consumption and cost trends over time.</p>
      <div class="form-group">
        <label>Date Range</label>
        <div style="display:flex;gap:8px;">
          <input type="date" id="report-material-start" class="form-control">
          <input type="date" id="report-material-end" class="form-control">
        </div>
      </div>
      <button class="btn btn-primary" onclick="FertHub.downloadMaterialReport()">Download CSV</button>
    </div>
  </div>
</div>

{# ══════════════════════════════════════════════════════════════ #}
{# ── MODAL CONTAINER ── #}
{# ══════════════════════════════════════════════════════════════ #}
<div class="fert-modal-overlay" id="fert-modal-overlay" style="display:none;" onclick="FertHub.closeModal()">
  <div class="fert-modal" onclick="event.stopPropagation()">
    <div class="fert-modal-header">
      <h3 id="fert-modal-title">Modal Title</h3>
      <button class="fert-modal-close" onclick="FertHub.closeModal()">&times;</button>
    </div>
    <div class="fert-modal-body" id="fert-modal-body">
      <!-- Dynamic form content -->
    </div>
    <div class="fert-modal-footer" id="fert-modal-footer">
      <button class="btn" onclick="FertHub.closeModal()">Cancel</button>
      <button class="btn btn-primary" id="fert-modal-submit">Save</button>
    </div>
  </div>
</div>

{# ── Hidden JSON data for JavaScript ── #}
<script id="fert-products-data" type="application/json">{{ products_json|safe }}</script>
<script id="fert-properties-data" type="application/json">{{ properties_json|safe }}</script>
<script id="fert-programs-data" type="application/json">{{ programs_json|safe }}</script>

{% endblock %}

{% block extra_js %}
<script src="{% static 'js/fertilization.js' %}"></script>
{% endblock %}
```

**Commit:**
```bash
git add fertilization/templates/
git commit -m "feat(fertilization): add hub HTML template with 6 tabs, data tables, modal container, and calculator"
```

---

## Task 7: Hub CSS

**Files:**
- Create: `fertilization/static/css/fertilization.css`

**What to build:**

CSS for the fertilization hub. Follow the same design system variables from `static/css/design-system.css` (dark theme with `--bg`, `--bg-elevated`, `--bg-surface`, `--border`, `--text`, `--primary`, etc.). Style the tab navigation, panels, calculator cards, modal, status badges, and data tables.

Key elements to style:
- `.fert-tabs` — horizontal tab navigation (matches `.emp-mgmt-tabs` pattern)
- `.fert-tab` — individual tab links with icons
- `.fert-panel` — content panels (one per tab)
- `.panel-header` — flex row with title + action button
- `.calc-grid` — 2-column grid for calculator cards
- `.calc-card` — card with header, description, form, result area
- `.calc-result` — green-tinted result display area
- `.fert-modal-overlay`, `.fert-modal` — modal (same pattern as calendar modal)
- `.status-badge` variants for program statuses
- `.empty-state` — centered empty state with icon
- `.tab-badge` — notification count badge on tabs

The CSS should be ~200-300 lines, responsive (single column on mobile at 767px).

**Commit:**
```bash
git add fertilization/static/
git commit -m "feat(fertilization): add hub CSS with tabs, panels, calculator cards, and modal styles"
```

---

## Task 8: Hub JavaScript — Tab Switching, Modals, Calculator

**Files:**
- Create: `fertilization/static/js/fertilization.js`

**What to build:**

The main JavaScript file for the hub. It handles:

1. **Tab switching** — click tab → show corresponding panel, hide others, update active class
2. **Modal management** — open/close modal, populate form HTML dynamically, submit via fetch
3. **Product Calculator** — sqft × rate → lbs needed, bags needed, cost
4. **Pricing Calculator** — calls `/fertilization/api/calculate-pricing/` → shows breakdown
5. **CRUD operations** — Programs, Products, Enrollments, Applications (all via fetch to JSON endpoints)
6. **Report downloads** — trigger CSV downloads via `/fertilization/api/reports/`

Structure as an IIFE with a `FertHub` namespace on `window`:

```javascript
(function() {
  'use strict';

  const CSRF = () => document.querySelector('#fert-csrf-form input[name=csrfmiddlewaretoken]').value;

  // Parse embedded JSON data
  const productsData = JSON.parse(document.getElementById('fert-products-data')?.textContent || '[]');
  const propertiesData = JSON.parse(document.getElementById('fert-properties-data')?.textContent || '[]');
  const programsData = JSON.parse(document.getElementById('fert-programs-data')?.textContent || '[]');

  // ── Tab Switching ──
  function initTabs() { /* ... */ }

  // ── Modal Management ──
  function openModal(title, bodyHtml, onSubmit) { /* ... */ }
  function closeModal() { /* ... */ }

  // ── API Helper ──
  async function api(url, method = 'GET', body = null) { /* fetch wrapper with CSRF */ }

  // ── Programs CRUD ──
  function openProgramModal(programId = null) { /* ... */ }
  function editProgram(id) { /* ... */ }
  function duplicateProgram(id) { /* ... */ }

  // ── Products CRUD ──
  function openProductModal(productId = null) { /* ... */ }
  function editProduct(id) { /* ... */ }

  // ── Enrollment CRUD ──
  function openEnrollModal() { /* ... */ }
  function viewEnrollment(id) { /* ... */ }
  function cancelEnrollment(id) { /* ... */ }

  // ── Applications CRUD ──
  function openApplicationModal() { /* ... */ }
  function editApplication(id) { /* ... */ }

  // ── Calculators ──
  function calculateProduct() { /* client-side: sqft × rate / 1000 */ }
  function calculatePricing() { /* calls API for full breakdown */ }

  // ── Reports ──
  function downloadComplianceReport() { /* window.location to CSV endpoint */ }
  function downloadProfitReport() { /* ... */ }
  function downloadMaterialReport() { /* ... */ }

  // ── Populate dropdowns ──
  function populateDropdowns() { /* fill <select> elements from JSON data */ }

  // ── Init ──
  document.addEventListener('DOMContentLoaded', function() {
    initTabs();
    populateDropdowns();
  });

  // Export to window
  window.FertHub = {
    openProgramModal, editProgram, duplicateProgram,
    openProductModal, editProduct,
    openEnrollModal, viewEnrollment, cancelEnrollment,
    openApplicationModal, editApplication,
    calculateProduct, calculatePricing,
    downloadComplianceReport, downloadProfitReport, downloadMaterialReport,
    closeModal,
  };
})();
```

This is a large file (~600-800 lines). Key details:

- **Modal forms** are built as HTML strings with form inputs. When the user clicks "Save", the JS collects form values, POSTs to the API, and reloads the page on success.
- **Product calculator** is purely client-side (no API call needed — just math).
- **Pricing calculator** calls the server API because it needs to look up program round details and product costs.
- **Enrollment modal** includes the auto-pricing preview: when property + program are selected, it auto-calls the pricing API and shows the breakdown.
- **Application modal** auto-fills sqft from the selected property and calculates lbs needed when product + rate are set.

**Commit:**
```bash
git add fertilization/static/js/
git commit -m "feat(fertilization): add hub JavaScript with tabs, modals, CRUD, calculators, and reports"
```

---

## Task 9: AJAX API Views — Programs + Rounds

**Files:**
- Modify: `fertilization/views.py` (add program and round CRUD views)

**What to build:**

Add these view functions after the hub view:

### `program_list_create` (GET/POST):
- GET: Return all programs as JSON (with rounds nested)
- POST: Create a new program. Expects JSON body with `name`, `description`, `grass_type`. Returns the new program as JSON.

### `program_detail` (GET/POST):
- GET: Return single program with rounds as JSON
- POST: Update program fields. Returns updated program as JSON.

### `program_delete` (POST):
- Soft check: if program has active enrollments, return error.
- Otherwise delete program (CASCADE deletes rounds too).

### `program_duplicate` (POST):
- Copy program + all rounds. Append " (Copy)" to name.
- Return new program as JSON.

### `round_list_create` (GET/POST for a specific program):
- GET: Return all rounds for program
- POST: Create a new round. Expects JSON with `round_number`, `name`, `target_month_start`, `target_month_end`, `product_ids`, `default_rate_override`, `crew_instructions`.

### `round_update_delete` (POST/DELETE):
- POST: Update round fields
- DELETE: Delete round (renumber remaining rounds)

All views should:
- Use `@role_required("owner", "manager")`
- Call `get_business(request)` and filter by business
- Return `JsonResponse`
- Handle validation errors with 400 status

**Commit:**
```bash
git add fertilization/views.py
git commit -m "feat(fertilization): add program and round CRUD API views"
```

---

## Task 10: AJAX API Views — Products (Enhanced CRUD)

**Files:**
- Modify: `fertilization/views.py` (add product views)

**What to build:**

### `product_list_create` (GET/POST):
- GET: Return all products as JSON (including new NPK, rate, EPA fields)
- POST: Create/update product. Expects JSON or form data with all FertilizerProduct fields including new ones.

### `product_detail` (GET/POST):
- GET: Return single product as JSON
- POST: Update product fields including NPK, application_rate, product_type, epa_registration_number

Note: These views manage `billing.FertilizerProduct` — imported from billing.models.

**Commit:**
```bash
git add fertilization/views.py
git commit -m "feat(fertilization): add product CRUD API views with NPK and application rate support"
```

---

## Task 11: AJAX API Views — Enrollments + Auto-Pricing

**Files:**
- Modify: `fertilization/views.py` (add enrollment views and pricing endpoints)

**What to build:**

### `enrollment_list_create` (GET/POST):
- GET: Return enrollments (filtered by year query param, default current year)
- POST: Create enrollment. This is the BIG one:
  1. Validates property_id, program_id, year
  2. Checks no duplicate enrollment exists
  3. Creates `CustomerProgramEnrollment` with pricing fields
  4. Auto-generates `ScheduledRound` records for each round in the program
  5. Dates come from `_fertilization_dates_for_year()` (imported from jobs.views)
  6. Each ScheduledRound gets `material_cost` calculated via pricing engine
  7. Each ScheduledRound gets `price` calculated based on enrollment pricing method
  8. Returns enrollment with rounds as JSON

### `enrollment_detail` (GET):
- Return enrollment with all scheduled rounds, including job links and application links

### `enrollment_cancel` (POST):
- Set status to 'cancelled'. Skip any pending/scheduled rounds.

### `calculate_pricing` (GET):
- Query params: `property_id`, `program_id`, `markup_pct`, `base_fee`
- Calls `calculate_enrollment_pricing()` from `fertilization.pricing`
- Returns full pricing breakdown as JSON

### `calculate_product` (GET):
- Query params: `square_feet`, `product_id`, `rate`
- Calls `calculate_lbs_needed()` and product's `calculate_cost()`
- Returns lbs needed, bags needed, material cost

### `route_calculator` (GET):
- Query param: `date`
- Finds all ScheduledRounds for that date
- Aggregates total material needed per product across all properties
- Returns truck loading sheet data as JSON

**Commit:**
```bash
git add fertilization/views.py
git commit -m "feat(fertilization): add enrollment, auto-pricing, and calculator API views"
```

---

## Task 12: AJAX API Views — Applications + Reports

**Files:**
- Modify: `fertilization/views.py` (add application and report views)

**What to build:**

### `application_list_create` (GET/POST):
- GET: Return applications filtered by date range, property, product (query params)
- POST: Create application record. Expects property_id, product_id, application_date, pounds_used, square_feet, lbs_per_1000_sqft, charge_amount, weather fields. Auto-calculates material_cost from product.

### `application_detail` (GET/POST):
- GET: Return single application as JSON
- POST: Update application fields

### `report_compliance` (GET):
- Query params: `start_date`, `end_date`
- Returns CSV download with columns: Date, Property Address, Customer, Product, EPA #, Lbs Applied, Rate (lbs/1k sqft), Sq Ft Treated, Applicator, Temp, Wind, Conditions
- Set Content-Type to `text/csv` with Content-Disposition attachment header

### `report_profit` (GET):
- Query params: `start_date`, `end_date`
- Returns CSV with: Date, Property, Product, Material Cost, Charge Amount, Profit, Margin %

### `report_material_usage` (GET):
- Query params: `start_date`, `end_date`
- Aggregates by product: Product Name, Total Lbs Used, Total Cost, # Applications

**Commit:**
```bash
git add fertilization/views.py
git commit -m "feat(fertilization): add application CRUD and CSV report views"
```

---

## Task 13: Wire into Base Template — Sidebar Nav

**Files:**
- Modify: `templates/base.html` (add Fertilization nav link in sidebar)

**What to build:**

Add a "Fertilization" link in the sidebar navigation. Find the nav section (around line 567-631) and add after the Estimates link (or wherever makes sense in the flow — it should be near Jobs and Estimator):

```html
<a href="{% url 'fertilization:hub' %}" class="btn btn-nav {% if '/fertilization' in request.path %}active{% endif %}">
  <i data-lucide="leaf" class="nav-icon"></i>
  Fertilization
</a>
```

Also add the CSS include in the `<head>`:
```html
<link rel="stylesheet" href="{% static 'css/fertilization.css' %}">
```

**Commit:**
```bash
git add templates/base.html
git commit -m "feat(fertilization): add Fertilization link to sidebar navigation"
```

---

## Task 14: Integration Testing

**Files:** None created — just verification steps

**Run these checks:**

```bash
# 1. Django system check
python manage.py check

# 2. Migrations are clean
python manage.py makemigrations --check --dry-run

# 3. All URL patterns resolve
python -c "
from django.urls import reverse
urls = [
    'fertilization:hub',
    'fertilization:program_list_create',
    'fertilization:product_list_create',
    'fertilization:enrollment_list_create',
    'fertilization:calculate_pricing',
    'fertilization:calculate_product',
    'fertilization:application_list_create',
    'fertilization:report_compliance',
]
for name in urls:
    try:
        url = reverse(name)
        print(f'  ✓ {name} → {url}')
    except Exception as e:
        print(f'  ✗ {name} → {e}')
"

# 4. Models are queryable
python -c "
import django; django.setup()
from fertilization.models import FertilizationProgram, ProgramRound, CustomerProgramEnrollment, ScheduledRound
print(f'FertilizationProgram: {FertilizationProgram.objects.count()}')
print(f'ProgramRound: {ProgramRound.objects.count()}')
print(f'CustomerProgramEnrollment: {CustomerProgramEnrollment.objects.count()}')
print(f'ScheduledRound: {ScheduledRound.objects.count()}')
print('All models queryable ✓')
"

# 5. Pricing engine works
python -c "
import django; django.setup()
from fertilization.pricing import calculate_lbs_needed, calculate_suggested_price
from decimal import Decimal
lbs = calculate_lbs_needed(3.5, 10000)
assert lbs == Decimal('35.00'), f'Expected 35.00, got {lbs}'
price = calculate_suggested_price(Decimal('45'), Decimal('40'), Decimal('25'))
assert price == Decimal('88.00'), f'Expected 88.00, got {price}'
print('Pricing engine calculations ✓')
"

# 6. Static files exist
python -c "
import os
files = [
    'fertilization/static/css/fertilization.css',
    'fertilization/static/js/fertilization.js',
    'fertilization/templates/fertilization/hub.html',
]
for f in files:
    assert os.path.exists(f), f'Missing: {f}'
    print(f'  ✓ {f}')
print('All static files found ✓')
"

# 7. Admin registrations
python -c "
import django; django.setup()
from django.contrib.admin.sites import site
from fertilization.models import FertilizationProgram, CustomerProgramEnrollment
from billing.models import FertilizerProduct, FertilizerApplication
for model in [FertilizationProgram, CustomerProgramEnrollment, FertilizerProduct, FertilizerApplication]:
    assert model in site._registry, f'{model.__name__} not registered in admin'
    print(f'  ✓ {model.__name__} registered')
print('All admin registrations ✓')
"
```

**Commit (if any fixes needed):**
```bash
git add -A
git commit -m "fix(fertilization): integration test fixes"
```

---

## Summary

| Task | What | New/Modified Files |
|------|------|-------------------|
| 1 | Django app + models | fertilization/{__init__,apps,models,admin}.py, config/settings.py |
| 2 | Enhance existing models | billing/models.py, customers/models.py, migrations |
| 3 | Admin registrations | billing/admin.py |
| 4 | Auto-pricing engine | fertilization/pricing.py |
| 5 | URL routing + hub view | fertilization/{urls,views}.py, config/urls.py |
| 6 | Hub HTML template | fertilization/templates/fertilization/hub.html |
| 7 | Hub CSS | fertilization/static/css/fertilization.css |
| 8 | Hub JavaScript | fertilization/static/js/fertilization.js |
| 9 | Program + Round API views | fertilization/views.py |
| 10 | Product API views | fertilization/views.py |
| 11 | Enrollment + pricing API views | fertilization/views.py |
| 12 | Application + report API views | fertilization/views.py |
| 13 | Sidebar nav link | templates/base.html |
| 14 | Integration testing | (verification only) |

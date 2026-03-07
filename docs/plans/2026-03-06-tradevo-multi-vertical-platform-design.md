# Tradevo — Multi-Vertical Home Service Platform Design

**Date:** 2026-03-06
**Status:** Approved
**Scope:** Transform the existing landscape-only SaaS into a multi-vertical home service business management platform.

---

## Overview

Tradevo is a one-stop-shop platform for home service businesses. The platform uses a **shared core + vertical modules** architecture: one unified platform for scheduling, CRM, invoicing, payroll, and payments, with plug-in modules that activate based on the business type selected at signup.

**Name:** Tradevo (trade + evolution)
**Positioning:** Direct competitor to Jobber, Housecall Pro, and ServiceTitan — but more affordable and more deeply customized per vertical.

---

## Phase 1 Launch Verticals (Big 5)

1. **Landscaping & Lawn Care** (existing — already built)
2. **HVAC** (heating, ventilation, air conditioning)
3. **Plumbing**
4. **Electrical**
5. **Cleaning** (residential & commercial)
6. **General / Other Home Service** (catch-all with core features only)

---

## Architecture: Shared Core + Vertical Modules

### Shared Core (same for ALL verticals)

- Scheduling & dispatching (calendar, recurring jobs, crews)
- CRM (customers, properties/locations, contracts, communication)
- Invoicing & estimates (line items, templates, automation, reminders)
- Payments (Stripe Connect, payment links)
- Employee management (payroll, time tracking, schedules, PTO)
- Financial reporting (revenue, expenses, profit tracking)
- Team messaging (direct, crew, broadcast)
- Auth & security (2FA, roles, audit logs)
- Customer portal (self-serve booking, invoice payment)
- Business settings (timezone, email, branding)
- Online booking (new — customers book from website/Google)

### Vertical Modules (enabled per business_type)

| Module | Landscaping | HVAC | Plumbing | Electrical | Cleaning |
|--------|:-----------:|:----:|:--------:|:----------:|:--------:|
| Fertilization & Chemical Tracking | X | | | | |
| Growing Season Management | X | | | | |
| Property Estimation (AI) | X | | | | |
| Flat Rate Pricebook | | X | X | X | |
| Equipment Tracking | | X | X | X | |
| Service Agreements | | X | X | X | X |
| Inspection Reports | | X | X | X | |
| Checklists & Quality Control | optional | optional | optional | optional | X (required) |
| Room-by-Room Estimating | | | | | X |

### Terminology Engine

Labels dynamically adjust throughout the app based on `business.business_type`:

| Concept | Landscaping | HVAC | Plumbing | Electrical | Cleaning |
|---------|------------|------|----------|------------|----------|
| Job | Job | Service Call | Service Call | Service Call | Cleaning |
| Property | Property | Location | Location | Location | Home |
| Crew | Crew | Tech Team | Tech Team | Tech Team | Cleaning Team |
| Crew Member | Crew Member | Technician | Technician | Technician | Cleaner |
| Completion Photo | Before/After | Work Photo | Work Photo | Work Photo | Completion Photo |
| Material | Material | Parts & Equipment | Parts & Fittings | Parts & Wiring | Supplies |
| Estimate | Estimate | Quote | Quote | Quote | Quote |
| Route | Route | Dispatch | Dispatch | Dispatch | Schedule |

Implementation: A `terminology` template context processor that reads `business.business_type` and injects a `terms` dict into every template. Templates use `{{ terms.job }}` instead of hardcoded "Job".

---

## Data Model Changes

### Business Model Additions

```python
# On the existing Business model:
BUSINESS_TYPE_CHOICES = [
    ("landscaping", "Landscaping & Lawn Care"),
    ("hvac", "HVAC"),
    ("plumbing", "Plumbing"),
    ("electrical", "Electrical"),
    ("cleaning", "Cleaning"),
    ("general", "Other Home Service"),
]

BUSINESS_SUBTYPE_CHOICES = [
    # Landscaping
    ("lawn_care", "Lawn Care Only"),
    ("full_service", "Full-Service Landscaping"),
    # HVAC
    ("residential_hvac", "Residential HVAC"),
    ("commercial_hvac", "Commercial HVAC"),
    ("both_hvac", "Residential & Commercial HVAC"),
    # Plumbing
    ("residential_plumbing", "Residential Plumbing"),
    ("commercial_plumbing", "Commercial Plumbing"),
    ("both_plumbing", "Residential & Commercial Plumbing"),
    # Electrical
    ("residential_electrical", "Residential Electrical"),
    ("commercial_electrical", "Commercial Electrical"),
    ("both_electrical", "Residential & Commercial Electrical"),
    # Cleaning
    ("residential_cleaning", "Residential Cleaning"),
    ("commercial_cleaning", "Commercial Cleaning"),
    ("both_cleaning", "Residential & Commercial Cleaning"),
    # General
    ("general", "General"),
]

business_type = CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, default="landscaping")
business_subtype = CharField(max_length=30, choices=BUSINESS_SUBTYPE_CHOICES, default="full_service", blank=True)
enabled_modules = JSONField(default=list, blank=True)  # Auto-populated from business_type
terminology_overrides = JSONField(default=dict, blank=True)  # Custom label overrides
```

### New App: `pricebook` (HVAC/Plumbing/Electrical)

```python
class PricebookCategory(models.Model):
    business = FK(Business)
    name = CharField(max_length=200)
    parent_category = FK("self", null=True, blank=True)  # Nested categories
    sort_order = IntegerField(default=0)
    is_active = BooleanField(default=True)

class PricebookItem(models.Model):
    business = FK(Business)
    category = FK(PricebookCategory)
    name = CharField(max_length=300)
    description = TextField(blank=True)
    sku = CharField(max_length=100, blank=True)  # Part number
    flat_rate_price = DecimalField()  # What customer pays
    material_cost = DecimalField()  # Internal cost
    labor_minutes = IntegerField(default=0)
    manufacturer = CharField(max_length=200, blank=True)
    part_number = CharField(max_length=200, blank=True)
    warranty_info = TextField(blank=True)
    is_active = BooleanField(default=True)
    # Enables CSV/Excel import of existing pricebooks
```

### New App: `equipment` (HVAC/Plumbing/Electrical)

```python
class Equipment(models.Model):
    business = FK(Business)
    customer = FK(Customer)
    property = FK(Property)
    equipment_type = CharField()  # furnace, ac_unit, water_heater, panel, etc.
    make = CharField(max_length=200)
    model = CharField(max_length=200)
    serial_number = CharField(max_length=200, blank=True)
    install_date = DateField(null=True)
    warranty_expiry = DateField(null=True)
    last_service_date = DateField(null=True)
    next_service_due = DateField(null=True)
    location_in_property = CharField(max_length=200, blank=True)  # "basement", "attic", etc.
    notes = TextField(blank=True)
    is_active = BooleanField(default=True)

class EquipmentServiceLog(models.Model):
    equipment = FK(Equipment)
    job = FK(Job, null=True)
    service_type = CharField()  # maintenance, repair, replacement, inspection
    technician = FK(User, null=True)
    notes = TextField(blank=True)
    parts_used = JSONField(default=list)  # [{pricebook_item_id, qty, cost}]
    date = DateField()
```

### New App: `service_agreements` (HVAC/Plumbing/Electrical/Cleaning)

```python
class ServiceAgreement(models.Model):
    business = FK(Business)
    customer = FK(Customer)
    name = CharField(max_length=200)  # "Annual HVAC Maintenance Plan"
    agreement_type = CharField()  # maintenance, warranty, service_plan
    status = CharField()  # active, expired, cancelled, pending
    start_date = DateField()
    end_date = DateField(null=True)
    billing_frequency = CharField()  # monthly, quarterly, annual, one_time
    price = DecimalField()
    auto_renew = BooleanField(default=False)
    visits_included = IntegerField(default=0)  # 0 = unlimited
    visits_used = IntegerField(default=0)
    discount_percent_on_repairs = DecimalField(default=0)  # Agreement holders get X% off
    equipment = ManyToManyField(Equipment, blank=True)  # HVAC: tied to specific units
    notes = TextField(blank=True)

class AgreementVisit(models.Model):
    agreement = FK(ServiceAgreement)
    scheduled_date = DateField()
    completed_date = DateField(null=True)
    job = FK(Job, null=True)  # Links to actual job when scheduled
    technician = FK(User, null=True)
    notes = TextField(blank=True)
    status = CharField()  # scheduled, completed, skipped, cancelled
```

### New App: `checklists` (All verticals, critical for Cleaning)

```python
class ChecklistTemplate(models.Model):
    business = FK(Business)
    name = CharField(max_length=200)  # "Standard Home Deep Clean"
    description = TextField(blank=True)
    is_default = BooleanField(default=False)  # Auto-attach to new jobs

class ChecklistTemplateItem(models.Model):
    template = FK(ChecklistTemplate)
    label = CharField(max_length=300)
    requires_photo = BooleanField(default=False)
    sort_order = IntegerField(default=0)
    section = CharField(max_length=100, blank=True)  # Group items: "Kitchen", "Bathroom"

class JobChecklist(models.Model):
    job = FK(Job)
    template = FK(ChecklistTemplate)
    completed_by = FK(User, null=True)
    completed_at = DateTimeField(null=True)

class JobChecklistItem(models.Model):
    checklist = FK(JobChecklist)
    template_item = FK(ChecklistTemplateItem, null=True)
    label = CharField(max_length=300)
    is_completed = BooleanField(default=False)
    completed_at = DateTimeField(null=True)
    photo = ImageField(null=True, blank=True)
    notes = TextField(blank=True)
    sort_order = IntegerField(default=0)
```

### New App: `inspections` (HVAC/Plumbing/Electrical)

```python
class InspectionTemplate(models.Model):
    business = FK(Business)
    name = CharField(max_length=200)  # "Annual Furnace Inspection"
    sections = JSONField(default=list)
    # sections: [{"name": "Heat Exchanger", "items": ["Check for cracks", "Verify airflow"]}]

class Inspection(models.Model):
    business = FK(Business)
    job = FK(Job)
    template = FK(InspectionTemplate, null=True)
    inspector = FK(User)
    status = CharField()  # in_progress, completed, requires_followup
    findings = JSONField(default=list)
    # findings: [{"section": "Heat Exchanger", "item": "Check for cracks", "result": "pass/fail/na", "notes": "", "photos": []}]
    recommendations = TextField(blank=True)
    customer_visible = BooleanField(default=True)  # Show on customer portal
    completed_at = DateTimeField(null=True)
```

### Existing Models — No Changes Required

- User, Customer, Property, Job, Crew, Invoice, Estimate, TimeEntry, Message, etc.
- Fertilization app stays as-is (landscaping module)
- Property Estimator stays as-is (landscaping module)
- Financials app stays as-is (shared core)

---

## Signup Flow Changes

### Current Flow
1. Business name + email + password → creates Business + User
2. Redirect to subscription

### New Flow
1. **Select business type** (card selector: Landscaping, HVAC, Plumbing, Electrical, Cleaning, Other)
2. **Select subtype** (Residential / Commercial / Both)
3. **Business name + email + password** → creates Business + User
4. **Auto-populate `enabled_modules`** based on business_type
5. **Redirect to subscription** (tier selection with trade premium option)
6. **Vertical-specific onboarding checklist**

### Module Auto-Population Logic

```python
MODULE_DEFAULTS = {
    "landscaping": ["fertilization", "property_estimator", "growing_season", "checklists"],
    "hvac": ["pricebook", "equipment", "service_agreements", "inspections", "checklists"],
    "plumbing": ["pricebook", "equipment", "service_agreements", "inspections", "checklists"],
    "electrical": ["pricebook", "equipment", "service_agreements", "inspections", "checklists"],
    "cleaning": ["checklists", "service_agreements", "room_estimating"],
    "general": ["checklists"],
}
```

---

## Landing Pages

### URL Structure
```
/                    → Universal landing page (all verticals)
/landscaping/        → Landscaping-specific landing page
/hvac/               → HVAC-specific landing page
/plumbing/           → Plumbing-specific landing page
/electrical/         → Electrical-specific landing page
/cleaning/           → Cleaning-specific landing page
/pricing/            → Universal pricing (shows all tiers)
/features/           → Universal features (filterable by vertical)
/signup/             → New multi-step signup with vertical selection
```

### Universal Landing Page (`/`)
- Hero: "One platform for every home service business"
- Vertical selector cards (animated, pick your trade)
- Feature highlights with vertical toggle
- Social proof / testimonials from multiple verticals
- Pricing comparison table
- CTA buttons throughout

### Vertical Landing Pages (`/landscaping/`, `/hvac/`, etc.)
- Trade-specific hero imagery and copy
- Features relevant to THAT vertical highlighted
- Screenshots showing the app in that vertical's terminology
- Trade-specific testimonials
- SEO optimized for "[trade] business management software"
- CTA pre-selects their vertical in signup

---

## Subscription Tiers (Revised)

| | Solo | Pro | Trade Premium |
|---|------|-----|---------------|
| Price | $39/mo | $79/mo | $129/mo |
| Users | 1-2 | Up to 10 (+$15/ea) | Up to 20 (+$15/ea) |
| Target | Solo operators | Teams (all verticals) | HVAC/Plumbing/Electrical teams |
| Core Features | Scheduling, CRM, invoicing, estimates, payments | + payroll, messaging, automation | + pricebook, equipment tracking, service agreements, inspections |
| Checklists | Basic | Full | Full |
| Online Booking | Yes | Yes | Yes |
| Customer Portal | Yes | Yes | Yes |
| Document Templates | 1 | Unlimited | Unlimited |
| Reports | Basic | Full | Full + trade-specific |

---

## Terminology Engine Implementation

### Context Processor Approach

A Django context processor injects a `terms` dict into every template based on the logged-in user's `business.business_type`.

```python
# businesses/context_processors.py
TERMINOLOGY = {
    "landscaping": {
        "job": "Job", "job_plural": "Jobs",
        "crew_member": "Crew Member", "crew": "Crew",
        "property": "Property", "material": "Material",
        "estimate": "Estimate", "route": "Route",
        "completion_photo": "Before/After Photo",
    },
    "hvac": {
        "job": "Service Call", "job_plural": "Service Calls",
        "crew_member": "Technician", "crew": "Tech Team",
        "property": "Location", "material": "Parts & Equipment",
        "estimate": "Quote", "route": "Dispatch",
        "completion_photo": "Work Photo",
    },
    # ... plumbing, electrical, cleaning, general
}

def terminology(request):
    if hasattr(request, "user") and request.user.is_authenticated:
        btype = getattr(request.user.business, "business_type", "general")
        terms = TERMINOLOGY.get(btype, TERMINOLOGY["general"])
        # Apply any custom overrides
        overrides = getattr(request.user.business, "terminology_overrides", {})
        terms = {**terms, **overrides}
        return {"terms": terms}
    return {"terms": TERMINOLOGY["general"]}
```

Templates then use `{{ terms.job }}` instead of hardcoded "Job".

### Sidebar Navigation Filtering

The sidebar hides/shows sections based on `enabled_modules`:

```python
def navigation(request):
    if hasattr(request, "user") and request.user.is_authenticated:
        modules = request.user.business.enabled_modules or []
        return {
            "show_fertilization": "fertilization" in modules,
            "show_pricebook": "pricebook" in modules,
            "show_equipment": "equipment" in modules,
            "show_service_agreements": "service_agreements" in modules,
            "show_inspections": "inspections" in modules,
            "show_property_estimator": "property_estimator" in modules,
        }
    return {}
```

---

## Phase 1 Scope (Current — Build Now)

### New Django Apps to Create
1. `pricebook` — Flat rate pricebook with categories, items, CSV import
2. `equipment` — Customer equipment tracking with service logs
3. `service_agreements` — Maintenance contracts with scheduled visits
4. `checklists` — Job checklists with templates and photo verification
5. `inspections` — Digital inspection reports with templates

### Changes to Existing Apps
1. `businesses` — Add business_type, business_subtype, enabled_modules, terminology_overrides
2. `accounts` — New multi-step signup flow with vertical selection
3. `config/settings.py` — Register new apps, add terminology context processor
4. `templates/base.html` — Dynamic sidebar based on enabled_modules, terminology throughout
5. `templates/marketing/` — New universal + vertical landing pages
6. `subscription` — Add Trade Premium tier, update Stripe products/prices

### Online Booking (New Feature)
- Public booking page per business (like customer portal but for new customers)
- Embeddable booking widget for business websites
- Service selection, date/time picker, contact info collection
- Auto-creates Customer + Job in the system

### Twilio SMS Integration (New)
- Two-way SMS messaging between business and customers
- Appointment reminders via SMS
- "On my way" text notifications
- SMS-based review requests
- Inbound message routing to correct customer record

---

## Phase 2 Scope (Future — SMS & Email Marketing)

> Reference only. Not building now but Twilio SMS setup happens in Phase 1.

- SendGrid integration for bulk email campaigns
- Marketing campaign builder (email + SMS)
- Customer segmentation for targeted campaigns
- Automated reactivation campaigns for lapsed customers
- Seasonal reminder campaigns
- Referral program automation

## Phase 3 Scope (Future — AI Features)

> Reference only. Not building now.

- AI job pricing suggestions based on history and market data
- Smart pricebook recommendations
- AI-powered customer communication drafts
- Predictive scheduling (suggest optimal times)
- Equipment failure prediction (based on age, service history)

## Phase 4 Scope (Future — AI Receptionist & Advanced)

> Reference only. Not building now.

- Twilio Voice + OpenAI for 24/7 phone answering
- Auto-booking from phone calls
- Voice commands in mobile app
- Website builder with booking widget
- Supplier API integrations (Home Depot, Ferguson)
- Consumer financing (Stripe payment plans for large jobs)
- Franchise / multi-location management
- Fleet/GPS tracking
- Inventory management across trucks/warehouses
- Native iOS/Android mobile apps

---

## Cost Analysis

### Phase 1 Infrastructure Costs (New)
- **Twilio SMS**: ~$0.0079/msg + $1.15/phone number/mo. At 50 businesses = ~$97/mo
- **All other Phase 1 work**: $0 new API costs (built in-house)
- **Stripe**: New price IDs for Trade Premium tier (no added cost)

### Existing Infrastructure (Unchanged)
- Supabase Pro: ~$25/mo
- Railway: ~$5-20/mo
- Google Maps: ~$0-200/mo (free credits)
- Stripe: Transaction-based (passed to customers)

### Phase 2+ Future Costs (Reference)
- SendGrid: $20/mo for 50K emails
- OpenAI API: ~$100-300/mo at scale
- Twilio Voice: ~$200-500/mo at scale

---

## Competitive Positioning

| | Tradevo Solo ($39) | Tradevo Pro ($79) | Tradevo Premium ($129) | Jobber ($39-199) | Housecall Pro ($69-189) | ServiceTitan ($245-500/tech) |
|---|---|---|---|---|---|---|
| Multi-vertical | Yes | Yes | Yes | Yes (shallow) | Yes (shallow) | Trades only |
| Vertical-specific modules | Basic | Standard | Full | No | Limited | Yes (enterprise) |
| Pricebook | - | - | Yes | No | Yes (add-on) | Yes (add-on $$) |
| Equipment tracking | - | - | Yes | No | No | Yes |
| Service agreements | - | Yes | Yes | No | Yes (higher tier) | Yes |
| Online booking | Yes | Yes | Yes | Yes | Yes | Yes |
| Two-way SMS | Basic | Yes | Yes | Yes | Yes | Yes (add-on) |
| AI features | - | - | - | Yes (new) | Yes (new) | Limited |
| Price for 10 techs | $39 | $199 | $264 | $199+ | $189+ | $2,500-5,000 |

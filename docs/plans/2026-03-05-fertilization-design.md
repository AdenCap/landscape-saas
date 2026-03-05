# Fertilization Management — Feature Design

## Goal

Build a comprehensive fertilization management hub that lets landscape business owners define annual fertilization programs, auto-calculate pricing from square footage and products, manage customer enrollments, record applications, and generate compliance reports. The core experience: owner inputs square footage, selects a program, and gets an automatic price based on the products used and their desired markup.

## Competitive Context

Mid-market landscape SaaS has a clear gap: Real Green dominates enterprise ($700/mo) with deep chemical tracking, while Jobber/GorillaDesk offer only basic bolt-on chemical logging. Service Autopilot's "Master Packages" and FieldCentral's "Round Chaining" are the closest mid-market competitors for program management. This feature targets that gap — Real Green depth at mid-market price, modern UX.

## Architecture

New `fertilization` Django app serving as the management hub. Builds on existing `billing.FertilizerProduct` and `billing.FertilizerApplication` models (enhanced with new fields via migrations). Server-rendered tabbed page at `/fertilization/` with AJAX modals for CRUD operations — same pattern as Employee Management hub.

**Key integrations:**
- `billing.FertilizerProduct` — product library (enhanced with NPK, rates, EPA)
- `billing.FertilizerApplication` — application records (enhanced with weather)
- `customers.Property` — property data (enhanced with lawn_square_feet)
- `jobs.Job` — scheduled rounds create Jobs for dispatch
- `pricing.ServiceTemplate` — fertilization programs reference services for billing

---

## Data Models

### Enhanced Existing Models

**`billing.FertilizerProduct` — new fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `nitrogen_pct` | Decimal(5,2), nullable | N% from product label (e.g., 32.00 for "32-0-4") |
| `phosphorus_pct` | Decimal(5,2), nullable | P% from product label |
| `potassium_pct` | Decimal(5,2), nullable | K% from product label |
| `application_rate` | Decimal(6,2), nullable | Recommended lbs per 1,000 sqft |
| `product_type` | CharField choices: granular, liquid | Affects unit display and calculations |
| `epa_registration_number` | CharField(50), blank | For compliance tracking |

**`billing.FertilizerApplication` — new fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `weather_temp_f` | SmallIntegerField, nullable | Temperature at time of application |
| `weather_wind_mph` | Decimal(4,1), nullable | Wind speed |
| `weather_conditions` | CharField choices | clear, cloudy, partly_cloudy, light_rain, overcast |
| `applied_by` | FK to User, nullable | Technician who applied |

**`customers.Property` — new field:**

| Field | Type | Purpose |
|-------|------|---------|
| `lawn_square_feet` | PositiveIntegerField, nullable | Core sqft for quick calculations |

### New Models (fertilization app)

**`FertilizationProgram`** — Reusable annual program template

| Field | Type | Purpose |
|-------|------|---------|
| `business` | FK to Business | Ownership |
| `name` | CharField(200) | e.g., "5-Round Premium Cool-Season" |
| `description` | TextField, blank | Program details for internal use |
| `grass_type` | CharField choices: cool_season, warm_season, both | Target grass type |
| `is_active` | BooleanField, default True | Show in dropdowns |
| `created_at` | DateTimeField auto_now_add | Audit |
| `updated_at` | DateTimeField auto_now | Audit |

**`ProgramRound`** — One round within a program template

| Field | Type | Purpose |
|-------|------|---------|
| `program` | FK to FertilizationProgram (CASCADE) | Parent program |
| `round_number` | PositiveSmallIntegerField | Order (1-12) |
| `name` | CharField(100) | e.g., "Early Spring Pre-Emergent" |
| `target_month_start` | PositiveSmallIntegerField (1-12) | Earliest month for this round |
| `target_month_end` | PositiveSmallIntegerField (1-12) | Latest month for this round |
| `products` | M2M to FertilizerProduct | Products used in this round |
| `default_rate_override` | Decimal(6,2), nullable | Override product's default rate |
| `crew_instructions` | TextField, blank | What to do / notes for crew |

Unique together: (program, round_number)

**`CustomerProgramEnrollment`** — Assigns a program to a property for a year

| Field | Type | Purpose |
|-------|------|---------|
| `business` | FK to Business | Ownership |
| `property` | FK to Property (CASCADE) | Which property |
| `program` | FK to FertilizationProgram (PROTECT) | Which program template |
| `year` | PositiveSmallIntegerField | Program year (e.g., 2026) |
| `status` | CharField choices: enrolled, in_progress, completed, cancelled | Lifecycle |
| `pricing_method` | CharField choices: per_application, annual_flat, per_sqft | How to charge |
| `price_per_application` | Decimal(10,2), nullable | If pricing_method = per_application |
| `annual_price` | Decimal(10,2), nullable | If pricing_method = annual_flat |
| `price_per_sqft` | Decimal(6,4), nullable | If pricing_method = per_sqft |
| `base_fee` | Decimal(8,2), default 0 | Stop/trip charge per visit |
| `markup_pct` | Decimal(5,2), default 40 | Markup over material cost |
| `notes` | TextField, blank | Internal notes |
| `created_at` | DateTimeField auto_now_add | Audit |

Unique together: (property, program, year)

**`ScheduledRound`** — Actual scheduled round for an enrolled customer

| Field | Type | Purpose |
|-------|------|---------|
| `enrollment` | FK to CustomerProgramEnrollment (CASCADE) | Parent enrollment |
| `round_template` | FK to ProgramRound (SET_NULL, nullable) | Source round template |
| `round_number` | PositiveSmallIntegerField | Round # (preserved if template deleted) |
| `scheduled_date` | DateField | When this round is scheduled |
| `status` | CharField choices: pending, scheduled, completed, skipped | Lifecycle |
| `job` | FK to Job (SET_NULL, nullable) | Linked Job when dispatched |
| `application` | FK to FertilizerApplication (SET_NULL, nullable) | Linked record after completion |
| `price` | Decimal(10,2) | What to charge for this round |
| `material_cost` | Decimal(10,2), default 0 | Calculated material cost |
| `notes` | TextField, blank | Round-specific notes |

---

## Auto-Pricing Engine

### Formulas

**Material cost per round:**
```
For each product in round:
  lbs_needed = product.application_rate × (property.lawn_square_feet / 1000)
  product_cost = lbs_needed × product.cost_per_pound_equivalent
round_material_cost = sum(product_costs)
```

**Price per application (per_application method):**
```
price = base_fee + (lawn_square_feet / 1000 × rate_per_1000_sqft)
```

**Annual price (annual_flat method):**
```
total_material = sum(round_material_costs)
annual_price = total_material × (1 + markup_pct / 100)
```

**Per-sqft method:**
```
price_per_round = lawn_square_feet × price_per_sqft + base_fee
```

### Auto-Pricing Workflow

1. Owner selects property → system shows lawn_sqft (or prompts to enter)
2. Selects program template
3. System instantly calculates material cost per round and total
4. Shows suggested price at owner's default markup
5. Owner adjusts markup, base fee, or enters flat override
6. Confirms → rounds auto-scheduled across growing season dates
7. Jobs created for each round, ready to dispatch

---

## UI — Tabbed Hub at `/fertilization/`

### Programs Tab
- Table: program name, # rounds, grass type, active toggle
- Create/edit modal with inline round builder
- Duplicate button to copy programs

### Customers Tab
- Table: property, customer, program, year, status, price, rounds completed (e.g., "3/5")
- Enroll button → select property → select program → auto-price → confirm
- Bulk enroll: multiple properties → same program → individual pricing
- Expand row: shows each scheduled round with date, status, job link

### Products Tab
- Table: name, NPK display (e.g., "32-0-4"), type, app rate, cost/lb, active toggle
- Add/edit modal with all product fields including NPK, EPA, application rate
- Cost comparison column (cost per lb equivalent)

### Applications Tab
- Table: date, property, product, amount, weather, applicator, cost vs. charge, profit%
- Filter by date range, property, product
- Record application modal: select property → auto-fill sqft → select product → auto-calc lbs → weather → save

### Calculator Tab
- **Product calculator**: sqft + product + rate → lbs needed, bags needed, material cost
- **Pricing calculator**: sqft + program → material cost per round, annual total, suggested prices at 20/30/40/50% markup
- **Route calculator**: select date → all scheduled properties → total material needed (truck loading sheet)

### Reports Tab
- **Compliance export**: date range + filters → CSV/PDF of all applications with EPA#, weather, applicator
- **Profit report**: revenue vs. material cost by program, property, month
- **Material usage**: product consumption over time, cost trends
- **Program status**: enrollment overview — enrolled, in progress, completed, cancelled counts

---

## Key Integration Points

### With Jobs App
- When enrollment is confirmed, `ScheduledRound` records are created with dates spread across the growing season (reuses existing `_fertilization_dates_for_year()` logic)
- Each round can optionally create a `Job` record for crew dispatch
- When a Job is completed, the linked ScheduledRound updates to "completed" and a FertilizerApplication record is created

### With Billing App
- FertilizerApplication records feed into InvoiceLineItem creation
- Program pricing integrates with the existing per-service or monthly invoicing flow
- EstimateLineItem with item_type='fertilizing' can reference a program for estimate generation

### With Property Estimator
- PropertyEstimate.grass_sqft can auto-populate Property.lawn_square_feet
- Fertilizer calculator enhanced to reference the product library

---

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `fertilization/__init__.py` | NEW | App init |
| `fertilization/apps.py` | NEW | App config |
| `fertilization/models.py` | NEW | FertilizationProgram, ProgramRound, CustomerProgramEnrollment, ScheduledRound |
| `fertilization/admin.py` | NEW | Admin registrations with inlines |
| `fertilization/views.py` | NEW | Hub page view + AJAX endpoint views |
| `fertilization/urls.py` | NEW | URL routing |
| `fertilization/forms.py` | NEW | Forms for programs, rounds, enrollments, products |
| `fertilization/pricing.py` | NEW | Auto-pricing calculation engine |
| `fertilization/templates/fertilization/hub.html` | NEW | Main tabbed hub template |
| `fertilization/static/css/fertilization.css` | NEW | Hub-specific styles |
| `fertilization/static/js/fertilization.js` | NEW | Tab switching, modals, calculator, AJAX |
| `billing/migrations/XXXX_*.py` | NEW | Add NPK, rate, EPA to FertilizerProduct; weather to FertilizerApplication |
| `customers/migrations/XXXX_*.py` | NEW | Add lawn_square_feet to Property |
| `config/settings.py` | EDIT | Add 'fertilization' to INSTALLED_APPS |
| `config/urls.py` | EDIT | Add fertilization URL include |
| `templates/base.html` | EDIT | Add Fertilization to sidebar nav |

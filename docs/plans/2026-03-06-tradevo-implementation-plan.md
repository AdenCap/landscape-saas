# Tradevo Multi-Vertical Platform — Implementation Plan

**Date:** 2026-03-06
**Design Doc:** `docs/plans/2026-03-06-tradevo-multi-vertical-platform-design.md`
**Phase:** Phase 1 (Core Multi-Vertical + Twilio SMS)

---

## Implementation Order

Tasks are ordered by dependency — each builds on the previous. Estimated scope is noted for planning but not as a time commitment.

---

### Task 1: Add business_type fields to Business model

**Files:** `businesses/models.py`, `businesses/migrations/0028_*.py`

Add to Business model:
- `business_type` CharField with choices (landscaping, hvac, plumbing, electrical, cleaning, general). Default: "landscaping"
- `business_subtype` CharField with choices (lawn_care, full_service, residential_hvac, commercial_hvac, both_hvac, etc.). Blank allowed.
- `enabled_modules` JSONField (default=list). Auto-populated based on business_type.
- `terminology_overrides` JSONField (default=dict). Custom label overrides.

Add a model method `get_default_modules(business_type)` that returns the default module list for a given type.

Add a `save()` override or signal: when `business_type` changes and `enabled_modules` is empty, auto-populate from defaults.

Run `makemigrations` and `migrate`. All existing businesses default to "landscaping" with landscaping modules.

**Spec check:** Existing businesses must be unaffected. Migration must set business_type="landscaping" for all existing rows.

---

### Task 2: Terminology engine (context processor + template tags)

**Files:** `businesses/context_processors.py` (new), `config/settings.py`, all templates that hardcode "Job", "Crew", "Property", etc.

Create `businesses/context_processors.py`:
- Define TERMINOLOGY dict mapping business_type → {job, job_plural, crew, crew_member, property, material, estimate, route, completion_photo}
- Context processor reads `request.user.business.business_type`, returns `{"terms": {...}}`
- Apply `terminology_overrides` from business model on top of defaults

Register in `settings.py` TEMPLATES context_processors list.

Create `businesses/templatetags/terminology.py` with a `{% term "job" %}` template tag as alternative to `{{ terms.job }}`.

**Do NOT update all templates yet** — that happens incrementally as we build vertical features. Just get the engine working so `{{ terms.job }}` is available everywhere.

**Spec check:** `{{ terms.job }}` renders "Job" for landscaping, "Service Call" for HVAC. Logged-out users get generic defaults.

---

### Task 3: Navigation filtering (sidebar dynamic sections)

**Files:** `businesses/context_processors.py`, `templates/base.html`

Add a `navigation` context processor that checks `business.enabled_modules` and returns flags:
- `show_fertilization`, `show_pricebook`, `show_equipment`, `show_service_agreements`, `show_inspections`, `show_property_estimator`, `show_checklists`

Update `templates/base.html` sidebar to wrap module-specific nav items in `{% if show_fertilization %}` etc.

Landscaping businesses see: Fertilization, Property Estimator (as before)
HVAC/Plumbing/Electrical see: Pricebook, Equipment, Service Agreements, Inspections
Cleaning sees: Checklists, Service Agreements
All see: Dashboard, Calendar, Clients, Invoices, Estimates, Employees, Settings, Messaging

**Spec check:** An HVAC business does NOT see "Fertilization" in the sidebar. A landscaping business does NOT see "Pricebook".

---

### Task 4: Multi-step signup flow

**Files:** `accounts/views.py`, `accounts/forms.py`, `templates/registration/signup.html` (rewrite), `templates/registration/select_business_type.html` (new)

Replace single-step signup with multi-step:
1. **Step 1** (`/accounts/signup/`): Select business type (card grid: Landscaping, HVAC, Plumbing, Electrical, Cleaning, Other). Store in session.
2. **Step 2** (`/accounts/signup/details/`): Business name + subtype selection + email + password. Subtype options change based on type selected in step 1.
3. On submit: Create Business with business_type + subtype, auto-populate enabled_modules, create User, log in, redirect to subscription.

Update SignUpForm to include business_type and business_subtype fields.

**Spec check:** A user selecting "HVAC" → "Residential" creates a Business with business_type="hvac", business_subtype="residential_hvac", enabled_modules=["pricebook", "equipment", "service_agreements", "inspections", "checklists"].

---

### Task 5: Create `pricebook` app (HVAC/Plumbing/Electrical)

**Files:** New app `pricebook/` with models.py, views.py, urls.py, forms.py, templates/

Models:
- `PricebookCategory`: business, name, parent_category (self-FK), sort_order, is_active
- `PricebookItem`: business, category, name, description, sku, flat_rate_price, material_cost, labor_minutes, manufacturer, part_number, warranty_info, is_active

Views:
- List all categories with items (tree view)
- Add/edit/delete categories
- Add/edit/delete items
- **CSV/Excel import** — upload a spreadsheet to bulk-create pricebook items
- Search/filter items by name, category, SKU

URLs: `/pricebook/`, `/pricebook/import/`, `/pricebook/categories/add/`, `/pricebook/items/add/`, etc.

Integration with estimates/invoices: when creating estimate or invoice line items, HVAC/Plumbing/Electrical users can "pick from pricebook" to auto-fill description, price, material cost.

Register app in settings.py INSTALLED_APPS.

**Spec check:** Only accessible when "pricebook" is in business.enabled_modules. CSV import creates items correctly. Pricebook items can be selected when creating invoice/estimate line items.

---

### Task 6: Create `equipment` app (HVAC/Plumbing/Electrical)

**Files:** New app `equipment/` with models.py, views.py, urls.py, forms.py, templates/

Models:
- `Equipment`: business, customer, property, equipment_type (choices: furnace, ac_unit, heat_pump, water_heater, boiler, electrical_panel, generator, other), make, model, serial_number, install_date, warranty_expiry, last_service_date, next_service_due, location_in_property, notes, is_active
- `EquipmentServiceLog`: equipment, job, service_type (maintenance/repair/replacement/inspection), technician, notes, parts_used (JSON), date

Views:
- Equipment list (filterable by customer, type, warranty status)
- Equipment detail (show service history)
- Add/edit equipment (from customer profile or standalone)
- Add service log entry (auto-created when job completed on equipment)

URLs: `/equipment/`, `/equipment/<id>/`, `/equipment/add/`, etc.

Integration: On customer profile page, show "Equipment" tab listing all equipment at their properties. When creating a job for HVAC/Plumbing/Electrical, allow selecting which equipment the job is for.

**Spec check:** Equipment is linked to customer+property. Service history shows chronological log. Warranty expiry alerts on dashboard.

---

### Task 7: Create `service_agreements` app

**Files:** New app `service_agreements/` with models.py, views.py, urls.py, forms.py, templates/

Models:
- `ServiceAgreement`: business, customer, name, agreement_type, status (active/expired/cancelled/pending), start_date, end_date, billing_frequency (monthly/quarterly/annual/one_time), price, auto_renew, visits_included, visits_used, discount_percent_on_repairs, equipment (M2M), notes
- `AgreementVisit`: agreement, scheduled_date, completed_date, job (FK), technician, notes, status (scheduled/completed/skipped/cancelled)

Views:
- Agreement list (filterable by status, customer)
- Agreement detail (show visits, billing history, linked equipment)
- Create/edit agreement
- Schedule visits (auto-generate based on frequency)
- Dashboard widget showing upcoming agreement visits and renewals due

URLs: `/agreements/`, `/agreements/<id>/`, `/agreements/create/`, etc.

Integration: On customer profile, show "Service Agreements" tab. When agreement visit is due, auto-create a job (or prompt to schedule). On invoices, show agreement discount if customer has active agreement.

**Spec check:** An HVAC business can create a "Annual Maintenance Plan" tied to a customer's furnace + AC. 2 visits/year auto-scheduled. Customer gets 15% off repairs.

---

### Task 8: Create `checklists` app

**Files:** New app `checklists/` with models.py, views.py, urls.py, forms.py, templates/

Models:
- `ChecklistTemplate`: business, name, description, is_default
- `ChecklistTemplateItem`: template, label, requires_photo, sort_order, section
- `JobChecklist`: job, template, completed_by, completed_at
- `JobChecklistItem`: checklist, template_item, label, is_completed, completed_at, photo, notes, sort_order

Views:
- Template list (manage reusable checklists)
- Create/edit templates with drag-and-drop item ordering
- On job detail/crew view: show checklist, check off items, upload photos
- Checklist completion blocks job completion if required items are incomplete

URLs: `/checklists/templates/`, `/checklists/templates/create/`, etc.

Integration: When creating a job, optionally attach a checklist template. For cleaning businesses with is_default=True, auto-attach to every new job. Crew mobile view shows checklist items to check off.

**Spec check:** A cleaning business creates a "Standard Home Clean" checklist with sections (Kitchen, Bathroom, Living Room) and items. When a cleaner arrives, they see the checklist in their crew view and check off items with optional photos.

---

### Task 9: Create `inspections` app (HVAC/Plumbing/Electrical)

**Files:** New app `inspections/` with models.py, views.py, urls.py, forms.py, templates/

Models:
- `InspectionTemplate`: business, name, sections (JSON: [{name, items}])
- `Inspection`: business, job, template, inspector, status (in_progress/completed/requires_followup), findings (JSON), recommendations, customer_visible, completed_at

Views:
- Template management (create/edit inspection templates)
- Start inspection from job detail
- Fill in inspection form (pass/fail/NA per item, notes, photos)
- Generate PDF inspection report for customer
- Customer portal shows completed inspections

URLs: `/inspections/`, `/inspections/templates/`, etc.

**Spec check:** An HVAC tech starts a furnace inspection from the job detail page, fills in findings for each section, and marks it complete. Customer can view the report in their portal.

---

### Task 10: Online booking system

**Files:** New views in `customers/views.py` or new app `booking/`, templates

Features:
- Public booking page per business: `/<business_slug>/book/` or `/book/<token>/`
- Service selection (from business's ServiceTemplate list)
- Date/time picker (respects business hours, existing schedule)
- Customer info collection (name, email, phone, address)
- Auto-creates Customer + Property + Job in the system
- Confirmation email/SMS to customer
- Embeddable widget code for business websites (iframe or JS snippet)

Integration: New customers created via booking appear in CRM. Jobs appear on calendar. Business owner gets notification of new booking.

**Spec check:** A potential customer visits the booking page, selects "AC Tune-Up", picks a date, enters their info, and submits. The HVAC business sees a new job on their calendar and a new customer in their CRM.

---

### Task 11: Twilio SMS integration

**Files:** New app `sms/` or add to existing `messaging/` app, `config/settings.py`

Setup:
- Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to env/settings
- Install `twilio` Python package

Features:
- **Outbound SMS**: Send texts to customers (appointment reminders, "on my way", review requests)
- **Inbound SMS**: Twilio webhook receives customer replies, routes to correct customer record
- **Two-way conversation view**: In customer profile, show SMS conversation history alongside email
- **Automated SMS**: Appointment reminders (configurable hours before), payment reminders, review requests
- **Business phone number**: Each business gets a Twilio number (or uses shared pool initially)

Models:
- `SMSMessage`: business, customer, direction (inbound/outbound), body, from_number, to_number, twilio_sid, status, created_at

Views:
- Send SMS from customer profile
- SMS conversation thread view
- SMS settings (enable/disable automated messages, customize templates)

Webhook: `/webhooks/twilio/inbound/` — receives inbound SMS, matches to customer by phone number, creates SMSMessage record, notifies business owner.

**Spec check:** Business owner sends "On my way! ETA 15 minutes" to customer. Customer replies "Great, gate code is 1234". Both messages appear in the customer's message thread.

---

### Task 12: Vertical-specific onboarding checklists

**Files:** `dashboard/views.py`, `dashboard/templates/dashboard/onboarding.html`

Update onboarding flow to be vertical-specific:

**Landscaping onboarding** (existing + tweaks):
1. Business profile (name, logo, contact info)
2. Add first customer
3. Set up services and pricing
4. Configure growing season
5. Connect email (Gmail SMTP)
6. Enable Stripe Connect
7. Set up invoice automation

**HVAC/Plumbing/Electrical onboarding:**
1. Business profile
2. Set up pricebook (import CSV or add items manually)
3. Add first customer + equipment
4. Create a service agreement template
5. Create an inspection template
6. Connect email
7. Enable Stripe Connect

**Cleaning onboarding:**
1. Business profile
2. Create cleaning checklists
3. Add first customer
4. Set up recurring schedules
5. Connect email
6. Enable Stripe Connect

**Spec check:** An HVAC business sees onboarding steps specific to their trade. They are not asked to "configure growing season."

---

### Task 13: Vertical landing pages

**Files:** `templates/marketing/` (new templates), `marketing/views.py` or `config/urls.py`

Create:
- `/` — Universal landing page: "One platform for every home service business" with vertical selector
- `/landscaping/` — Landscaping-specific features, screenshots, copy
- `/hvac/` — HVAC-specific features, screenshots, copy
- `/plumbing/` — Plumbing-specific features, screenshots, copy
- `/electrical/` — Electrical-specific features, screenshots, copy
- `/cleaning/` — Cleaning-specific features, screenshots, copy

Each vertical page:
- Trade-specific hero with relevant imagery
- Feature highlights relevant to that trade
- Screenshots showing the app in that trade's terminology
- SEO meta tags optimized for "[trade] business software"
- CTA links to signup with business_type pre-selected

Update existing `/pricing/` page to show Solo / Pro / Trade Premium tiers.

**Spec check:** `/hvac/` shows HVAC-relevant features (pricebook, equipment tracking, service agreements) and links to signup with HVAC pre-selected.

---

### Task 14: Subscription tier updates (Trade Premium)

**Files:** `subscription/views.py`, Stripe dashboard, `config/settings.py`

- Create new Stripe Product + Price for Trade Premium tier ($129/mo)
- Add `STRIPE_SUBSCRIPTION_PRICE_ID_PREMIUM` to settings/env
- Update subscription status page to show 3 tiers
- Update checkout flow: tier selection based on business_type recommendation
- HVAC/Plumbing/Electrical businesses see Trade Premium recommended
- Landscaping/Cleaning businesses see Pro recommended
- Update `SubscriptionRequiredMiddleware` to check tier vs. module access
- Trade Premium modules (pricebook, equipment, inspections) require Trade Premium subscription

**Spec check:** An HVAC business on Pro tier cannot access the pricebook (prompted to upgrade). An HVAC business on Trade Premium can access everything.

---

### Task 15: Update existing templates with terminology

**Files:** All templates that hardcode "Job", "Crew", "Property", "Estimate", etc.

Systematically replace hardcoded terms across all templates:
- `templates/jobs/` — Replace "Job" with `{{ terms.job }}`, "Crew" with `{{ terms.crew }}`
- `templates/billing/` — Replace "Estimate" with `{{ terms.estimate }}`
- `templates/customers/` — Replace "Property" with `{{ terms.property }}`
- `templates/dashboard/` — Update all dashboard widgets
- `templates/base.html` — Sidebar labels

This is a large but mechanical task. Search-and-replace across all templates.

**Spec check:** An HVAC business sees "Service Calls" instead of "Jobs" throughout the entire app. A cleaning business sees "Homes" instead of "Properties".

---

### Task 16: Integration testing & verification

**Files:** Test across all verticals

Verify:
- [ ] Signup flow works for all 6 business types
- [ ] Correct modules are enabled for each type
- [ ] Sidebar shows correct sections per type
- [ ] Terminology displays correctly throughout
- [ ] Pricebook CRUD works (HVAC/Plumbing/Electrical only)
- [ ] Equipment CRUD works with customer linking
- [ ] Service agreements create/schedule/track visits
- [ ] Checklists attach to jobs and completion works
- [ ] Inspections create/fill/complete workflow
- [ ] Online booking creates customer + job
- [ ] Twilio SMS send/receive works
- [ ] Onboarding shows correct steps per vertical
- [ ] Landing pages render correctly with SEO meta
- [ ] Subscription tiers enforce module access correctly
- [ ] Existing landscaping businesses are completely unaffected
- [ ] `python manage.py check` passes
- [ ] `python manage.py migrate --check` passes
- [ ] All existing features still work (regression)

---

## Summary

| Task | What | New App? |
|------|------|----------|
| 1 | Business model fields (business_type, modules) | No |
| 2 | Terminology engine | No (new file) |
| 3 | Sidebar navigation filtering | No |
| 4 | Multi-step signup flow | No |
| 5 | Pricebook app | Yes |
| 6 | Equipment app | Yes |
| 7 | Service Agreements app | Yes |
| 8 | Checklists app | Yes |
| 9 | Inspections app | Yes |
| 10 | Online booking | Yes or extend customers |
| 11 | Twilio SMS integration | Yes or extend messaging |
| 12 | Vertical onboarding checklists | No |
| 13 | Vertical landing pages | No (new templates) |
| 14 | Subscription tier updates | No |
| 15 | Template terminology replacement | No |
| 16 | Integration testing | No |

**Total: 5 new Django apps, ~16 implementation tasks**

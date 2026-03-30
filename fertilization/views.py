"""Views for the fertilization management hub."""
import csv
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages

from django.contrib.auth import get_user_model

from accounts.decorators import role_required, module_required
from accounts.utils import get_business

User = get_user_model()

from .models import (
    FertilizationProgram,
    ProgramRound,
    CustomerProgramEnrollment,
    ScheduledRound,
)
from billing.models import FertilizerProduct, FertilizerApplication
from customers.models import Property
from .pricing import (
    calculate_lbs_needed,
    calculate_bags_needed,
    calculate_round_material_cost,
    calculate_enrollment_pricing,
    calculate_suggested_price,
)
from jobs.views import _fertilization_dates_for_year


# ─────────────────────────────────────────────────────────────
#  Program Builder (full-page create/edit with inline rounds)
# ─────────────────────────────────────────────────────────────

@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def program_builder(request, program_id=None):
    """Full-page program creation/editing with inline rounds."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    program = None
    existing_rounds = []
    if program_id:
        program = get_object_or_404(FertilizationProgram, id=program_id, business=business)
        for r in program.rounds.order_by('round_number').prefetch_related('products'):
            existing_rounds.append({
                'id': r.id,
                'round_number': r.round_number,
                'name': r.name,
                'target_month_start': r.target_month_start,
                'target_month_end': r.target_month_end,
                'default_rate_override': float(r.default_rate_override) if r.default_rate_override else None,
                'crew_instructions': r.crew_instructions,
                'product_ids': list(r.products.values_list('id', flat=True)),
            })

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        grass_type = request.POST.get("grass_type") or "both"

        if not name:
            messages.error(request, "Program name is required.")
            return redirect(request.path)

        if program:
            program.name = name
            program.description = description
            program.grass_type = grass_type
            program.save()
        else:
            try:
                program = FertilizationProgram.objects.create(
                    business=business, name=name, description=description, grass_type=grass_type,
                )
            except Exception as e:
                messages.error(request, f"Error creating program: {e}")
                return redirect(request.path)

        # Delete existing rounds and recreate from form data
        program.rounds.all().delete()

        round_names = request.POST.getlist("round_name")
        round_month_starts = request.POST.getlist("round_month_start")
        round_month_ends = request.POST.getlist("round_month_end")
        round_instructions = request.POST.getlist("round_instructions")
        round_rates = request.POST.getlist("round_rate")

        for i in range(len(round_names)):
            rname = (round_names[i] if i < len(round_names) else "").strip()
            if not rname:
                continue
            try:
                ms = int(round_month_starts[i]) if i < len(round_month_starts) else 1
                me = int(round_month_ends[i]) if i < len(round_month_ends) else ms
            except (ValueError, TypeError):
                ms, me = 1, 1
            rate = None
            if i < len(round_rates) and round_rates[i].strip():
                try:
                    rate = Decimal(round_rates[i].strip())
                except (InvalidOperation, ValueError):
                    rate = None
            instr = round_instructions[i] if i < len(round_instructions) else ""
            pr = ProgramRound.objects.create(
                program=program,
                round_number=i + 1,
                name=rname,
                target_month_start=max(1, min(12, ms)),
                target_month_end=max(1, min(12, me)),
                default_rate_override=rate,
                crew_instructions=instr,
            )
            # Attach selected products to this round
            product_ids = request.POST.getlist(f"round_products_{i}")
            if product_ids:
                pr.products.set(product_ids)

        action = "updated" if program_id else "created"
        messages.success(request, f"Program '{program.name}' {action} with {program.rounds.count()} rounds.")
        return redirect("fertilization:hub")

    products = list(FertilizerProduct.objects.filter(business=business, active=True).values('id', 'name'))

    return render(request, "fertilization/program_builder.html", {
        "program": program,
        "existing_rounds": json.dumps(existing_rounds),
        "products": products,
        "grass_types": FertilizationProgram.GRASS_TYPE_CHOICES,
    })


# ─────────────────────────────────────────────────────────────
#  Hub view (fully functional)
# ─────────────────────────────────────────────────────────────

@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def enrollment_builder(request):
    """Full-page enrollment: pick customer/property, program, pricing → enroll."""
    business = get_business(request)
    if not business:
        return redirect("/")

    from datetime import date as dt_date
    from customers.models import Customer

    if request.method == "POST":
        property_id = request.POST.get("property_id")
        program_id = request.POST.get("program_id")
        year = request.POST.get("year") or dt_date.today().year
        pricing_method = request.POST.get("pricing_method") or "per_application"
        price_per_app = request.POST.get("price_per_application") or None
        annual_price = request.POST.get("annual_price") or None
        price_per_sqft = request.POST.get("price_per_sqft") or None
        notes = request.POST.get("notes", "")
        existing_id = request.POST.get("enrollment_id")

        prop = get_object_or_404(Property, id=property_id, customer__business=business)
        program = get_object_or_404(FertilizationProgram, id=program_id, business=business)

        try:
            if existing_id:
                # Update existing enrollment
                enrollment = get_object_or_404(CustomerProgramEnrollment, id=int(existing_id), business=business)
                enrollment.property = prop
                enrollment.program = program
                enrollment.year = int(year)
                enrollment.pricing_method = pricing_method
                enrollment.price_per_application = Decimal(price_per_app) if price_per_app else None
                enrollment.annual_price = Decimal(annual_price) if annual_price else None
                enrollment.price_per_sqft = Decimal(price_per_sqft) if price_per_sqft else None
                enrollment.notes = notes
                enrollment.save()
                messages.success(request, f"Enrollment for {prop.address} updated.")
            else:
                # Create new enrollment
                enrollment = CustomerProgramEnrollment.objects.create(
                    business=business,
                    property=prop,
                    program=program,
                    year=int(year),
                    pricing_method=pricing_method,
                    price_per_application=Decimal(price_per_app) if price_per_app else None,
                    annual_price=Decimal(annual_price) if annual_price else None,
                    price_per_sqft=Decimal(price_per_sqft) if price_per_sqft else None,
                    notes=notes,
                )
                # Smart mid-year enrollment: only create pending rounds for
                # months that haven't passed. Earlier rounds get marked as skipped.
                today = dt_date.today()
                sched_year = int(year)
                pending_count = 0
                skipped_count = 0
                for rnd in program.rounds.order_by('round_number'):
                    try:
                        sched_date = dt_date(sched_year, rnd.target_month_start, 15)
                    except ValueError:
                        sched_date = dt_date(sched_year, rnd.target_month_start, 1)
                    # If the round's target month is in the past for this year
                    is_past = sched_date < today and sched_year == today.year
                    ScheduledRound.objects.create(
                        enrollment=enrollment,
                        round_template=rnd,
                        round_number=rnd.round_number,
                        scheduled_date=sched_date,
                        status='skipped' if is_past else 'pending',
                    )
                    if is_past:
                        skipped_count += 1
                    else:
                        pending_count += 1
                msg = f"Enrolled {prop.address} in {program.name} ({year}) — {pending_count} round{'' if pending_count == 1 else 's'} scheduled"
                if skipped_count:
                    msg += f", {skipped_count} past round{'' if skipped_count == 1 else 's'} skipped (season already started)"
                messages.success(request, msg)
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect("fertilization:hub")

    # GET — build context
    customers = Customer.objects.filter(business=business).prefetch_related('properties').order_by('name')
    programs = FertilizationProgram.objects.filter(business=business, is_active=True).prefetch_related('rounds').order_by('name')
    default_price_per_sqft = business.default_fert_price_per_sqft or ""

    # Build customer/property JSON for JS
    customers_data = []
    for c in customers:
        props = [{"id": p.id, "address": p.address, "sqft": p.yard_sqft} for p in c.properties.all()]
        customers_data.append({"id": c.id, "name": c.name, "properties": props})

    programs_data = []
    for p in programs:
        programs_data.append({"id": p.id, "name": p.name, "rounds": p.rounds.count()})

    # Support editing: ?edit=<enrollment_id>
    edit_enrollment = None
    edit_data = {}
    edit_id = request.GET.get("edit")
    if edit_id:
        try:
            edit_enrollment = CustomerProgramEnrollment.objects.select_related(
                'property__customer', 'program'
            ).get(id=int(edit_id), business=business)
            edit_data = {
                "id": edit_enrollment.id,
                "customer_id": edit_enrollment.property.customer_id,
                "property_id": edit_enrollment.property_id,
                "program_id": edit_enrollment.program_id,
                "year": edit_enrollment.year,
                "pricing_method": edit_enrollment.pricing_method,
                "price_per_application": float(edit_enrollment.price_per_application) if edit_enrollment.price_per_application else None,
                "annual_price": float(edit_enrollment.annual_price) if edit_enrollment.annual_price else None,
                "price_per_sqft": float(edit_enrollment.price_per_sqft) if edit_enrollment.price_per_sqft else None,
                "notes": edit_enrollment.notes,
            }
        except CustomerProgramEnrollment.DoesNotExist:
            pass

    return render(request, "fertilization/enrollment_builder.html", {
        "customers_json": json.dumps(customers_data),
        "programs_json": json.dumps(programs_data),
        "default_price_per_sqft": default_price_per_sqft,
        "current_year": dt_date.today().year,
        "edit_enrollment": edit_enrollment,
        "edit_data_json": json.dumps(edit_data),
    })


@role_required("owner", "manager")
@module_required("fertilization")
def hub(request):
    """Main fertilization management hub — tabbed page."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    # Programs tab data
    programs = FertilizationProgram.objects.filter(
        business=business
    ).prefetch_related('rounds__products')

    # Products tab data
    products = FertilizerProduct.objects.filter(business=business).order_by('name')

    # Customers tab data — organized BY PROGRAM
    current_year = date.today().year
    today = date.today()
    current_month = today.month

    # --- Auto-fix orphaned rounds ---
    # Rounds marked 'scheduled' or 'completed' whose linked job no longer exists
    # must be reverted to 'pending'. This catches stale data from deleted jobs.
    from jobs.models import Job as _Job
    orphaned = ScheduledRound.objects.filter(
        enrollment__business=business,
        status__in=['scheduled', 'completed'],
    ).exclude(job__isnull=True)
    # Find rounds whose job_id points to a deleted job
    existing_job_ids = set(_Job.objects.filter(
        id__in=orphaned.values_list('job_id', flat=True)
    ).values_list('id', flat=True))
    for sr in orphaned:
        if sr.job_id and sr.job_id not in existing_job_ids:
            sr.job = None
            sr.status = 'pending'
            sr.save(update_fields=['job', 'status'])
    # Also fix rounds marked 'scheduled' with no job at all
    ScheduledRound.objects.filter(
        enrollment__business=business,
        status='scheduled',
        job__isnull=True,
    ).update(status='pending')
    # Fix enrollments with more scheduled rounds than the program has
    for enr in CustomerProgramEnrollment.objects.filter(business=business, year=current_year).select_related('program').prefetch_related('scheduled_rounds'):
        program_rounds = enr.program.rounds.count()
        scheduled_count = enr.scheduled_rounds.count()
        if scheduled_count > program_rounds:
            # Delete excess rounds (keep only the first N matching the program)
            keep_ids = list(enr.scheduled_rounds.order_by('round_number').values_list('id', flat=True)[:program_rounds])
            enr.scheduled_rounds.exclude(id__in=keep_ids).delete()

    # Re-sync enrollment statuses
    for enr in CustomerProgramEnrollment.objects.filter(business=business, year=current_year):
        completed = enr.scheduled_rounds.filter(status='completed').count()
        total = enr.scheduled_rounds.count()
        if total == 0:
            continue
        if completed >= total:
            new_status = 'completed'
        elif completed > 0:
            new_status = 'in_progress'
        else:
            new_status = 'enrolled'
        if enr.status != new_status:
            enr.status = new_status
            enr.save(update_fields=['status'])

    enrollments = CustomerProgramEnrollment.objects.filter(
        business=business, year=current_year
    ).select_related('property__customer', 'program').prefetch_related(
        'scheduled_rounds', 'scheduled_rounds__round_template'
    ).order_by('program__name', 'property__customer__name')

    # Build program-centric structure
    program_clients = {}
    for enr in enrollments:
        pid = enr.program_id
        if pid not in program_clients:
            program_round_count = enr.program.rounds.count()
            program_clients[pid] = {
                "program": enr.program,
                "clients": [],
                "program_round_count": program_round_count,
                "active_round_num": None,
                "active_round_ids": [],
                "next_round_num": None,
                "next_round_date": None,
            }

        # Per-client data
        active_ids = []
        all_pending_ids = []
        all_pending_rounds = []  # [{id, num, month_name}, ...]
        rounds_completed = 0
        import calendar as cal_mod
        for sr in enr.scheduled_rounds.all():
            if sr.status == 'completed':
                rounds_completed += 1
            elif sr.status == 'pending':
                all_pending_ids.append(sr.id)
                month_num = sr.round_template.target_month_start if sr.round_template else sr.scheduled_date.month
                all_pending_rounds.append({
                    "id": sr.id,
                    "num": sr.round_number,
                    "month": cal_mod.month_abbr[month_num] if 1 <= month_num <= 12 else "?",
                })
                if month_num <= current_month:
                    active_ids.append(sr.id)
                    if not program_clients[pid]["active_round_num"]:
                        program_clients[pid]["active_round_num"] = sr.round_number
                elif not program_clients[pid]["next_round_num"]:
                    program_clients[pid]["next_round_num"] = sr.round_number
                    program_clients[pid]["next_round_date"] = sr.scheduled_date

        # Calculate lbs needed (4 lbs per 1000 sqft industry standard)
        sqft = enr.property.yard_sqft or 0
        lbs_needed = round(sqft / 1000 * 4, 1) if sqft else 0

        # Only the FIRST pending round per client (the next one to schedule)
        next_round_id = active_ids[0] if active_ids else (all_pending_ids[0] if all_pending_ids else None)
        program_clients[pid]["active_round_ids"].extend(active_ids[:1] if active_ids else all_pending_ids[:1])
        enr.calc_rounds_completed = rounds_completed
        actual_scheduled = enr.scheduled_rounds.count()
        enr.calc_rounds_total = min(program_clients[pid]["program_round_count"], actual_scheduled) if actual_scheduled else program_clients[pid]["program_round_count"]
        enr.calc_sqft = sqft
        enr.calc_lbs_needed = lbs_needed
        # next_round_id = just the single next round to schedule
        enr.calc_next_round_id = str(next_round_id) if next_round_id else ''
        enr.calc_all_pending_ids = ','.join(str(rid) for rid in all_pending_ids)
        enr.calc_has_pending = len(all_pending_ids) > 0
        enr.calc_pending_rounds = all_pending_rounds
        program_clients[pid]["clients"].append(enr)

    # Sort programs by name
    program_list = sorted(program_clients.values(), key=lambda p: p["program"].name)

    # Applications tab data
    recent_applications = FertilizerApplication.objects.filter(
        business=business
    ).select_related('property__customer', 'product', 'applied_by')[:50]

    # Properties for dropdowns
    properties = Property.objects.filter(
        customer__business=business
    ).select_related('customer').order_by('customer__name', 'address')

    # JSON data for JavaScript dropdowns
    products_json = json.dumps([
        {
            'id': p.id,
            'name': p.name,
            'npk': p.npk_display,
            'application_rate': str(p.application_rate) if p.application_rate else '',
            'cost_per_pound': str(p.get_cost_per_pound_equivalent()),
            'product_type': p.product_type,
            'active': p.active,
        }
        for p in products.filter(active=True)
    ])

    properties_json = json.dumps([
        {
            'id': p.id,
            'address': p.address,
            'customer_name': p.customer.name,
            'lawn_sqft': p.yard_sqft,
        }
        for p in properties
    ])

    programs_json = json.dumps([
        {
            'id': prog.id,
            'name': prog.name,
            'num_rounds': len(prog.rounds.all()),
            'grass_type': prog.grass_type,
        }
        for prog in programs.filter(is_active=True)
    ])

    can_see_pricing = request.user.role in ("owner", "manager")

    # Revenue projections for fertilization
    from decimal import Decimal
    fert_annual_revenue = Decimal("0")
    fert_per_app_revenue = Decimal("0")
    total_enrollments = 0
    for enr in enrollments:
        total_enrollments += 1
        if enr.annual_price and enr.annual_price > 0:
            fert_annual_revenue += enr.annual_price
        elif enr.price_per_application and enr.price_per_application > 0:
            num_rounds = enr.program.rounds.count() if enr.program else 1
            fert_annual_revenue += enr.price_per_application * num_rounds
            fert_per_app_revenue += enr.price_per_application
        elif enr.price_per_sqft and enr.price_per_sqft > 0 and enr.property.yard_sqft:
            num_rounds = enr.program.rounds.count() if enr.program else 1
            per_app = enr.price_per_sqft * Decimal(str(enr.property.yard_sqft)) / Decimal("1000")
            fert_annual_revenue += per_app * num_rounds
    fert_monthly_revenue = (fert_annual_revenue / Decimal("12")).quantize(Decimal("0.01")) if fert_annual_revenue else Decimal("0")

    # Actual fert revenue earned this year
    from jobs.models import JobServiceItem
    from django.db.models import Sum, F
    fert_actual_revenue = Decimal("0")
    fert_svc_names = ["fertiliz", "fert", "weed control", "lawn treatment"]
    from pricing.models import ServiceTemplate
    fert_svcs = ServiceTemplate.objects.filter(business=business, active=True)
    fert_svc_ids = [s.id for s in fert_svcs if any(n in s.name.lower() for n in fert_svc_names)]
    if fert_svc_ids:
        fert_actual_revenue = JobServiceItem.objects.filter(
            service_id__in=fert_svc_ids,
            job__property__customer__business=business,
            job__status="completed",
            job__scheduled_date__gte=date(today.year, 1, 1),
        ).aggregate(total=Sum(F("quantity") * F("unit_price")))["total"] or Decimal("0")

    context = {
        'programs': programs,
        'products': products,
        'program_list': program_list,
        'recent_applications': recent_applications,
        'properties': properties,
        'current_year': current_year,
        'products_json': products_json,
        'properties_json': properties_json,
        'programs_json': programs_json,
        'growing_season_start': business.growing_season_start_month or 3,
        'growing_season_end': business.growing_season_end_month or 10,
        'can_see_pricing': can_see_pricing,
        'fert_annual_revenue': fert_annual_revenue,
        'fert_monthly_revenue': fert_monthly_revenue,
        'fert_actual_revenue': fert_actual_revenue,
        'total_enrollments': total_enrollments,
    }

    return render(request, "fertilization/hub.html", context)


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _biz_or_403(request):
    """Return (business, None) or (None, JsonResponse 403)."""
    biz = get_business(request)
    if not biz:
        return None, JsonResponse({"error": "No business"}, status=403)
    return biz, None


def _dec_or_none(request, field):
    """Parse a POST field as Decimal, returning None if blank or invalid."""
    val = request.POST.get(field, '').strip()
    if not val:
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


def _int_or_none(request, field):
    """Parse a POST field as int, returning None if blank or invalid."""
    val = request.POST.get(field, '').strip()
    if not val:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _validate_fk_ownership(model_class, pk_value, business, field_name="id"):
    """Validate that a FK value belongs to the business. Returns (pk, None) or (None, error_msg)."""
    if not pk_value:
        return None, None
    try:
        pk_int = int(pk_value)
    except (ValueError, TypeError):
        return None, f"Invalid {field_name}."
    if not model_class.objects.filter(pk=pk_int, business=business).exists():
        return None, f"{field_name} not found or not accessible."
    return pk_int, None


def _validate_user_ownership(pk_value, business):
    """Validate that a user FK belongs to the business. Returns (pk, None) or (None, error_msg)."""
    if not pk_value:
        return None, None
    try:
        pk_int = int(pk_value)
    except (ValueError, TypeError):
        return None, "Invalid applied_by_id."
    if not User.objects.filter(pk=pk_int, business=business).exists():
        return None, "applied_by_id not found or not accessible."
    return pk_int, None


def _program_round_to_dict(rnd):
    """Serialize a ProgramRound (template round, not scheduled round)."""
    return {
        'id': rnd.id,
        'round_number': rnd.round_number,
        'name': rnd.name,
        'target_month_start': rnd.target_month_start,
        'target_month_end': rnd.target_month_end,
        'product_ids': list(rnd.products.values_list('id', flat=True)),
        'product_names': list(rnd.products.values_list('name', flat=True)),
        'default_rate_override': str(rnd.default_rate_override) if rnd.default_rate_override else '',
        'crew_instructions': rnd.crew_instructions,
    }


def _program_to_dict(program):
    """Serialize a FertilizationProgram with nested rounds."""
    rounds = []
    for r in program.rounds.all():
        rounds.append({
            'id': r.id,
            'round_number': r.round_number,
            'name': r.name,
            'target_month_start': r.target_month_start,
            'target_month_end': r.target_month_end,
            'product_ids': list(r.products.values_list('id', flat=True)),
            'product_names': list(r.products.values_list('name', flat=True)),
            'default_rate_override': str(r.default_rate_override) if r.default_rate_override else '',
            'crew_instructions': r.crew_instructions,
        })
    return {
        'id': program.id,
        'name': program.name,
        'description': program.description,
        'grass_type': program.grass_type,
        'is_active': program.is_active,
        'num_rounds': program.num_rounds,
        'enrollment_count': program.enrollments.count(),
        'rounds': rounds,
    }


def _product_to_dict(product):
    """Serialize a FertilizerProduct."""
    return {
        'id': product.id,
        'name': product.name,
        'pricing_type': product.pricing_type,
        'cost_per_pound': str(product.cost_per_pound) if product.cost_per_pound is not None else '',
        'cost_per_bag': str(product.cost_per_bag) if product.cost_per_bag is not None else '',
        'lbs_per_bag': str(product.lbs_per_bag) if product.lbs_per_bag is not None else '',
        'active': product.active,
        'notes': product.notes,
        'nitrogen_pct': str(product.nitrogen_pct) if product.nitrogen_pct is not None else '',
        'phosphorus_pct': str(product.phosphorus_pct) if product.phosphorus_pct is not None else '',
        'potassium_pct': str(product.potassium_pct) if product.potassium_pct is not None else '',
        'npk_display': product.npk_display,
        'application_rate': str(product.application_rate) if product.application_rate is not None else '',
        'product_type': product.product_type,
        'epa_registration_number': product.epa_registration_number,
        'cost_per_pound_equivalent': str(product.get_cost_per_pound_equivalent()),
    }


def _round_to_dict(r):
    """Serialize a ScheduledRound."""
    return {
        'id': r.id,
        'round_number': r.round_number,
        'scheduled_date': str(r.scheduled_date),
        'status': r.status,
        'price': str(r.price),
        'material_cost': str(r.material_cost),
        'notes': r.notes,
        'job_id': r.job_id,
        'application_id': r.application_id,
        'round_template_id': r.round_template_id,
    }


def _enrollment_to_dict(enrollment):
    """Serialize a CustomerProgramEnrollment with scheduled rounds."""
    scheduled = []
    for sr in enrollment.scheduled_rounds.all():
        scheduled.append(_round_to_dict(sr))
    return {
        'id': enrollment.id,
        'property_id': enrollment.property_id,
        'property_address': enrollment.property.address,
        'customer_name': enrollment.property.customer.name,
        'program_id': enrollment.program_id,
        'program_name': enrollment.program.name,
        'year': enrollment.year,
        'status': enrollment.status,
        'pricing_method': enrollment.pricing_method,
        'price_per_application': str(enrollment.price_per_application) if enrollment.price_per_application is not None else '',
        'annual_price': str(enrollment.annual_price) if enrollment.annual_price is not None else '',
        'price_per_sqft': str(enrollment.price_per_sqft) if enrollment.price_per_sqft is not None else '',
        'base_fee': str(enrollment.base_fee),
        'markup_pct': str(enrollment.markup_pct),
        'notes': enrollment.notes,
        'rounds_completed': enrollment.rounds_completed,
        'total_rounds': enrollment.total_rounds,
        'scheduled_rounds': scheduled,
    }


def _application_to_dict(app):
    """Serialize a FertilizerApplication."""
    return {
        'id': app.id,
        'property_id': app.property_id,
        'property_address': app.property.address,
        'customer_name': app.property.customer.name,
        'product_id': app.product_id,
        'product_name': app.product.name if app.product else '',
        'job_id': app.job_id,
        'application_date': str(app.application_date),
        'pounds_used': str(app.pounds_used),
        'square_feet': str(app.square_feet) if app.square_feet is not None else '',
        'lbs_per_1000_sqft': str(app.lbs_per_1000_sqft) if app.lbs_per_1000_sqft is not None else '',
        'material_cost': str(app.material_cost),
        'charge_amount': str(app.charge_amount) if app.charge_amount is not None else '',
        'notes': app.notes,
        'weather_temp_f': app.weather_temp_f,
        'weather_wind_mph': str(app.weather_wind_mph) if app.weather_wind_mph is not None else '',
        'weather_conditions': app.weather_conditions,
        'applied_by_id': app.applied_by_id,
        'applied_by_name': (app.applied_by.get_full_name() or app.applied_by.username) if app.applied_by else '',
        'profit': str(app.profit) if app.profit is not None else '',
        'profit_margin': str(round(app.profit_margin, 1)) if app.profit_margin is not None else '',
    }


# ─────────────────────────────────────────────────────────────
#  Task 9 — Programs + Rounds API
# ─────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def program_list_create(request):
    """GET: list all programs. POST: create a new program."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return JsonResponse({"error": "Name is required."}, status=400)
        description = request.POST.get('description', '').strip()
        grass_type = request.POST.get('grass_type', 'both')
        if grass_type not in ('cool_season', 'warm_season', 'both'):
            grass_type = 'both'
        is_active = request.POST.get('is_active', 'true').lower() not in ('false', '0')

        if FertilizationProgram.objects.filter(business=biz, name=name).exists():
            return JsonResponse({"error": "A program with this name already exists."}, status=400)

        program = FertilizationProgram.objects.create(
            business=biz,
            name=name,
            description=description,
            grass_type=grass_type,
            is_active=is_active,
        )
        return JsonResponse({"ok": True, "program": _program_to_dict(program)})

    # GET
    programs = FertilizationProgram.objects.filter(
        business=biz
    ).prefetch_related('rounds__products', 'enrollments')
    return JsonResponse({"items": [_program_to_dict(p) for p in programs]})


@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def program_detail(request, pk):
    """GET: single program detail. POST: update program."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    program = get_object_or_404(FertilizationProgram, pk=pk, business=biz)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name and name != program.name:
            if FertilizationProgram.objects.filter(business=biz, name=name).exclude(pk=pk).exists():
                return JsonResponse({"error": "A program with this name already exists."}, status=400)
            program.name = name
        if 'description' in request.POST:
            program.description = request.POST.get('description', '').strip()
        if 'grass_type' in request.POST:
            gt = request.POST.get('grass_type', 'both')
            if gt in ('cool_season', 'warm_season', 'both'):
                program.grass_type = gt
        if 'is_active' in request.POST:
            program.is_active = request.POST.get('is_active', 'true').lower() not in ('false', '0')
        program.save()
        return JsonResponse({"ok": True, "program": _program_to_dict(program)})

    # GET
    return JsonResponse({"data": _program_to_dict(program)})


@require_POST
@role_required("owner", "manager")
@module_required("fertilization")
def program_delete(request, pk):
    """POST: delete program if no active enrollments."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    program = get_object_or_404(FertilizationProgram, pk=pk, business=biz)

    active_enrollments = program.enrollments.exclude(status='cancelled').count()
    if active_enrollments:
        return JsonResponse(
            {"error": f"Cannot delete: {active_enrollments} active enrollment(s) exist."},
            status=400,
        )

    program.delete()
    return JsonResponse({"ok": True})


@require_POST
@role_required("owner", "manager")
@module_required("fertilization")
def program_duplicate(request, pk):
    """POST: duplicate program with all rounds and M2M products."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    original = get_object_or_404(
        FertilizationProgram.objects.prefetch_related('rounds__products'),
        pk=pk,
        business=biz,
    )

    # Find a unique name
    new_name = f"{original.name} (Copy)"
    counter = 2
    while FertilizationProgram.objects.filter(business=biz, name=new_name).exists():
        new_name = f"{original.name} (Copy {counter})"
        counter += 1

    new_program = FertilizationProgram.objects.create(
        business=biz,
        name=new_name,
        description=original.description,
        grass_type=original.grass_type,
        is_active=original.is_active,
    )

    for rnd in original.rounds.all():
        product_ids = list(rnd.products.values_list('id', flat=True))
        new_round = ProgramRound.objects.create(
            program=new_program,
            round_number=rnd.round_number,
            name=rnd.name,
            target_month_start=rnd.target_month_start,
            target_month_end=rnd.target_month_end,
            default_rate_override=rnd.default_rate_override,
            crew_instructions=rnd.crew_instructions,
        )
        new_round.products.set(product_ids)

    return JsonResponse({"ok": True, "program": _program_to_dict(new_program)})


@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def round_list_create(request, program_id):
    """GET: list rounds for a program. POST: create a round."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    program = get_object_or_404(FertilizationProgram, pk=program_id, business=biz)

    if request.method == 'POST':
        try:
            round_number = int(request.POST.get('round_number', 0))
            target_month_start = int(request.POST.get('target_month_start', 1))
            target_month_end = int(request.POST.get('target_month_end', 12))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid numeric field."}, status=400)

        name = request.POST.get('name', '').strip()
        if not name:
            return JsonResponse({"error": "Name is required."}, status=400)

        if ProgramRound.objects.filter(program=program, round_number=round_number).exists():
            return JsonResponse({"error": f"Round number {round_number} already exists."}, status=400)

        crew_instructions = request.POST.get('crew_instructions', '').strip()

        default_rate_override = None
        rate_str = request.POST.get('default_rate_override', '').strip()
        if rate_str:
            try:
                default_rate_override = Decimal(rate_str)
            except InvalidOperation:
                return JsonResponse({"error": "Invalid default_rate_override."}, status=400)

        rnd = ProgramRound.objects.create(
            program=program,
            round_number=round_number,
            name=name,
            target_month_start=target_month_start,
            target_month_end=target_month_end,
            default_rate_override=default_rate_override,
            crew_instructions=crew_instructions,
        )

        # Handle product_ids (comma-separated)
        product_ids_str = request.POST.get('product_ids', '').strip()
        if product_ids_str:
            try:
                pids = [int(x.strip()) for x in product_ids_str.split(',') if x.strip()]
                rnd.products.set(
                    FertilizerProduct.objects.filter(id__in=pids, business=biz)
                )
            except (ValueError, TypeError):
                pass  # ignore bad product ids

        return JsonResponse({"ok": True, "round": _program_round_to_dict(rnd)})

    # GET
    rounds = [_program_round_to_dict(r) for r in program.rounds.prefetch_related('products').all()]
    return JsonResponse({"items": rounds})


@require_http_methods(["POST", "DELETE"])
@role_required("owner", "manager")
@module_required("fertilization")
def round_update_delete(request, program_id, pk):
    """POST: update round. DELETE (or POST _method=delete): delete round."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    program = get_object_or_404(FertilizationProgram, pk=program_id, business=biz)
    rnd = get_object_or_404(ProgramRound, pk=pk, program=program)

    # Handle delete
    if request.method == 'DELETE' or request.POST.get('_method') == 'delete':
        rnd.delete()
        return JsonResponse({"ok": True})

    if request.method == 'POST':
        if 'name' in request.POST:
            rnd.name = request.POST.get('name', '').strip() or rnd.name
        if 'round_number' in request.POST:
            try:
                new_num = int(request.POST['round_number'])
                if new_num != rnd.round_number and ProgramRound.objects.filter(
                    program=program, round_number=new_num
                ).exclude(pk=pk).exists():
                    return JsonResponse({"error": f"Round number {new_num} already exists."}, status=400)
                rnd.round_number = new_num
            except (ValueError, TypeError):
                pass
        if 'target_month_start' in request.POST:
            try:
                rnd.target_month_start = int(request.POST['target_month_start'])
            except (ValueError, TypeError):
                pass
        if 'target_month_end' in request.POST:
            try:
                rnd.target_month_end = int(request.POST['target_month_end'])
            except (ValueError, TypeError):
                pass
        if 'crew_instructions' in request.POST:
            rnd.crew_instructions = request.POST.get('crew_instructions', '')

        rate_str = request.POST.get('default_rate_override', '').strip()
        if 'default_rate_override' in request.POST:
            if rate_str:
                try:
                    rnd.default_rate_override = Decimal(rate_str)
                except InvalidOperation:
                    return JsonResponse({"error": "Invalid default_rate_override."}, status=400)
            else:
                rnd.default_rate_override = None

        rnd.save()

        # Update products M2M if provided
        product_ids_str = request.POST.get('product_ids', '').strip()
        if 'product_ids' in request.POST:
            if product_ids_str:
                try:
                    pids = [int(x.strip()) for x in product_ids_str.split(',') if x.strip()]
                    rnd.products.set(
                        FertilizerProduct.objects.filter(id__in=pids, business=biz)
                    )
                except (ValueError, TypeError):
                    pass
            else:
                rnd.products.clear()

        return JsonResponse({
            "ok": True,
            "round": _program_round_to_dict(rnd),
        })

    return JsonResponse({"error": "Method not allowed."}, status=405)


# ─────────────────────────────────────────────────────────────
#  Task 10 — Products API
# ─────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def product_list_create(request):
    """GET: list all products. POST: create a product."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return JsonResponse({"error": "Name is required."}, status=400)

        if FertilizerProduct.objects.filter(business=biz, name=name).exists():
            return JsonResponse({"error": "A product with this name already exists."}, status=400)

        pricing_type = request.POST.get('pricing_type', 'per_pound')
        if pricing_type not in ('per_pound', 'per_bag'):
            pricing_type = 'per_pound'

        product_type = request.POST.get('product_type', 'granular')
        if product_type not in ('granular', 'liquid'):
            product_type = 'granular'

        product = FertilizerProduct.objects.create(
            business=biz,
            name=name,
            pricing_type=pricing_type,
            cost_per_pound=_dec_or_none(request, 'cost_per_pound'),
            cost_per_bag=_dec_or_none(request, 'cost_per_bag'),
            lbs_per_bag=_dec_or_none(request, 'lbs_per_bag'),
            active=request.POST.get('active', 'true').lower() not in ('false', '0'),
            notes=request.POST.get('notes', '').strip(),
            nitrogen_pct=_dec_or_none(request, 'nitrogen_pct'),
            phosphorus_pct=_dec_or_none(request, 'phosphorus_pct'),
            potassium_pct=_dec_or_none(request, 'potassium_pct'),
            application_rate=_dec_or_none(request, 'application_rate'),
            product_type=product_type,
            epa_registration_number=request.POST.get('epa_registration_number', '').strip(),
        )
        return JsonResponse({"ok": True, "product": _product_to_dict(product)})

    # GET
    products = FertilizerProduct.objects.filter(business=biz)
    return JsonResponse({"items": [_product_to_dict(p) for p in products]})


@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def product_detail(request, pk):
    """GET: single product detail. POST: update product."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    product = get_object_or_404(FertilizerProduct, pk=pk, business=biz)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name and name != product.name:
            if FertilizerProduct.objects.filter(business=biz, name=name).exclude(pk=pk).exists():
                return JsonResponse({"error": "A product with this name already exists."}, status=400)
            product.name = name

        if 'pricing_type' in request.POST:
            pt = request.POST.get('pricing_type')
            if pt in ('per_pound', 'per_bag'):
                product.pricing_type = pt

        if 'product_type' in request.POST:
            pt = request.POST.get('product_type')
            if pt in ('granular', 'liquid'):
                product.product_type = pt

        for f in ('cost_per_pound', 'cost_per_bag', 'lbs_per_bag',
                   'nitrogen_pct', 'phosphorus_pct', 'potassium_pct', 'application_rate'):
            if f in request.POST:
                val = request.POST.get(f, '').strip()
                if val:
                    try:
                        setattr(product, f, Decimal(val))
                    except InvalidOperation:
                        pass
                else:
                    setattr(product, f, None)

        if 'active' in request.POST:
            product.active = request.POST.get('active', 'true').lower() not in ('false', '0')
        if 'notes' in request.POST:
            product.notes = request.POST.get('notes', '')
        if 'epa_registration_number' in request.POST:
            product.epa_registration_number = request.POST.get('epa_registration_number', '').strip()

        product.save()
        return JsonResponse({"ok": True, "product": _product_to_dict(product)})

    # GET
    return JsonResponse({"data": _product_to_dict(product)})


# ─────────────────────────────────────────────────────────────
#  Task 11 — Enrollments + Pricing API
# ─────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def enrollment_list_create(request):
    """GET: list enrollments for year. POST: create enrollment with scheduled rounds."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    if request.method == 'POST':
        # --- required fields ---
        property_id = request.POST.get('property_id', '').strip()
        program_id = request.POST.get('program_id', '').strip()
        year_str = request.POST.get('year', '').strip()

        if not property_id or not program_id or not year_str:
            return JsonResponse({"error": "property_id, program_id, and year are required."}, status=400)

        try:
            year = int(year_str)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid year."}, status=400)

        prop = get_object_or_404(Property, pk=property_id, customer__business=biz)
        program = get_object_or_404(FertilizationProgram, pk=program_id, business=biz)

        if CustomerProgramEnrollment.objects.filter(property=prop, program=program, year=year).exists():
            return JsonResponse({"error": "This property is already enrolled in this program for this year."}, status=400)

        # --- pricing fields ---
        pricing_method = request.POST.get('pricing_method', 'per_application')
        if pricing_method not in ('per_application', 'annual_flat', 'per_sqft'):
            pricing_method = 'per_application'

        def _dec_or_default(field, default='0'):
            val = request.POST.get(field, '').strip()
            if not val:
                return Decimal(default) if default else None
            try:
                return Decimal(val)
            except InvalidOperation:
                return Decimal(default) if default else None

        enrollment = CustomerProgramEnrollment.objects.create(
            business=biz,
            property=prop,
            program=program,
            year=year,
            status='enrolled',
            pricing_method=pricing_method,
            price_per_application=_dec_or_default('price_per_application', default=''),
            annual_price=_dec_or_default('annual_price', default=''),
            price_per_sqft=_dec_or_default('price_per_sqft', default=''),
            base_fee=_dec_or_default('base_fee', '0'),
            markup_pct=_dec_or_default('markup_pct', '40'),
            notes=request.POST.get('notes', '').strip(),
        )

        # --- generate scheduled rounds ---
        rounds = list(program.rounds.prefetch_related('products').all())
        n_rounds = len(rounds)

        start_month = getattr(biz, 'growing_season_start_month', None) or 3
        end_month = getattr(biz, 'growing_season_end_month', None) or 10

        dates = _fertilization_dates_for_year(year, n_rounds, start_month, end_month)
        square_feet = prop.yard_sqft or 0

        for i, rnd_template in enumerate(rounds):
            # Calculate material cost for this round
            products = rnd_template.products.all()
            products_with_rates = [
                {
                    'product': p,
                    'rate_override': rnd_template.default_rate_override,
                }
                for p in products
            ]
            round_cost_info = calculate_round_material_cost(products_with_rates, square_feet)
            mat_cost = round_cost_info['total_cost']

            # Calculate price using markup
            price = calculate_suggested_price(mat_cost, enrollment.markup_pct, enrollment.base_fee)

            scheduled_date = dates[i] if i < len(dates) else date(year, 6, 15)

            ScheduledRound.objects.create(
                enrollment=enrollment,
                round_template=rnd_template,
                round_number=rnd_template.round_number,
                scheduled_date=scheduled_date,
                status='pending',
                price=price,
                material_cost=mat_cost,
            )

        # Refetch with select_related for proper serialization
        enrollment = CustomerProgramEnrollment.objects.select_related(
            'property__customer', 'program'
        ).prefetch_related('scheduled_rounds').get(pk=enrollment.pk)
        return JsonResponse({"ok": True, "enrollment": _enrollment_to_dict(enrollment)})

    # GET
    year = request.GET.get('year', '')
    if not year:
        year = date.today().year
    else:
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = date.today().year

    enrollments = CustomerProgramEnrollment.objects.filter(
        business=biz, year=year
    ).select_related('property__customer', 'program').prefetch_related('scheduled_rounds')

    return JsonResponse({"items": [_enrollment_to_dict(e) for e in enrollments]})


@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def enrollment_detail(request, pk):
    """GET: single enrollment with all scheduled rounds."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    enrollment = get_object_or_404(
        CustomerProgramEnrollment.objects.select_related('property__customer', 'program').prefetch_related('scheduled_rounds'),
        pk=pk,
        business=biz,
    )
    return JsonResponse({"data": _enrollment_to_dict(enrollment)})


@require_POST
@role_required("owner", "manager")
@module_required("fertilization")
def enrollment_cancel(request, pk):
    """POST: cancel enrollment, skip pending rounds."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    enrollment = get_object_or_404(CustomerProgramEnrollment, pk=pk, business=biz)
    enrollment.status = 'cancelled'
    enrollment.save(update_fields=['status'])

    # Skip all pending rounds
    enrollment.scheduled_rounds.filter(status='pending').update(status='skipped')

    return JsonResponse({"ok": True})


@require_POST
@role_required("owner", "manager")
@module_required("fertilization")
def enrollment_delete(request, pk):
    """POST: permanently delete an enrollment and its scheduled rounds."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    enrollment = get_object_or_404(CustomerProgramEnrollment, pk=pk, business=biz)
    customer_name = enrollment.property.customer.name
    enrollment.delete()
    messages.success(request, f"Enrollment for {customer_name} deleted.")
    return redirect("fertilization:hub")


@require_http_methods(["GET"])
@role_required("owner", "manager")
@module_required("fertilization")
def calculate_pricing(request):
    """GET: calculate enrollment pricing breakdown."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    property_id = request.GET.get('property_id', '')
    program_id = request.GET.get('program_id', '')
    if not property_id or not program_id:
        return JsonResponse({"error": "property_id and program_id are required."}, status=400)

    prop = get_object_or_404(Property, pk=property_id, customer__business=biz)
    program = get_object_or_404(
        FertilizationProgram.objects.prefetch_related('rounds__products'),
        pk=program_id,
        business=biz,
    )

    square_feet = prop.yard_sqft or 0

    try:
        markup_pct = Decimal(request.GET.get('markup_pct', '40'))
    except InvalidOperation:
        markup_pct = Decimal('40')

    try:
        base_fee = Decimal(request.GET.get('base_fee', '0'))
    except InvalidOperation:
        base_fee = Decimal('0')

    result = calculate_enrollment_pricing(program, square_feet, markup_pct, base_fee)

    # Serialize round_breakdown
    round_breakdown = []
    for rb in result['round_breakdown']:
        rnd = rb['round']
        product_details = []
        for pd in rb['product_details']:
            product_details.append({
                'product_id': pd['product'].id,
                'product_name': pd['product'].name,
                'lbs_needed': str(pd['lbs_needed']),
                'cost': str(pd['cost']),
            })
        round_breakdown.append({
            'round_id': rnd.id,
            'round_number': rnd.round_number,
            'round_name': rnd.name,
            'material_cost': str(rb['material_cost']),
            'suggested_price': str(rb['suggested_price']),
            'product_details': product_details,
        })

    return JsonResponse({
        "data": {
            'property_id': prop.id,
            'property_address': prop.address,
            'square_feet': square_feet,
            'program_id': program.id,
            'program_name': program.name,
            'markup_pct': str(markup_pct),
            'base_fee': str(base_fee),
            'total_material_cost': str(result['total_material_cost']),
            'num_rounds': result['num_rounds'],
            'cost_per_round': str(result['cost_per_round']),
            'suggested_per_application': str(result['suggested_per_application']),
            'suggested_annual': str(result['suggested_annual']),
            'round_breakdown': round_breakdown,
        }
    })


@require_http_methods(["GET"])
@role_required("owner", "manager")
@module_required("fertilization")
def calculate_product(request):
    """GET: calculate lbs/bags/cost for a product on a given area."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    product_id = request.GET.get('product_id', '')
    square_feet_str = request.GET.get('square_feet', '')

    if not product_id or not square_feet_str:
        return JsonResponse({"error": "product_id and square_feet are required."}, status=400)

    product = get_object_or_404(FertilizerProduct, pk=product_id, business=biz)

    try:
        square_feet = Decimal(square_feet_str)
    except InvalidOperation:
        return JsonResponse({"error": "Invalid square_feet."}, status=400)

    # Use rate override from query param, or product default
    rate_str = request.GET.get('rate', '').strip()
    if rate_str:
        try:
            rate = Decimal(rate_str)
        except InvalidOperation:
            return JsonResponse({"error": "Invalid rate."}, status=400)
    elif product.application_rate:
        rate = product.application_rate
    else:
        return JsonResponse({"error": "No application rate available."}, status=400)

    lbs_needed = calculate_lbs_needed(rate, square_feet)
    bags_needed = calculate_bags_needed(lbs_needed, product.lbs_per_bag or 0) if product.lbs_per_bag else 0
    material_cost = product.calculate_cost(lbs_needed)

    return JsonResponse({
        "data": {
            'product_id': product.id,
            'product_name': product.name,
            'square_feet': str(square_feet),
            'rate': str(rate),
            'lbs_needed': str(lbs_needed),
            'bags_needed': bags_needed,
            'material_cost': str(material_cost),
        }
    })


@require_http_methods(["GET"])
@role_required("owner", "manager")
@module_required("fertilization")
def route_calculator(request):
    """GET: truck loading sheet for a given date — aggregate materials per product."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    date_str = request.GET.get('date', '')
    if not date_str:
        return JsonResponse({"error": "date is required."}, status=400)

    try:
        target_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    scheduled = ScheduledRound.objects.filter(
        enrollment__business=biz,
        scheduled_date=target_date,
    ).exclude(status='skipped').select_related(
        'enrollment__property__customer',
        'round_template',
    ).prefetch_related('round_template__products')

    # Aggregate products
    product_totals = {}  # product_id -> {product, total_lbs, total_cost, stops}
    stops = []

    for sr in scheduled:
        prop = sr.enrollment.property
        square_feet = prop.yard_sqft or 0
        stop_products = []

        if sr.round_template:
            for product in sr.round_template.products.all():
                rate = sr.round_template.default_rate_override or product.application_rate or Decimal('0')
                if rate and square_feet:
                    lbs = calculate_lbs_needed(rate, square_feet)
                    cost = product.calculate_cost(lbs)
                else:
                    lbs = Decimal('0')
                    cost = Decimal('0')

                if product.id not in product_totals:
                    product_totals[product.id] = {
                        'product_id': product.id,
                        'product_name': product.name,
                        'total_lbs': Decimal('0'),
                        'total_cost': Decimal('0'),
                        'stop_count': 0,
                    }
                product_totals[product.id]['total_lbs'] += lbs
                product_totals[product.id]['total_cost'] += cost
                product_totals[product.id]['stop_count'] += 1

                stop_products.append({
                    'product_name': product.name,
                    'lbs_needed': str(lbs),
                })

        stops.append({
            'scheduled_round_id': sr.id,
            'round_number': sr.round_number,
            'property_address': prop.address,
            'customer_name': prop.customer.name,
            'square_feet': prop.yard_sqft or 0,
            'products': stop_products,
        })

    materials = []
    for pt in product_totals.values():
        materials.append({
            'product_id': pt['product_id'],
            'product_name': pt['product_name'],
            'total_lbs': str(pt['total_lbs']),
            'total_cost': str(pt['total_cost']),
            'stop_count': pt['stop_count'],
        })

    return JsonResponse({
        "data": {
            'date': str(target_date),
            'total_stops': len(stops),
            'materials': materials,
            'stops': stops,
        }
    })


# ─────────────────────────────────────────────────────────────
#  Task 12 — Applications + Reports API
# ─────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def application_list_create(request):
    """GET: list applications with filters. POST: create application."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    if request.method == 'POST':
        property_id = request.POST.get('property_id', '').strip()
        product_id = request.POST.get('product_id', '').strip()
        application_date_str = request.POST.get('application_date', '').strip()
        pounds_used_str = request.POST.get('pounds_used', '').strip()

        if not property_id or not application_date_str or not pounds_used_str:
            return JsonResponse({"error": "property_id, application_date, and pounds_used are required."}, status=400)

        prop = get_object_or_404(Property, pk=property_id, customer__business=biz)

        try:
            application_date_val = date.fromisoformat(application_date_str)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid application_date. Use YYYY-MM-DD."}, status=400)

        try:
            pounds_used = Decimal(pounds_used_str)
        except InvalidOperation:
            return JsonResponse({"error": "Invalid pounds_used."}, status=400)

        product = None
        material_cost = Decimal('0')
        if product_id:
            product = get_object_or_404(FertilizerProduct, pk=product_id, business=biz)
            material_cost = product.calculate_cost(pounds_used)

        # Override material_cost if explicitly provided
        mc_str = request.POST.get('material_cost', '').strip()
        if mc_str:
            try:
                material_cost = Decimal(mc_str)
            except InvalidOperation:
                pass

        # Validate FK ownership for job, estimate, applied_by
        from jobs.models import Job
        from billing.models import Estimate

        job_id_str = request.POST.get('job_id', '').strip()
        job_pk, job_err = _validate_fk_ownership(Job, job_id_str, biz, "job_id") if job_id_str else (None, None)
        if job_err:
            return JsonResponse({"error": job_err}, status=400)

        estimate_id_str = request.POST.get('estimate_id', '').strip()
        estimate_pk, est_err = _validate_fk_ownership(Estimate, estimate_id_str, biz, "estimate_id") if estimate_id_str else (None, None)
        if est_err:
            return JsonResponse({"error": est_err}, status=400)

        applied_by_id_str = request.POST.get('applied_by_id', '').strip()
        applied_by_pk, ab_err = _validate_user_ownership(applied_by_id_str, biz)
        if ab_err:
            return JsonResponse({"error": ab_err}, status=400)

        app = FertilizerApplication.objects.create(
            business=biz,
            property=prop,
            product=product,
            job_id=job_pk,
            estimate_id=estimate_pk,
            application_date=application_date_val,
            pounds_used=pounds_used,
            square_feet=_dec_or_none(request, 'square_feet'),
            lbs_per_1000_sqft=_dec_or_none(request, 'lbs_per_1000_sqft'),
            material_cost=material_cost,
            charge_amount=_dec_or_none(request, 'charge_amount'),
            notes=request.POST.get('notes', '').strip(),
            weather_temp_f=_int_or_none(request, 'weather_temp_f'),
            weather_wind_mph=_dec_or_none(request, 'weather_wind_mph'),
            weather_conditions=request.POST.get('weather_conditions', '').strip(),
            applied_by_id=applied_by_pk,
        )
        # Refetch with select_related for serialization
        app = FertilizerApplication.objects.select_related(
            'property__customer', 'product', 'applied_by'
        ).get(pk=app.pk)
        return JsonResponse({"ok": True, "application": _application_to_dict(app)})

    # GET with filters
    qs = FertilizerApplication.objects.filter(
        business=biz
    ).select_related('property__customer', 'product', 'applied_by')

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    property_id = request.GET.get('property_id', '')
    product_id = request.GET.get('product_id', '')

    if start_date:
        try:
            qs = qs.filter(application_date__gte=date.fromisoformat(start_date))
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            qs = qs.filter(application_date__lte=date.fromisoformat(end_date))
        except (ValueError, TypeError):
            pass
    if property_id:
        qs = qs.filter(property_id=property_id)
    if product_id:
        qs = qs.filter(product_id=product_id)

    return JsonResponse({"items": [_application_to_dict(a) for a in qs[:200]]})


@require_http_methods(["GET", "POST"])
@role_required("owner", "manager")
@module_required("fertilization")
def application_detail(request, pk):
    """GET: single application. POST: update application."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    app = get_object_or_404(
        FertilizerApplication.objects.select_related('property__customer', 'product', 'applied_by'),
        pk=pk,
        business=biz,
    )

    if request.method == 'POST':
        if 'application_date' in request.POST:
            val = request.POST.get('application_date', '').strip()
            if val:
                try:
                    app.application_date = date.fromisoformat(val)
                except (ValueError, TypeError):
                    return JsonResponse({"error": "Invalid application_date."}, status=400)

        if 'pounds_used' in request.POST:
            val = request.POST.get('pounds_used', '').strip()
            if val:
                try:
                    app.pounds_used = Decimal(val)
                except InvalidOperation:
                    return JsonResponse({"error": "Invalid pounds_used."}, status=400)

        if 'product_id' in request.POST:
            pid = request.POST.get('product_id', '').strip()
            if pid:
                product = get_object_or_404(FertilizerProduct, pk=pid, business=biz)
                app.product = product
                # Recalculate material cost if not explicitly provided
                if 'material_cost' not in request.POST:
                    app.material_cost = product.calculate_cost(app.pounds_used)
            else:
                app.product = None

        for f in ('square_feet', 'lbs_per_1000_sqft', 'material_cost',
                   'charge_amount', 'weather_wind_mph'):
            if f in request.POST:
                val = request.POST.get(f, '').strip()
                if val:
                    try:
                        setattr(app, f, Decimal(val))
                    except InvalidOperation:
                        pass
                else:
                    setattr(app, f, None)

        if 'notes' in request.POST:
            app.notes = request.POST.get('notes', '')
        if 'weather_temp_f' in request.POST:
            val = request.POST.get('weather_temp_f', '').strip()
            if val:
                try:
                    app.weather_temp_f = int(val)
                except (ValueError, TypeError):
                    pass  # ignore invalid temp
            else:
                app.weather_temp_f = None
        if 'weather_conditions' in request.POST:
            app.weather_conditions = request.POST.get('weather_conditions', '').strip()
        if 'applied_by_id' in request.POST:
            val = request.POST.get('applied_by_id', '').strip()
            validated_pk, err = _validate_user_ownership(val, biz)
            if err:
                return JsonResponse({"error": err}, status=400)
            app.applied_by_id = validated_pk

        app.save()
        # Refresh relations after save
        app.refresh_from_db()
        app = FertilizerApplication.objects.select_related(
            'property__customer', 'product', 'applied_by'
        ).get(pk=app.pk)
        return JsonResponse({"ok": True, "application": _application_to_dict(app)})

    # GET
    return JsonResponse({"data": _application_to_dict(app)})


@require_http_methods(["GET"])
@role_required("owner", "manager")
@module_required("fertilization")
def report_compliance(request):
    """GET: CSV download of compliance report for date range."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    qs = FertilizerApplication.objects.filter(
        business=biz
    ).select_related('property__customer', 'product', 'applied_by').order_by('application_date')

    if start_date:
        try:
            qs = qs.filter(application_date__gte=date.fromisoformat(start_date))
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            qs = qs.filter(application_date__lte=date.fromisoformat(end_date))
        except (ValueError, TypeError):
            pass

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="compliance_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Property', 'Customer', 'Product', 'EPA #',
        'Lbs', 'Rate', 'SqFt', 'Applicator', 'Temp', 'Wind', 'Conditions',
    ])

    for app in qs:
        writer.writerow([
            str(app.application_date),
            app.property.address,
            app.property.customer.name,
            app.product.name if app.product else '',
            app.product.epa_registration_number if app.product else '',
            str(app.pounds_used),
            str(app.lbs_per_1000_sqft) if app.lbs_per_1000_sqft is not None else '',
            str(app.square_feet) if app.square_feet is not None else '',
            (app.applied_by.get_full_name() or app.applied_by.username) if app.applied_by else '',
            str(app.weather_temp_f) if app.weather_temp_f is not None else '',
            str(app.weather_wind_mph) if app.weather_wind_mph is not None else '',
            app.weather_conditions,
        ])

    return response


@require_http_methods(["GET"])
@role_required("owner", "manager")
@module_required("fertilization")
def report_profit(request):
    """GET: CSV download of profit report for date range."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    qs = FertilizerApplication.objects.filter(
        business=biz
    ).select_related('property__customer', 'product').order_by('application_date')

    if start_date:
        try:
            qs = qs.filter(application_date__gte=date.fromisoformat(start_date))
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            qs = qs.filter(application_date__lte=date.fromisoformat(end_date))
        except (ValueError, TypeError):
            pass

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="profit_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Property', 'Product', 'Material Cost', 'Charge', 'Profit', 'Margin%',
    ])

    for app in qs:
        profit = app.profit
        margin = app.profit_margin
        writer.writerow([
            str(app.application_date),
            app.property.address,
            app.product.name if app.product else '',
            str(app.material_cost),
            str(app.charge_amount) if app.charge_amount is not None else '',
            str(profit) if profit is not None else '',
            str(round(margin, 1)) if margin is not None else '',
        ])

    return response


@require_http_methods(["GET"])
@role_required("owner", "manager")
@module_required("fertilization")
def report_material_usage(request):
    """GET: CSV download of material usage aggregated by product."""
    biz, err = _biz_or_403(request)
    if err:
        return err

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    qs = FertilizerApplication.objects.filter(
        business=biz
    )

    if start_date:
        try:
            qs = qs.filter(application_date__gte=date.fromisoformat(start_date))
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            qs = qs.filter(application_date__lte=date.fromisoformat(end_date))
        except (ValueError, TypeError):
            pass

    # Aggregate by product
    product_agg = qs.values(
        'product__id', 'product__name'
    ).annotate(
        total_lbs=Sum('pounds_used'),
        total_cost=Sum('material_cost'),
        num_applications=Count('id'),
    ).order_by('product__name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="material_usage_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Product', 'Total Lbs', 'Total Cost', '# Applications',
    ])

    for row in product_agg:
        writer.writerow([
            row['product__name'] or 'Unknown',
            str(row['total_lbs'] or 0),
            str(row['total_cost'] or 0),
            row['num_applications'],
        ])

    return response


# ─────────────────────────────────────────────────────────────
#  Batch Schedule: create jobs from pending rounds
# ─────────────────────────────────────────────────────────────

@require_POST
@require_POST
@role_required("owner", "manager")
def update_enrollment_price(request):
    """Update per-application price for a fertilization enrollment (inline edit)."""
    from django.http import JsonResponse
    import json as _json
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    try:
        data = _json.loads(request.body)
    except _json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    enrollment_id = data.get("enrollment_id")
    price = data.get("price", "").strip() if data.get("price") else ""

    if not enrollment_id:
        return JsonResponse({"error": "Missing enrollment_id"}, status=400)

    enr = get_object_or_404(CustomerProgramEnrollment, id=enrollment_id, business=business)

    if price:
        from decimal import Decimal
        try:
            enr.price_per_application = Decimal(price)
            enr.save(update_fields=["price_per_application"])
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid price"}, status=400)
    else:
        enr.price_per_application = None
        enr.save(update_fields=["price_per_application"])

    return JsonResponse({"ok": True})


@role_required("owner", "manager")
@module_required("fertilization")
def batch_schedule_rounds(request):
    """Batch-create calendar jobs from selected pending fertilization rounds."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    round_ids = request.POST.getlist("round_ids")
    schedule_date_str = request.POST.get("schedule_date", "")
    round_template_id = request.POST.get("round_template_id", "").strip()

    # Deduplicate round IDs
    seen = set()
    unique_ids = []
    for rid in round_ids:
        if rid and rid not in seen:
            seen.add(rid)
            unique_ids.append(rid)

    if not unique_ids:
        messages.error(request, "No rounds selected.")
        return redirect("fertilization:hub")

    from django.db import transaction
    from jobs.models import Job, JobServiceItem
    from pricing.models import ServiceTemplate
    from pricing.utils import get_effective_rate

    fert_service = ServiceTemplate.objects.filter(
        business=business, active=True, name__icontains="fertil"
    ).first()
    if not fert_service:
        # Auto-create a fertilization service template
        fert_service = ServiceTemplate.objects.create(
            business=business,
            name="Fertilization",
            default_unit="visit",
            default_rate=0,
            pricing_method="flat",
            active=True,
        )

    target_date = None
    if schedule_date_str:
        try:
            target_date = date.fromisoformat(schedule_date_str)
        except (ValueError, TypeError):
            pass

    created = 0
    skipped = 0
    try:
        rounds_qs = ScheduledRound.objects.filter(
            id__in=unique_ids,
            enrollment__business=business,
            status='pending',
        ).select_related('enrollment__property__customer', 'enrollment__program', 'round_template')

        # If a specific round template was selected, filter to only those rounds
        if round_template_id:
            rounds_qs = rounds_qs.filter(round_template_id=round_template_id)

        rounds = rounds_qs

        for sr in rounds:
            # Double-check: skip if already has a job linked
            if sr.job_id:
                skipped += 1
                continue

            prop = sr.enrollment.property
            job_date = target_date or sr.scheduled_date

            round_name = sr.round_template.name if sr.round_template else f"Round {sr.round_number}"
            job = Job.objects.create(
                property=prop,
                scheduled_date=job_date,
                status="scheduled",
                notes=f"[Fertilization] {round_name} — {sr.enrollment.program.name} — {prop.customer.name}",
            )

            if fert_service:
                unit, rate = get_effective_rate(prop, fert_service)
                JobServiceItem.objects.create(
                    job=job,
                    service=fert_service,
                    description=f"{round_name} ({sr.enrollment.program.name})",
                    quantity=1,
                    unit=unit,
                    unit_price=sr.price if sr.price else rate,
                )

            sr.job = job
            sr.status = 'scheduled'
            sr.save(update_fields=['job', 'status'])
            created += 1
    except Exception as e:
        messages.error(request, f"Error scheduling: {e}")
        return redirect("fertilization:hub")

    msg = f"Scheduled {created} fertilization round{'' if created == 1 else 's'} on the calendar."
    if skipped:
        msg += f" ({skipped} already scheduled, skipped.)"
    messages.success(request, msg)
    return redirect("fertilization:hub")

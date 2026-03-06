"""Views for the fertilization management hub."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from accounts.decorators import role_required
from accounts.utils import get_business


# ─────────────────────────────────────────────────────────────
#  Hub view (fully functional)
# ─────────────────────────────────────────────────────────────

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
            'lawn_sqft': p.lawn_square_feet,
        }
        for p in properties
    ])

    programs_json = json.dumps([
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


# ─────────────────────────────────────────────────────────────
#  API view stubs — to be implemented in later tasks
# ─────────────────────────────────────────────────────────────

@role_required("owner", "manager")
def program_list_create(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def program_detail(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def program_delete(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def program_duplicate(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def round_list_create(request, program_id):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def round_update_delete(request, program_id, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def product_list_create(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def product_detail(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def enrollment_list_create(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def enrollment_detail(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def enrollment_cancel(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def calculate_pricing(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def calculate_product(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def route_calculator(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def application_list_create(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def application_detail(request, pk):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def report_compliance(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def report_profit(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)


@role_required("owner", "manager")
def report_material_usage(request):
    """Stub — implemented in a later task."""
    return JsonResponse({"status": "not_implemented"}, status=501)

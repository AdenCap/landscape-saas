from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods

from accounts.decorators import role_required
from accounts.utils import get_business
from .models import ServiceTemplate


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def service_pricing(request):
    """Manage service pricing — list all services, add new ones, edit rates."""
    business = get_business(request)
    if not business:
        return redirect("/")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = (request.POST.get("name") or "").strip()
            if not name:
                messages.error(request, "Service name is required.")
                return redirect("service_pricing")
            pricing_method = request.POST.get("pricing_method", "flat")
            default_rate = request.POST.get("default_rate") or "0"
            rate_per_sqft = request.POST.get("rate_per_sqft") or None
            min_price = request.POST.get("min_price") or None
            default_unit = request.POST.get("default_unit", "visit")
            pricing_notes = request.POST.get("pricing_notes", "")

            try:
                ServiceTemplate.objects.create(
                    business=business,
                    name=name,
                    pricing_method=pricing_method,
                    default_unit=default_unit,
                    default_rate=Decimal(default_rate),
                    rate_per_sqft=Decimal(rate_per_sqft) if rate_per_sqft else None,
                    min_price=Decimal(min_price) if min_price else None,
                    pricing_notes=pricing_notes,
                )
                messages.success(request, f"Service '{name}' created.")
            except (InvalidOperation, Exception) as e:
                messages.error(request, f"Error: {e}")

        elif action == "update":
            svc_id = request.POST.get("service_id")
            svc = get_object_or_404(ServiceTemplate, id=svc_id, business=business)
            svc.name = (request.POST.get("name") or svc.name).strip()
            svc.pricing_method = request.POST.get("pricing_method", svc.pricing_method)
            svc.default_unit = request.POST.get("default_unit", svc.default_unit)
            rate = request.POST.get("default_rate")
            if rate:
                try:
                    svc.default_rate = Decimal(rate)
                except InvalidOperation:
                    pass
            sqft_rate = request.POST.get("rate_per_sqft")
            svc.rate_per_sqft = Decimal(sqft_rate) if sqft_rate else None
            mp = request.POST.get("min_price")
            svc.min_price = Decimal(mp) if mp else None
            svc.pricing_notes = request.POST.get("pricing_notes", "")
            svc.active = request.POST.get("active") == "on"
            svc.save()
            messages.success(request, f"'{svc.name}' updated.")

        elif action == "delete":
            svc_id = request.POST.get("service_id")
            svc = get_object_or_404(ServiceTemplate, id=svc_id, business=business)
            name = svc.name
            svc.delete()
            messages.success(request, f"'{name}' deleted.")

        return redirect("service_pricing")

    services = ServiceTemplate.objects.filter(business=business).order_by("name")
    return render(request, "pricing/service_pricing.html", {
        "services": services,
    })

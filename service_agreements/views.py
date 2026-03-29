import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods

from accounts.decorators import role_required, module_required
from accounts.utils import get_business
from customers.models import Customer, Property
from jobs.models import Job, JobServiceItem
from pricing.models import ServiceTemplate
from pricing.utils import get_effective_rate
from .models import ServiceAgreement, AgreementVisit, AgreementLineItem


@login_required
@module_required("service_agreements")
def hub(request):
    biz = request.user.business
    agreements = ServiceAgreement.objects.filter(business=biz).select_related("customer").order_by("-created_at")
    return render(request, "service_agreements/hub.html", {
        "agreements": agreements,
    })


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def agreement_create(request):
    """Create a maintenance plan — define services + auto-schedule jobs on the calendar."""
    business = get_business(request)
    if not business:
        return redirect("/")

    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        property_id = request.POST.get("property_id")
        name = (request.POST.get("name") or "").strip()
        price = request.POST.get("price") or "0"
        notes = request.POST.get("notes", "")

        if not customer_id or not property_id or not name:
            messages.error(request, "Customer, property, and plan name are required.")
            return redirect("service_agreements:agreement_create")

        customer = get_object_or_404(Customer, id=customer_id, business=business)
        prop = get_object_or_404(Property, id=property_id, customer=customer)

        billing_freq = request.POST.get("billing_frequency", "annual")
        prepaid = request.POST.get("prepaid") == "on"
        prepaid_amount = request.POST.get("prepaid_amount", "").strip()
        start_date_str = request.POST.get("start_date", "")
        end_date_str = request.POST.get("end_date", "")

        try:
            start_dt = date.fromisoformat(start_date_str) if start_date_str else date.today()
        except (ValueError, TypeError):
            start_dt = date.today()
        try:
            end_dt = date.fromisoformat(end_date_str) if end_date_str else None
        except (ValueError, TypeError):
            end_dt = None

        agreement = ServiceAgreement.objects.create(
            business=business,
            customer=customer,
            name=name,
            agreement_type="maintenance",
            status="active",
            start_date=start_dt,
            end_date=end_dt,
            billing_frequency=billing_freq,
            price=Decimal(price) if price else Decimal("0"),
            prepaid=prepaid,
            prepaid_amount=Decimal(prepaid_amount) if prepaid_amount else None,
            notes=notes,
        )

        # Save line items
        line_names = request.POST.getlist("line_name")
        line_freqs = request.POST.getlist("line_frequency")
        line_qtys = request.POST.getlist("line_qty")
        line_prices = request.POST.getlist("line_price")
        line_expected = request.POST.getlist("line_expected")
        for i in range(len(line_names)):
            ln = (line_names[i] or "").strip()
            if not ln:
                continue
            qty = Decimal(line_qtys[i]) if i < len(line_qtys) and line_qtys[i] else Decimal("1")
            AgreementLineItem.objects.create(
                agreement=agreement,
                service_name=ln,
                frequency=line_freqs[i] if i < len(line_freqs) else "per_visit",
                quantity=qty,
                unit_price=Decimal(line_prices[i]) if i < len(line_prices) and line_prices[i] else Decimal("0"),
                times_expected=int(line_expected[i]) if i < len(line_expected) and line_expected[i] else None,
                order=i,
            )

        # Parse service visits from form
        visit_services = request.POST.getlist("visit_service")
        visit_months = request.POST.getlist("visit_month")
        visit_days = request.POST.getlist("visit_day")
        visit_notes = request.POST.getlist("visit_notes")

        jobs_created = 0
        year = date.today().year

        for i in range(len(visit_services)):
            svc_id = visit_services[i] if i < len(visit_services) else ""
            month = int(visit_months[i]) if i < len(visit_months) and visit_months[i] else 0
            day = int(visit_days[i]) if i < len(visit_days) and visit_days[i] else 15
            vnotes = visit_notes[i] if i < len(visit_notes) else ""

            if not svc_id or not month:
                continue

            service = ServiceTemplate.objects.filter(id=svc_id, business=business, active=True).first()
            if not service:
                continue

            # Calculate scheduled date
            try:
                sched_date = date(year, month, min(day, 28))
                # If date is in the past, schedule for next year
                if sched_date < date.today():
                    sched_date = date(year + 1, month, min(day, 28))
            except ValueError:
                sched_date = date(year, month, 15)

            # Create the job on the calendar
            job = Job.objects.create(
                property=prop,
                scheduled_date=sched_date,
                status="scheduled",
                notes=f"[{agreement.name}] {vnotes}".strip(),
            )

            # Add service line item
            unit, rate = get_effective_rate(prop, service)
            JobServiceItem.objects.create(
                job=job,
                service=service,
                description=service.name,
                quantity=1,
                unit=unit,
                unit_price=rate,
            )

            # Create agreement visit record
            AgreementVisit.objects.create(
                agreement=agreement,
                scheduled_date=sched_date,
                job=job,
                status="scheduled",
                notes=vnotes,
            )
            jobs_created += 1

        agreement.visits_included = jobs_created
        agreement.save(update_fields=["visits_included"])

        messages.success(request, f"Maintenance plan '{name}' created with {jobs_created} visits scheduled on the calendar.")
        return redirect("service_agreements:hub")

    # GET — build form context
    customers = Customer.objects.filter(business=business).prefetch_related('properties').order_by('name')
    services = ServiceTemplate.objects.filter(business=business, active=True).order_by('name')

    customers_data = []
    for c in customers:
        props = [{"id": p.id, "address": p.address, "sqft": p.yard_sqft} for p in c.properties.all()]
        customers_data.append({"id": c.id, "name": c.name, "properties": props})

    return render(request, "service_agreements/agreement_create.html", {
        "customers_json": json.dumps(customers_data),
        "services": services,
    })


@role_required("owner", "manager")
def agreement_detail(request, agreement_id):
    """View agreement details with all scheduled visits."""
    business = get_business(request)
    agreement = get_object_or_404(ServiceAgreement.objects.select_related('customer'), id=agreement_id, business=business)
    visits = agreement.visits.select_related('job').order_by('scheduled_date')
    return render(request, "service_agreements/agreement_detail.html", {
        "agreement": agreement,
        "visits": visits,
    })


@require_POST
@role_required("owner", "manager")
def agreement_delete(request, agreement_id):
    """Delete an agreement."""
    business = get_business(request)
    agreement = get_object_or_404(ServiceAgreement, id=agreement_id, business=business)
    name = agreement.name
    agreement.delete()
    messages.success(request, f"Agreement '{name}' deleted.")
    return redirect("service_agreements:hub")

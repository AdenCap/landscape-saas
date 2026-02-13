import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from accounts.decorators import role_required
from billing.services import create_draft_invoice_for_job, create_and_send_invoice_for_job
from billing.monthly import generate_monthly_invoice_for_customer
from .models import Job, JobServiceItem
from .forms import AddJobServiceItemForm, CreateJobForm, get_job_service_formset
from pricing.utils import get_effective_rate


def calendar_view(request):
    return render(request, 'jobs/calendar.html')


def calendar_events(request):
    jobs = Job.objects.select_related('property').all()
    events = [
        {
            "title": job.property.address,
            "start": job.scheduled_date.isoformat(),
        }
        for job in jobs
    ]
    return JsonResponse(events, safe=False)


def daily_route_view(request):
    # Optional: allow ?date=YYYY-MM-DD
    date_str = request.GET.get('date')
    if date_str:
        jobs = Job.objects.filter(scheduled_date=date_str)
    else:
        jobs = Job.objects.filter(scheduled_date=timezone.now().date())

    jobs = jobs.select_related('property', 'assigned_to').order_by('route_order')
    return render(request, 'jobs/daily_route.html', {"jobs": jobs})


@require_POST
def update_route_order(request):
    data = json.loads(request.body)
    for item in data:
        Job.objects.filter(id=item["id"]).update(route_order=item["order"])
    return JsonResponse({"status": "ok"})


@role_required("owner", "crew")
def crew_today_view(request):
    from time_tracking.models import TimeEntry

    today = timezone.now().date()

    jobs = Job.objects.filter(scheduled_date=today).select_related("property")

    if request.user.role == "crew":
        jobs = jobs.filter(assigned_to=request.user)

    jobs = jobs.order_by("route_order")

    # For clock in/out widget
    time_clock_current_entry = TimeEntry.objects.filter(
        user=request.user, clock_out__isnull=True
    ).order_by('-clock_in').first() if request.user.is_authenticated else None

    return render(request, "jobs/crew_today.html", {
        "jobs": jobs,
        "time_clock_current_entry": time_clock_current_entry,
    })

@require_POST
@role_required("owner", "crew")
def start_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    # Crew can only start their own jobs
    if request.user.role == "crew" and job.assigned_to_id != request.user.id:
        return redirect("crew_today")

    job.status = "in_progress"
    job.save()
    return redirect("crew_today")


@require_POST
@role_required("owner", "crew")
def complete_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    if request.user.role == "crew" and job.assigned_to_id != request.user.id:
        return redirect("crew_today")

    job.status = "completed"
    job.save()

    # Owner: choose billing (send now or add to monthly). Crew: done, owner bills later.
    if request.user.role == "owner":
        return redirect("job_billing_options", job_id=job_id)
    messages.success(request, "Job completed. The owner will handle billing.")
    return redirect("crew_today")

@role_required("owner")
def create_job(request):
    """Create a new landscaping job from the dashboard."""
    business = request.user.business
    if not business:
        messages.error(request, "You must be associated with a business to create jobs.")
        return redirect("owner_dashboard")

    if request.method == "POST":
        form = CreateJobForm(request.POST, business=business)
        ServiceFormSet = get_job_service_formset(business)
        formset = ServiceFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            prop = form.cleaned_data["property"]
            job = Job.objects.create(
                property=prop,
                scheduled_date=form.cleaned_data["scheduled_date"],
                assigned_to=form.cleaned_data.get("assigned_to"),
                notes=form.cleaned_data.get("notes") or "",
                status="scheduled",
            )
            for form_data in formset:
                if form_data.cleaned_data.get("service"):
                    service = form_data.cleaned_data["service"]
                    qty = form_data.cleaned_data["quantity"]
                    unit, rate = get_effective_rate(prop, service)
                    JobServiceItem.objects.create(
                        job=job,
                        service=service,
                        quantity=qty,
                        unit=unit,
                        unit_price=rate,
                    )
            messages.success(request, f"Job created for {prop.address} on {job.scheduled_date}.")
            return redirect("job_detail", job_id=job.id)
    else:
        form = CreateJobForm(business=business)
        ServiceFormSet = get_job_service_formset(business)
        formset = ServiceFormSet()

    return render(request, "jobs/job_create.html", {
        "form": form,
        "formset": formset,
    })


@role_required("owner")
def job_billing_options(request, job_id):
    """After job completion: choose to send invoice now or add to monthly."""
    job = get_object_or_404(Job, id=job_id)
    if job.status != "completed":
        return redirect("job_detail", job_id=job_id)

    return render(request, "jobs/job_billing_options.html", {
        "job": job,
        "customer": job.property.customer,
    })


@require_POST
@role_required("owner")
def job_bill_now(request, job_id):
    """Create and send invoice immediately for completed job."""
    job = get_object_or_404(Job, id=job_id)
    if job.status != "completed":
        messages.error(request, "Only completed jobs can be invoiced.")
        return redirect("job_detail", job_id=job_id)

    if not job.service_items.exists():
        messages.error(request, "Add at least one service to the job before invoicing.")
        return redirect("job_detail", job_id=job_id)

    create_and_send_invoice_for_job(job, send=True)
    messages.success(request, f"Invoice created and sent for {job.property.address}.")
    return redirect("billing:invoice_list")


@require_POST
@role_required("owner")
def job_add_to_monthly(request, job_id):
    """Add completed job to customer's monthly invoice."""
    job = get_object_or_404(Job, id=job_id)
    if job.status != "completed":
        messages.error(request, "Only completed jobs can be added to monthly invoice.")
        return redirect("job_detail", job_id=job_id)

    customer = job.property.customer
    d = job.scheduled_date
    invoice = generate_monthly_invoice_for_customer(customer, d.year, d.month)
    messages.success(
        request,
        f"Job added to {customer.name}'s monthly invoice for {d.strftime('%B %Y')}. "
        f"Invoice #{invoice.id} is in draft.",
    )
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@role_required("owner")
def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    # figure out business (adjust if your Property model stores business differently)
    business = getattr(job.property, "business", None)
    if business is None and hasattr(job.property, "customer") and hasattr(job.property.customer, "business"):
        business = job.property.customer.business

    form = AddJobServiceItemForm(business=business)

    has_unbilled = job.service_items.filter(billed_invoice__isnull=True).exists()
    return render(request, "jobs/job_detail.html", {
        "job": job,
        "form": form,
        "items": job.service_items.select_related("service").all(),
        "has_unbilled_items": has_unbilled,
    })


@require_POST
@role_required("owner")
def add_job_service_item(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    business = getattr(job.property, "business", None)
    if business is None and hasattr(job.property, "customer") and hasattr(job.property.customer, "business"):
        business = job.property.customer.business

    form = AddJobServiceItemForm(request.POST, business=business)
    if not form.is_valid():
        return redirect("job_detail", job_id=job.id)

    service = form.cleaned_data["service"]
    quantity = form.cleaned_data["quantity"]

    unit, rate = get_effective_rate(job.property, service)

    # If item already exists on job, update quantity (simple behavior)
    item, created = JobServiceItem.objects.get_or_create(
        job=job,
        service=service,
        defaults={"quantity": quantity, "unit": unit, "unit_price": rate},
    )
    if not created:
        item.quantity = quantity
        item.unit = unit
        item.unit_price = rate
        item.save()

    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner")
def remove_job_service_item(request, job_id, item_id):
    job = get_object_or_404(Job, id=job_id)
    JobServiceItem.objects.filter(id=item_id, job=job).delete()
    return redirect("job_detail", job_id=job.id)
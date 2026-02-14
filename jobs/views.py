import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from accounts.decorators import role_required
from billing.services import create_draft_invoice_for_job, create_and_send_invoice_for_job
from billing.monthly import generate_monthly_invoice_for_customer
from .models import Job, JobServiceItem, Crew
from .forms import AddJobServiceItemForm, CreateJobForm, get_job_service_formset
from pricing.utils import get_effective_rate
from accounts.models import User

CREW_COLORS = [
    '#3b82f6', '#22c55e', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]
UNASSIGNED_COLOR = '#94a3b8'


def _get_crew_legend(business):
    """Return list of {name, color} for calendar legend. Crews and employees with custom colors."""
    if not business:
        return [{"name": "Unassigned", "color": UNASSIGNED_COLOR}]
    legend = []
    for crew in Crew.objects.filter(business=business).order_by("name"):
        legend.append({"name": crew.name, "color": crew.color or CREW_COLORS[0]})
    for u in User.objects.filter(business=business, role="crew").order_by("first_name", "username"):
        c = (u.color or "").strip()
        legend.append({"name": u.get_full_name() or u.username, "color": c if c else CREW_COLORS[len(legend) % len(CREW_COLORS)]})
    legend.append({"name": "Unassigned", "color": UNASSIGNED_COLOR})
    return legend


def calendar_view(request):
    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    crew_legend = _get_crew_legend(business)
    return render(request, 'jobs/calendar.html', {'crew_legend': crew_legend})


def _color_for_assignee(job, crew_colors, user_colors):
    """Get color for job - crew or employee, using custom colors."""
    if job.assigned_crew_id:
        return crew_colors.get(job.assigned_crew_id) or (job.assigned_crew.color if job.assigned_crew else None) or UNASSIGNED_COLOR
    if job.assigned_to_id:
        c = user_colors.get(job.assigned_to_id)
        if c:
            return c
        if job.assigned_to and job.assigned_to.color:
            return job.assigned_to.color.strip()
        return CREW_COLORS[0]
    return UNASSIGNED_COLOR


def calendar_events(request):
    jobs = Job.objects.select_related('property', 'assigned_to', 'assigned_crew').all()

    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    if business:
        jobs = jobs.filter(property__customer__business=business)

    crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))} if business else {}
    user_colors = {}
    if business:
        for u in User.objects.filter(business=business, role="crew"):
            if u.color and u.color.strip():
                user_colors[u.id] = u.color.strip()

    events = []
    for job in jobs:
        base_color = _color_for_assignee(job, crew_colors, user_colors)
        is_completed = job.status == 'completed'
        if is_completed:
            bc = (base_color or '#94a3b8').lstrip('#')
            if len(bc) >= 6:
                r, g, b = int(bc[0:2], 16), int(bc[2:4], 16), int(bc[4:6], 16)
                bg = f'rgba({r},{g},{b},0.35)'
            else:
                bg = UNASSIGNED_COLOR
        else:
            bg = base_color or UNASSIGNED_COLOR

        if job.assigned_crew:
            assignee_name = job.assigned_crew.name
        elif job.assigned_to:
            assignee_name = job.assigned_to.get_full_name() or job.assigned_to.username
        else:
            assignee_name = 'Unassigned'

        title = job.property.address
        if is_completed:
            title = '✓ ' + title

        events.append({
            "id": job.id,
            "title": title,
            "start": job.scheduled_date.isoformat(),
            "backgroundColor": bg,
            "borderColor": base_color or UNASSIGNED_COLOR,
            "extendedProps": {
                "status": job.status,
                "crew": assignee_name,
                "jobId": job.id,
            },
        })
    return JsonResponse(events, safe=False)


@role_required("owner", "crew")
def daily_route_view(request):
    date_str = request.GET.get('date')
    if date_str:
        jobs = Job.objects.filter(scheduled_date=date_str)
    else:
        jobs = Job.objects.filter(scheduled_date=timezone.now().date())

    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    if business:
        jobs = jobs.filter(property__customer__business=business)

    jobs = jobs.select_related('property', 'assigned_to', 'assigned_crew').order_by('route_order')
    date_param = date_str or timezone.now().strftime('%Y-%m-%d')

    crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))} if business else {}
    user_colors = {}
    if business:
        for u in User.objects.filter(business=business, role="crew"):
            if u.color and u.color.strip():
                user_colors[u.id] = u.color.strip()
    jobs_with_colors = [{"job": j, "color": _color_for_assignee(j, crew_colors, user_colors)} for j in jobs]

    return render(request, 'jobs/daily_route.html', {
        "jobs": jobs,
        "jobs_with_colors": jobs_with_colors,
        "date_param": date_param,
    })


@require_POST
@role_required("owner")
def update_route_order(request):
    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    data = json.loads(request.body)
    for item in data:
        qs = Job.objects.filter(id=item["id"])
        if business:
            qs = qs.filter(property__customer__business=business)
        qs.update(route_order=item["order"])
    return JsonResponse({"status": "ok"})


@require_POST
@role_required("owner")
def optimize_route(request):
    """Reorder jobs by nearest-neighbor from first job (or centroid). Requires property lat/lng."""
    from math import sqrt

    date_str = request.POST.get("date") or request.GET.get("date")
    if date_str:
        jobs = list(Job.objects.filter(scheduled_date=date_str))
    else:
        jobs = list(Job.objects.filter(scheduled_date=timezone.now().date()))

    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    if business:
        jobs = [j for j in jobs if j.property.customer.business_id == business.id]

    if not jobs:
        return JsonResponse({"status": "ok", "message": "No jobs to optimize"})

    def has_coords(j):
        return j.property.latitude is not None and j.property.longitude is not None

    coords_jobs = [(j, float(j.property.latitude), float(j.property.longitude)) for j in jobs if has_coords(j)]
    if len(coords_jobs) < 2:
        return JsonResponse({"status": "ok", "message": "Need 2+ properties with lat/lng to optimize"})

    def dist(a, b):
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    remaining = set(range(len(coords_jobs)))
    order = [0]
    remaining.discard(0)
    current = coords_jobs[0]

    while remaining:
        best_idx = min(remaining, key=lambda i: dist(current[1:], coords_jobs[i][1:]))
        order.append(best_idx)
        remaining.discard(best_idx)
        current = coords_jobs[best_idx]

    for i, idx in enumerate(order):
        Job.objects.filter(id=coords_jobs[idx][0].id).update(route_order=i)

    return JsonResponse({"status": "ok", "message": "Route optimized"})


@role_required("owner", "crew")
def crew_today_view(request):
    from time_tracking.models import TimeEntry

    today = timezone.now().date()

    jobs = Job.objects.filter(scheduled_date=today).select_related("property", "assigned_to", "assigned_crew")

    if request.user.role == "crew":
        from django.db.models import Q
        jobs = jobs.filter(
            Q(assigned_to=request.user) |
            Q(assigned_crew__members=request.user)
        ).distinct()

    jobs = jobs.order_by("route_order")

    # For clock in/out widget
    time_clock_current_entry = TimeEntry.objects.filter(
        user=request.user, clock_out__isnull=True
    ).order_by('-clock_in').first() if request.user.is_authenticated else None

    return render(request, "jobs/crew_today.html", {
        "jobs": jobs,
        "time_clock_current_entry": time_clock_current_entry,
    })

def _user_can_access_job(user, job):
    """Crew can access if assigned to them or if they're in the assigned crew."""
    if user.role == "owner":
        return True
    if job.assigned_to_id == user.id:
        return True
    if job.assigned_crew_id and job.assigned_crew.members.filter(id=user.id).exists():
        return True
    return False


@require_POST
@role_required("owner", "crew")
def start_job(request, job_id):
    job = get_object_or_404(Job.objects.select_related("assigned_crew"), id=job_id)

    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        return redirect("crew_today")

    job.status = "in_progress"
    job.save()
    return redirect("crew_today")


@require_POST
@role_required("owner", "crew")
def complete_job(request, job_id):
    job = get_object_or_404(Job.objects.select_related("assigned_crew"), id=job_id)

    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
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
            atype = form.cleaned_data.get("assignee_type")
            assigned_to = None
            assigned_crew = None
            if atype == "crew":
                assigned_crew = form.cleaned_data.get("assigned_crew")
            elif atype == "employee":
                assigned_to = form.cleaned_data.get("assigned_to")

            job = Job.objects.create(
                property=prop,
                scheduled_date=form.cleaned_data["scheduled_date"],
                assigned_to=assigned_to,
                assigned_crew=assigned_crew,
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
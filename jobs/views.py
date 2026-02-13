import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.decorators import role_required
from billing.services import create_draft_invoice_for_job
from .models import Job, JobServiceItem
from .forms import AddJobServiceItemForm
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
    today = timezone.now().date()

    jobs = Job.objects.filter(scheduled_date=today).select_related("property")

    if request.user.role == "crew":
        jobs = jobs.filter(assigned_to=request.user)

    jobs = jobs.order_by("route_order")

    return render(request, "jobs/crew_today.html", {"jobs": jobs})

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

    # Create invoice draft (NOT sent)
    create_draft_invoice_for_job(job)

    return redirect("crew_today")

@role_required("owner")
def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    # figure out business (adjust if your Property model stores business differently)
    business = getattr(job.property, "business", None)
    if business is None and hasattr(job.property, "customer") and hasattr(job.property.customer, "business"):
        business = job.property.customer.business

    form = AddJobServiceItemForm(business=business)

    return render(request, "jobs/job_detail.html", {
        "job": job,
        "form": form,
        "items": job.service_items.select_related("service").all(),
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
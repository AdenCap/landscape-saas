import json
from datetime import datetime, timedelta

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
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
    for u in User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name", "username"):
        c = (u.color or "").strip()
        legend.append({"name": u.get_full_name() or u.username, "color": c if c else CREW_COLORS[len(legend) % len(CREW_COLORS)]})
    legend.append({"name": "Unassigned", "color": UNASSIGNED_COLOR})
    return legend


@role_required("owner", "crew")
def job_list(request):
    """List current and upcoming jobs (scheduled today or in the future), plus unscheduled."""
    business = getattr(request.user, 'business', None)
    if not business:
        return redirect("/")
    today = timezone.now().date()
    qs = Job.objects.filter(
        property__customer__business=business,
    ).select_related('property', 'property__customer', 'assigned_to', 'assigned_crew').prefetch_related('service_items__service').order_by('scheduled_date', 'scheduled_time', 'id')
    if getattr(request.user, 'role', None) == 'crew':
        qs = qs.filter(
            Q(assigned_to=request.user) |
            Q(assigned_crew__members=request.user) |
            Q(assigned_crew__crew_leader=request.user)
        ).distinct()
    upcoming = list(qs.filter(scheduled_date__gte=today))
    unscheduled = list(qs.filter(scheduled_date__isnull=True))[:30]
    return render(request, 'jobs/job_list.html', {
        'upcoming_jobs': upcoming,
        'unscheduled_jobs': unscheduled,
        'today': today,
    })


def calendar_view(request):
    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    crew_legend = _get_crew_legend(business)
    services = []
    crews = []
    if business:
        from pricing.models import ServiceTemplate
        services = list(ServiceTemplate.objects.filter(business=business, active=True).order_by("name").values("id", "name"))
        crews = list(Crew.objects.filter(business=business).order_by("name").values("id", "name"))
    return render(request, 'jobs/calendar.html', {
        'crew_legend': crew_legend,
        'filter_services': services,
        'filter_crews': crews,
    })


def _color_for_assignee(job, crew_colors, user_colors):
    """Get color for job - custom override, crew, or employee."""
    if job.color and job.color.strip():
        return job.color.strip()
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
    jobs = Job.objects.select_related(
        'property', 'property__customer', 'assigned_to', 'assigned_crew'
    ).prefetch_related('service_items__service').filter(scheduled_date__isnull=False)

    business = getattr(request.user, 'business', None) if request.user.is_authenticated else None
    if business:
        jobs = jobs.filter(property__customer__business=business)

    # Crew only sees jobs assigned to them or their crew
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'crew':
        user = request.user
        jobs = jobs.filter(
            Q(assigned_to=user) |
            Q(assigned_crew__members=user) |
            Q(assigned_crew__crew_leader=user)
        ).distinct()

    # Filters from query params
    service_ids = request.GET.get("services", "")
    crew_ids = request.GET.get("crews", "")
    if service_ids:
        ids = [int(x) for x in service_ids.split(",") if x.strip().isdigit()]
        if ids:
            jobs = jobs.filter(service_items__service_id__in=ids).distinct()
    if crew_ids:
        cids = [int(x) for x in crew_ids.split(",") if x.strip().isdigit()]
        if cids:
            jobs = jobs.filter(assigned_crew_id__in=cids)

    crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))} if business else {}
    user_colors = {}
    if business:
        for u in User.objects.filter(business=business, role__in=["crew", "owner"]):
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

        customer_name = job.property.customer.name if job.property.customer else ""
        service_names = list({si.service.name for si in job.service_items.select_related('service').all() if si.service})
        services_str = ", ".join(service_names) if service_names else "No services"

        title = job.property.address
        if is_completed:
            title = '✓ ' + title

        # Timed events (week/day view) vs all-day (month view)
        if job.scheduled_time:
            dt = datetime.combine(job.scheduled_date, job.scheduled_time)
            start_str = dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_dt = dt + timedelta(hours=1)
            end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            evt = {
                "id": job.id,
                "title": title,
                "start": start_str,
                "end": end_str,
                "backgroundColor": bg,
                "borderColor": base_color or UNASSIGNED_COLOR,
                "extendedProps": {
                    "status": job.status, "crew": assignee_name, "jobId": job.id,
                    "customer": customer_name, "services": services_str,
                },
            }
        else:
            evt = {
                "id": job.id,
                "title": title,
                "start": job.scheduled_date.isoformat(),
                "allDay": True,
                "backgroundColor": bg,
                "borderColor": base_color or UNASSIGNED_COLOR,
                "extendedProps": {
                    "status": job.status, "crew": assignee_name, "jobId": job.id,
                    "customer": customer_name, "services": services_str,
                },
            }
        events.append(evt)
    return JsonResponse(events, safe=False)


@require_GET
@login_required
def calendar_job_data(request, job_id):
    """Return job details for calendar modal. Owners get full data; crew get address, notes, services, images only."""
    business = getattr(request.user, 'business', None)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(
        Job.objects.select_related('property', 'property__customer', 'assigned_to', 'assigned_crew')
        .prefetch_related('service_items__service'),
        id=job_id,
        property__customer__business=business,
    )
    user_role = getattr(request.user, 'role', 'owner')
    is_owner = user_role == 'owner'

    # Crew may only view jobs assigned to them or their crew
    if not is_owner:
        can_view = (
            job.assigned_to_id == request.user.id or
            (job.assigned_crew and (
                request.user in job.assigned_crew.members.all() or
                job.assigned_crew.crew_leader_id == request.user.id
            ))
        )
        if not can_view:
            return JsonResponse({"error": "You do not have access to this job."}, status=403)

    # Services list (name, quantity, unit)
    services = [
        {"name": si.service.name if si.service else "—", "quantity": str(si.quantity), "unit": si.unit or "visit"}
        for si in job.service_items.select_related('service').all()
    ]

    # Property images from estimates (Property Estimator)
    images = []
    try:
        from property_estimator.models import PropertyEstimate
        for est in PropertyEstimate.objects.filter(property=job.property).prefetch_related('images'):
            for img in est.images.all():
                if img.image:
                    images.append({"url": img.image.url})
    except Exception:
        pass

    base_response = {
        "user_role": user_role,
        "job": {
            "id": job.id,
            "address": job.property.address,
            "scheduled_date": job.scheduled_date.isoformat() if job.scheduled_date else "",
            "scheduled_time": job.scheduled_time.strftime("%H:%M") if job.scheduled_time else "",
            "status": job.status,
            "notes": job.notes or "",
            "services": services,
            "images": images,
            "assigned_crew_id": job.assigned_crew_id if is_owner else None,
            "assigned_to_id": job.assigned_to_id if is_owner else None,
            "color": job.color or "",
            "has_unbilled_items": job.service_items.filter(billed_at__isnull=True).exists() if is_owner else False,
            "has_services": job.service_items.exists(),
        },
    }
    if is_owner:
        crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))}
        user_colors_map = {}
        for i, u in enumerate(User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name", "username")):
            if u.color and u.color.strip():
                user_colors_map[u.id] = u.color.strip()
            else:
                user_colors_map[u.id] = CREW_COLORS[i % len(CREW_COLORS)]
        crews = [{"id": c.id, "name": c.name, "color": crew_colors.get(c.id, CREW_COLORS[0])} for c in Crew.objects.filter(business=business).order_by("name")]
        employees = [
            {"id": u.id, "name": u.get_full_name() or u.username, "color": user_colors_map.get(u.id, CREW_COLORS[0])}
            for u in User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name", "username")
        ]
        customer = job.property.customer
        base_response["customer"] = {
            "name": customer.name,
            "email": customer.email or "",
            "phone": customer.phone or "",
        }
        base_response["crews"] = crews
        base_response["employees"] = employees
    return JsonResponse(base_response)


@require_POST
@role_required("owner")
def calendar_job_update(request, job_id):
    """Update job crew, notes, and customer contact from calendar modal."""
    business = getattr(request.user, 'business', None)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(
        Job.objects.select_related('property', 'property__customer'),
        id=job_id,
        property__customer__business=business,
    )
    data = json.loads(request.body) if request.body else {}
    # Crew and employee are mutually exclusive
    if "assigned_crew_id" in data:
        vid = data["assigned_crew_id"]
        if vid is None or vid == "":
            job.assigned_crew = None
        else:
            crew = Crew.objects.filter(business=business, id=vid).first()
            job.assigned_crew = crew
            job.assigned_to = None  # clear employee when crew selected
    if "assigned_to_id" in data:
        vid = data["assigned_to_id"]
        if vid is None or vid == "":
            job.assigned_to = None
        else:
            user = User.objects.filter(business=business, role__in=["crew", "owner"], id=vid).first()
            job.assigned_to = user
            job.assigned_crew = None  # clear crew when employee selected
    if "notes" in data:
        job.notes = (data["notes"] or "")[:2000]
    if "scheduled_time" in data:
        val = data["scheduled_time"]
        if val is None or val == "":
            job.scheduled_time = None
        elif isinstance(val, str) and ":" in val:
            parts = val.split(":")
            from datetime import time as dt_time
            h = int(parts[0] or 0)
            m = int(parts[1] or 0) if len(parts) > 1 else 0
            job.scheduled_time = dt_time(h, m, 0)
    if "customer_email" in data:
        job.property.customer.email = (data["customer_email"] or "")[:254]
        job.property.customer.save()
    if "customer_phone" in data:
        job.property.customer.phone = (data["customer_phone"] or "")[:20]
        job.property.customer.save()
    if "color" in data:
        val = (data["color"] or "").strip()
        if val:
            if not val.startswith("#"):
                val = "#" + val
            if len(val) in (4, 7) and all(c in "#0123456789abcdefABCDEF" for c in val):
                job.color = val
            else:
                job.color = None
        else:
            job.color = None  # Clear override = use crew/employee default
    job.save()

    # Return new color and assignee so calendar can update the event immediately
    business = getattr(request.user, 'business', None)
    crew_colors = {}
    user_colors = {}
    if business:
        crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))}
        for u in User.objects.filter(business=business, role__in=["crew", "owner"]):
            if u.color and u.color.strip():
                user_colors[u.id] = u.color.strip()
            else:
                user_colors[u.id] = CREW_COLORS[0]
    job.refresh_from_db()
    if job.assigned_crew:
        assignee_name = job.assigned_crew.name
    elif job.assigned_to:
        assignee_name = job.assigned_to.get_full_name() or job.assigned_to.username
    else:
        assignee_name = "Unassigned"
    color = _color_for_assignee(job, crew_colors, user_colors)
    is_completed = job.status == "completed"
    if is_completed and color:
        bc = color.lstrip("#")
        if len(bc) >= 6:
            r, g, b = int(bc[0:2], 16), int(bc[2:4], 16), int(bc[4:6], 16)
            bg = f"rgba({r},{g},{b},0.35)"
        else:
            bg = UNASSIGNED_COLOR
    else:
        bg = color or UNASSIGNED_COLOR
    return JsonResponse({
        "status": "ok",
        "backgroundColor": bg,
        "borderColor": color or UNASSIGNED_COLOR,
        "crew": assignee_name,
    })


@require_POST
@role_required("owner")
def calendar_job_reschedule(request, job_id):
    """Update job scheduled_date when dragged to new date."""
    business = getattr(request.user, 'business', None)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(
        Job,
        id=job_id,
        property__customer__business=business,
    )
    data = json.loads(request.body) if request.body else {}
    new_date = data.get("scheduled_date") or data.get("date")
    if not new_date:
        return JsonResponse({"error": "Missing scheduled_date"}, status=400)
    try:
        from datetime import time as dt_time
        date_str = new_date
        time_obj = None
        if isinstance(new_date, str) and "T" in new_date:
            parts = new_date.split("T")
            date_str = parts[0]
            if len(parts) > 1 and parts[1]:
                time_part = parts[1][:8]
                if ":" in time_part:
                    tparts = (time_part + ":0:0").split(":")[:3]
                    h, m, s = int(tparts[0] or 0), int(tparts[1] or 0), int(tparts[2] or 0)
                    time_obj = dt_time(h, m, s)
        job.scheduled_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        job.scheduled_time = time_obj
        job.save()
        return JsonResponse({"status": "ok", "scheduled_date": date_str})
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_GET
@role_required("owner")
def calendar_unscheduled_jobs(request):
    """List jobs with no scheduled_date (accepted but not yet on calendar)."""
    business = getattr(request.user, 'business', None)
    if not business:
        return JsonResponse({"jobs": []})
    jobs = Job.objects.filter(
        property__customer__business=business,
        scheduled_date__isnull=True,
    ).select_related('property', 'property__customer').prefetch_related('service_items__service').order_by('-created_at')[:50]
    out = []
    for j in jobs:
        services = list({si.service.name for si in j.service_items.all() if si.service})
        out.append({
            "id": j.id,
            "address": j.property.address,
            "customer": j.property.customer.name if j.property.customer else "",
            "services": ", ".join(services) if services else "No services",
            "status": j.status,
        })
    return JsonResponse({"jobs": out})


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
        for u in User.objects.filter(business=business, role__in=["crew", "owner"]):
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
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Forbidden"}, status=403)
        return redirect("crew_today")

    job.status = "completed"
    job.save()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "redirect": None})

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

            sched_date = form.cleaned_data.get("scheduled_date")
            sched_time = form.cleaned_data.get("scheduled_time") if sched_date else None
            color_val = (form.cleaned_data.get("color") or "").strip()
            if color_val and not color_val.startswith("#"):
                color_val = "#" + color_val
            if color_val and len(color_val) not in (4, 7):
                color_val = None
            job = Job.objects.create(
                property=prop,
                scheduled_date=sched_date,
                scheduled_time=sched_time,
                assigned_to=assigned_to,
                assigned_crew=assigned_crew,
                notes=form.cleaned_data.get("notes") or "",
                status="scheduled",
                color=color_val if color_val else None,
            )
            for form_data in formset:
                if form_data.cleaned_data.get("service"):
                    service = form_data.cleaned_data["service"]
                    qty = form_data.cleaned_data["quantity"]
                    unit, rate = get_effective_rate(prop, service)
                    override_price = form_data.cleaned_data.get("unit_price")
                    if override_price is not None:
                        rate = override_price
                    unit = getattr(service, "default_unit", None) or unit
                    JobServiceItem.objects.create(
                        job=job,
                        service=service,
                        quantity=qty,
                        unit=unit,
                        unit_price=rate,
                    )
            msg = f"Job created for {prop.address}" + (f" on {job.scheduled_date}" if job.scheduled_date else " (unscheduled)")
            messages.success(request, msg + ".")
            if job.scheduled_date:
                return redirect("job_detail", job_id=job.id)
            return redirect("calendar")
    else:
        from customers.models import Property
        initial = {}
        date_param = request.GET.get("date")
        time_param = request.GET.get("time")
        estimate_id = request.GET.get("estimate")
        if estimate_id:
            estimate_id = str(estimate_id).strip()

        if date_param:
            initial["scheduled_date"] = date_param
            initial["scheduled_time"] = time_param if time_param else "08:00"

        formset_initial = []
        if estimate_id and business:
            from billing.models import Estimate
            est = Estimate.objects.filter(
                id=estimate_id, business=business, status="accepted"
            ).select_related("customer").prefetch_related("line_items").first()
            if est:
                initial["customer"] = est.customer_id
                props = list(est.customer.properties.all().order_by("address")[:1])
                if len(props) == 1:
                    initial["property"] = props[0].id
                for item in est.line_items.all():
                    if item.material_cost or item.labor_cost:
                        price = (item.material_cost or 0) + (item.labor_cost or 0)
                        if item.quantity and item.quantity > 0:
                            price = price / item.quantity
                    else:
                        price = item.unit_price
                    formset_initial.append({
                        "service_name": item.description[:120],
                        "quantity": item.quantity,
                        "unit_price": price,
                    })

        form = CreateJobForm(initial=initial, business=business)
        if initial.get("customer") and business:
            form.fields["property"].queryset = Property.objects.filter(
                customer_id=initial["customer"], customer__business=business
            ).order_by("address")
        ServiceFormSet = get_job_service_formset(business)
        formset = ServiceFormSet(initial=formset_initial) if formset_initial else ServiceFormSet()

    from pricing.models import ServiceTemplate
    from customers.models import Customer
    from billing.models import Estimate
    service_templates = []
    customers_with_properties = []
    accepted_estimates = []
    if business:
        service_templates = list(ServiceTemplate.objects.filter(business=business, active=True).order_by("name").values("name"))
        customers_with_properties = [
            {
                "id": c.id,
                "name": c.name,
                "properties": [{"id": p.id, "address": p.address} for p in c.properties.all().order_by("address")],
            }
            for c in Customer.objects.filter(business=business).prefetch_related("properties").order_by("name")
        ]
        accepted_estimates = [
            {"id": e.id, "title": e.title, "total": e.base_total(), "customer_id": e.customer_id, "customer_name": e.customer.name}
            for e in Estimate.objects.filter(business=business, status="accepted")
            .select_related("customer").order_by("-accepted_at", "-id")[:20]
        ]
    return render(request, "jobs/job_create.html", {
        "form": form,
        "formset": formset,
        "service_templates": service_templates,
        "customers_with_properties": customers_with_properties,
        "accepted_estimates": accepted_estimates,
        "loaded_estimate_id": estimate_id if estimate_id else None,
    })


@require_POST
@role_required("owner")
def job_delete(request, job_id):
    """Delete a job."""
    business = getattr(request.user, "business", None)
    if not business:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "No business"}, status=403)
        return redirect("/")
    job = get_object_or_404(
        Job,
        id=job_id,
        property__customer__business=business,
    )
    job.delete()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    messages.success(request, "Job deleted.")
    return redirect("calendar")


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
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Only completed jobs can be invoiced."}, status=400)
        messages.error(request, "Only completed jobs can be invoiced.")
        return redirect("job_detail", job_id=job_id)

    if not job.service_items.exists():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Add at least one service before invoicing."}, status=400)
        messages.error(request, "Add at least one service to the job before invoicing.")
        return redirect("job_detail", job_id=job_id)

    create_and_send_invoice_for_job(job, send=True)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    messages.success(request, f"Invoice created and sent for {job.property.address}.")
    return redirect("billing:invoice_list")


@require_POST
@role_required("owner")
def job_add_to_monthly(request, job_id):
    """Add completed job to customer's monthly invoice."""
    job = get_object_or_404(Job, id=job_id)
    if job.status != "completed":
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Only completed jobs can be added to monthly."}, status=400)
        messages.error(request, "Only completed jobs can be added to monthly invoice.")
        return redirect("job_detail", job_id=job_id)

    d = job.scheduled_date or timezone.now().date()
    customer = job.property.customer
    invoice = generate_monthly_invoice_for_customer(customer, d.year, d.month, include_job=job)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "invoice_id": invoice.id})
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
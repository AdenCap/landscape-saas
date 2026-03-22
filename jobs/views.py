import json
from datetime import date, datetime, timedelta
from urllib.parse import quote

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import role_required
from accounts.utils import get_business
from accounts.models import Notification
from billing.services import create_draft_invoice_for_job
from billing.monthly import generate_monthly_invoice_for_customer
from .models import Job, JobServiceItem, Crew, RecurringJob, JobIssue, JobIssuePhoto, JobCompletionPhoto, JobPhoto, JobAssignmentLog, Meeting, JobNote, PropertyNote
from customers.models import Property
from .forms import AddJobServiceItemForm, CreateJobForm, get_job_service_formset, ReportIssueForm, MeetingForm
from pricing.utils import get_effective_rate
from accounts.models import User

CREW_COLORS = [
    '#22c55e', '#22c55e', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]
UNASSIGNED_COLOR = '#94a3b8'

# Status-based calendar colors (default when no custom color set)
STATUS_COLORS = {
    'scheduled': '#3b82f6',    # Blue
    'in_progress': '#f59e0b',  # Amber
    'completed': '#22c55e',    # Green
    'skipped': '#6b7280',      # Gray
    'cancelled': '#6b7280',    # Gray
}


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


def _get_job_details(job):
    """Get job title, amount, and payment status for display."""
    from decimal import Decimal
    
    # Job title: use services if available, otherwise property address
    services = list(job.service_items.select_related('service').all())
    if services:
        service_names = [si.service.name if si.service else "Service" for si in services[:3]]
        title = ", ".join(service_names)
        if len(services) > 3:
            title += f" +{len(services) - 3} more"
    else:
        title = job.property.address
    
    # Calculate job amount from service items
    job_amount = Decimal("0")
    for si in services:
        job_amount += si.line_total()
    
    # Check payment status from invoice
    is_paid = False
    invoice_status = None
    if hasattr(job, 'invoice') and job.invoice:
        invoice_status = job.invoice.status
        is_paid = job.invoice.status == 'paid'
    
    return {
        'title': title,
        'amount': job_amount,
        'is_paid': is_paid,
        'invoice_status': invoice_status,
    }


@role_required("owner", "manager", "crew")
def job_list(request):
    """
    List jobs with filtering options:
    - Default: upcoming jobs (today and future) + unscheduled
    - Filter by: past 7 days, past 30 days, this month, specific date, or all completed jobs
    """
    business = get_business(request)
    if not business:
        return redirect("/")
    today = timezone.now().date()
    
    # Base queryset
    qs = Job.objects.filter(
        property__customer__business=business,
    ).select_related('property', 'property__customer', 'assigned_to', 'assigned_crew', 'completed_by', 'invoice').prefetch_related('service_items__service')
    
    # Crew filter: only see jobs assigned to them
    if getattr(request.user, 'role', None) == 'crew':
        qs = qs.filter(
            Q(assigned_to=request.user) |
            Q(assigned_crew__members=request.user) |
            Q(assigned_crew__crew_leader=request.user)
        ).distinct()
    
    # Get filter parameter
    filter_type = request.GET.get('filter', '').strip()
    filter_date = request.GET.get('date', '').strip()
    
    upcoming = []
    past_jobs = []
    unscheduled = []
    filter_label = "Upcoming"
    
    if filter_type == 'past_7_days':
        start_date = today - timedelta(days=7)
        past_jobs = list(qs.filter(
            scheduled_date__gte=start_date,
            scheduled_date__lt=today
        ).order_by('-scheduled_date', 'scheduled_time', 'id'))
        filter_label = "Past 7 Days"
    elif filter_type == 'past_30_days':
        start_date = today - timedelta(days=30)
        past_jobs = list(qs.filter(
            scheduled_date__gte=start_date,
            scheduled_date__lt=today
        ).order_by('-scheduled_date', 'scheduled_time', 'id'))
        filter_label = "Past 30 Days"
    elif filter_type == 'this_month':
        month_start = today.replace(day=1)
        past_jobs = list(qs.filter(
            scheduled_date__gte=month_start,
            scheduled_date__lt=today
        ).order_by('-scheduled_date', 'scheduled_time', 'id'))
        filter_label = "This Month (Past)"
    elif filter_type == 'completed':
        # All completed jobs, regardless of date
        past_jobs = list(qs.filter(
            status='completed'
        ).order_by('-scheduled_date', 'scheduled_time', 'id'))
        filter_label = "All Completed Jobs"
    elif filter_type == 'date' and filter_date:
        # Specific date filter
        try:
            from datetime import datetime as dt
            target_date = dt.strptime(filter_date, '%Y-%m-%d').date()
            past_jobs = list(qs.filter(
                scheduled_date=target_date
            ).order_by('scheduled_time', 'id'))
            filter_label = f"Jobs on {target_date.strftime('%B %d, %Y')}"
        except (ValueError, TypeError):
            # Invalid date, fall back to default
            pass
    
    # Default: show upcoming and unscheduled
    unscheduled_with_details = []
    if not filter_type:
        upcoming_qs = qs.filter(scheduled_date__gte=today).order_by('scheduled_date', 'scheduled_time', 'id')
        upcoming = list(upcoming_qs)
        unscheduled_qs = qs.filter(scheduled_date__isnull=True).order_by('-created_at')[:30]
        for job in unscheduled_qs:
            details = _get_job_details(job)
            unscheduled_with_details.append({
                'job': job,
                'title': details['title'],
                'amount': details['amount'],
                'is_paid': details['is_paid'],
                'invoice_status': details['invoice_status'],
            })
    
    # Get counts for filter badges
    completed_count = qs.filter(status='completed').count()
    past_7_days_count = qs.filter(scheduled_date__gte=today - timedelta(days=7), scheduled_date__lt=today).count()
    past_30_days_count = qs.filter(scheduled_date__gte=today - timedelta(days=30), scheduled_date__lt=today).count()
    month_start = today.replace(day=1)
    this_month_past_count = qs.filter(scheduled_date__gte=month_start, scheduled_date__lt=today).count()
    
    # Add job details to all job lists
    upcoming_with_details = []
    for job in upcoming:
        details = _get_job_details(job)
        upcoming_with_details.append({
            'job': job,
            'title': details['title'],
            'amount': details['amount'],
            'is_paid': details['is_paid'],
            'invoice_status': details['invoice_status'],
        })
    
    past_jobs_with_details = []
    for job in past_jobs:
        details = _get_job_details(job)
        past_jobs_with_details.append({
            'job': job,
            'title': details['title'],
            'amount': details['amount'],
            'is_paid': details['is_paid'],
            'invoice_status': details['invoice_status'],
        })
    
    return render(request, 'jobs/job_list.html', {
        'upcoming_jobs': upcoming_with_details,
        'past_jobs': past_jobs_with_details,
        'unscheduled_jobs': unscheduled_with_details,
        'today': today,
        'filter_type': filter_type,
        'filter_date': filter_date,
        'filter_label': filter_label,
        'completed_count': completed_count,
        'past_7_days_count': past_7_days_count,
        'past_30_days_count': past_30_days_count,
        'this_month_past_count': this_month_past_count,
    })


@role_required("owner", "manager", "crew")
def calendar_view(request):
    business = get_business(request) if request.user.is_authenticated else None
    crew_legend = _get_crew_legend(business)
    services = []
    crews = []
    employees = []
    weather_forecast = []
    if business:
        from pricing.models import ServiceTemplate
        services = list(ServiceTemplate.objects.filter(business=business, active=True).order_by("name").values("id", "name"))
        crews = list(Crew.objects.filter(business=business).order_by("name").values("id", "name"))
        employees = [
            {"id": u.id, "name": u.get_full_name() or u.username}
            for u in User.objects.filter(business=business).exclude(role="client").order_by("first_name", "last_name")
        ]
        # Fetch weather forecast for the business location
        from jobs.weather import get_forecast, get_business_location
        location = get_business_location(business)
        if location:
            weather_forecast = get_forecast(location[0], location[1])
    return render(request, 'jobs/calendar.html', {
        'crew_legend': crew_legend,
        'filter_services': services,
        'filter_crews': crews,
        'filter_employees': employees,
        'weather_forecast': weather_forecast,
    })


def _color_for_assignee(job, crew_colors, user_colors):
    """Get color for job: custom override > status-based default.
    Crew/employee colors are still used as the crew dot indicator."""
    if job.color and job.color.strip():
        return job.color.strip()
    # Default: use status-based coloring
    return STATUS_COLORS.get(job.status, STATUS_COLORS.get('scheduled', '#3b82f6'))


def _crew_color_for_job(job, crew_colors, user_colors):
    """Get crew/employee color for the dot indicator on event cards."""
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


@login_required
def calendar_events(request):
    jobs = Job.objects.select_related(
        'property', 'property__customer', 'assigned_to', 'assigned_crew',
        'recurring_job'
    ).prefetch_related('service_items__service', 'assigned_employees').filter(scheduled_date__isnull=False)

    business = get_business(request) if request.user.is_authenticated else None
    if business:
        jobs = jobs.filter(property__customer__business=business)

    # Crew only sees jobs assigned to them or their crew
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'crew':
        user = request.user
        jobs = jobs.filter(
            Q(assigned_to=user) |
            Q(assigned_employees=user) |
            Q(assigned_crew__members=user) |
            Q(assigned_crew__crew_leader=user)
        ).distinct()

    # Filters from query params
    service_ids = request.GET.get("services", "")
    crew_ids = request.GET.get("crews", "")
    employee_ids = request.GET.get("employees", "")
    if service_ids:
        ids = [int(x) for x in service_ids.split(",") if x.strip().isdigit()]
        if ids:
            jobs = jobs.filter(service_items__service_id__in=ids).distinct()
    if crew_ids:
        cids = [int(x) for x in crew_ids.split(",") if x.strip().isdigit()]
        if cids:
            jobs = jobs.filter(assigned_crew_id__in=cids)
    if employee_ids:
        eids = [int(x) for x in employee_ids.split(",") if x.strip().isdigit()]
        if eids:
            jobs = jobs.filter(
                Q(assigned_to_id__in=eids) | Q(assigned_employees__id__in=eids)
            ).distinct()

    search = (request.GET.get("search") or "").strip()
    if search:
        jobs = jobs.filter(
            Q(property__address__icontains=search)
            | Q(property__customer__name__icontains=search)
            | Q(service_items__service__name__icontains=search)
        ).distinct()

    crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))} if business else {}
    user_colors = {}
    if business:
        for u in User.objects.filter(business=business, role__in=["crew", "owner"]):
            if u.color and u.color.strip():
                user_colors[u.id] = u.color.strip()

    events = []
    for job in jobs:
        base_color = _color_for_assignee(job, crew_colors, user_colors)
        crew_dot_color = _crew_color_for_job(job, crew_colors, user_colors)
        is_completed = job.status == 'completed'
        bg = base_color or STATUS_COLORS.get('scheduled', '#3b82f6')

        if job.assigned_crew:
            assignee_name = job.assigned_crew.name
        elif job.assigned_to:
            # Check for multiple assigned employees
            all_employees = list(job.assigned_employees.all())
            if len(all_employees) > 1:
                assignee_name = ", ".join(
                    (e.get_full_name() or e.username) for e in all_employees
                )
            else:
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
                "id": str(job.id),
                "title": title,
                "start": start_str,
                "end": end_str,
                "backgroundColor": bg,
                "borderColor": bg,
                "extendedProps": {
                    "status": job.status, "crew": assignee_name, "jobId": job.id,
                    "customer": customer_name, "services": services_str,
                    "crewColor": crew_dot_color,
                    "statusColor": STATUS_COLORS.get(job.status, '#3b82f6'),
                    "assigneeColor": crew_dot_color,
                    "jobColorOverride": job.color.strip() if job.color and job.color.strip() else None,
                    "serviceAbbr": service_names[0] if service_names else "",
                    "recurring": bool(job.recurring_job_id),
                    "frequency": job.recurring_job.frequency if job.recurring_job_id else None,
                },
            }
        else:
            evt = {
                "id": str(job.id),
                "title": title,
                "start": job.scheduled_date.isoformat(),
                "allDay": True,
                "backgroundColor": bg,
                "borderColor": bg,
                "extendedProps": {
                    "status": job.status, "crew": assignee_name, "jobId": job.id,
                    "customer": customer_name, "services": services_str,
                    "crewColor": crew_dot_color,
                    "statusColor": STATUS_COLORS.get(job.status, '#3b82f6'),
                    "assigneeColor": crew_dot_color,
                    "jobColorOverride": job.color.strip() if job.color and job.color.strip() else None,
                    "serviceAbbr": service_names[0] if service_names else "",
                    "recurring": bool(job.recurring_job_id),
                    "frequency": job.recurring_job.frequency if job.recurring_job_id else None,
                },
            }
        events.append(evt)

    # Owner-only: add meetings to calendar
    if business and getattr(request.user, "role", None) in ("owner", "manager"):
        meetings = Meeting.objects.filter(business=business).select_related("customer").order_by("scheduled_at")
        if search:
            meetings = meetings.filter(
                Q(title__icontains=search) | Q(customer__name__icontains=search)
            )
        meeting_color = "#7c3aed"
        for m in meetings:
            start_dt = m.scheduled_at
            end_dt = start_dt + timedelta(minutes=m.duration_minutes or 60)
            start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            customer_name = m.customer.name if m.customer else ""
            evt = {
                "id": "m-%s" % m.id,
                "title": m.title,
                "start": start_str,
                "end": end_str,
                "backgroundColor": meeting_color,
                "borderColor": meeting_color,
                "extendedProps": {
                    "type": "meeting",
                    "meetingId": m.id,
                    "customer": customer_name,
                },
            }
            events.append(evt)

    return JsonResponse(events, safe=False)


@require_GET
@login_required
def calendar_job_data(request, job_id):
    """Return job details for calendar modal. Owners get full data; crew get address, notes, services, images only."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(
        Job.objects.select_related('property', 'property__customer', 'assigned_to', 'assigned_crew')
        .prefetch_related('service_items__service'),
        id=job_id,
        property__customer__business=business,
    )
    user_role = getattr(request.user, 'role', 'owner')
    is_owner = user_role in ('owner', 'manager')

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
            "assigned_employee_ids": list(job.assigned_employees.values_list('id', flat=True)) if is_owner else [],
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
@role_required("owner", "manager")
def calendar_job_update(request, job_id):
    """Update job crew, notes, and customer contact from calendar modal."""
    business = get_business(request)
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
            job.assigned_employees.clear()
        else:
            user = User.objects.filter(business=business, role__in=["crew", "owner"], id=vid).first()
            job.assigned_to = user
            job.assigned_crew = None  # clear crew when employee selected
            # Add to M2M if not already there
            if user and not job.assigned_employees.filter(id=user.id).exists():
                job.assigned_employees.add(user)
    if "assigned_employee_ids" in data:
        eids = data["assigned_employee_ids"]
        if isinstance(eids, list):
            employees = User.objects.filter(business=business, role__in=["crew", "owner"], id__in=eids)
            job.assigned_employees.set(employees)
            if employees.exists():
                job.assigned_to = employees.first()
                job.assigned_crew = None
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

    if "assigned_crew_id" in data or "assigned_to_id" in data:
        assignee = job.assigned_crew.name if job.assigned_crew else (job.assigned_to.get_full_name() or job.assigned_to.username if job.assigned_to else "Unassigned")
        JobAssignmentLog.objects.create(
            job=job,
            user=request.user,
            details=f"Assignment set to {assignee} (from calendar)",
        )

    # Return new color and assignee so calendar can update the event immediately
    business = get_business(request)
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
    bg = color or STATUS_COLORS.get('scheduled', '#3b82f6')
    return JsonResponse({
        "status": "ok",
        "backgroundColor": bg,
        "borderColor": bg,
        "crew": assignee_name,
    })


@require_POST
@role_required("owner", "manager")
def calendar_job_reschedule(request, job_id):
    """Update job scheduled_date when dragged to new date."""
    business = get_business(request)
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


@require_POST
@role_required("owner", "manager")
def calendar_bulk_reschedule(request):
    """Bulk reschedule jobs from one date to another (rain day push)."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    data = json.loads(request.body) if request.body else {}
    from_date = data.get("from_date")
    to_date = data.get("to_date")
    job_ids = data.get("job_ids", [])
    skip_weekends = data.get("skip_weekends", False)
    if not from_date or not to_date:
        return JsonResponse({"error": "Missing from_date or to_date"}, status=400)
    try:
        from_d = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_d = datetime.strptime(to_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid date format"}, status=400)
    # If skip_weekends, advance Saturday/Sunday to Monday
    if skip_weekends:
        while to_d.weekday() >= 5:
            to_d += timedelta(days=1)
        to_date = to_d.strftime("%Y-%m-%d")
    jobs = Job.objects.filter(
        property__customer__business=business,
        scheduled_date=from_d,
        status__in=["scheduled", "in_progress"],
    )
    if job_ids:
        jobs = jobs.filter(id__in=job_ids)
    count = jobs.update(scheduled_date=to_d)
    return JsonResponse({"moved": count, "to_date": to_date})


@require_POST
@role_required("owner", "manager")
def calendar_quick_create(request):
    """Create a job from the calendar quick-create popover (Google Calendar style)."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    data = json.loads(request.body) if request.body else {}
    customer_id = data.get("customer_id")
    property_id = data.get("property_id")
    service_id = data.get("service_id")
    scheduled_date_str = data.get("scheduled_date")
    scheduled_time_str = data.get("scheduled_time")
    assigned_crew_id = data.get("assigned_crew_id")
    assigned_to_id = data.get("assigned_to_id")
    color = data.get("color")
    notes = data.get("notes", "")

    if not customer_id or not property_id or not service_id or not scheduled_date_str:
        return JsonResponse({"error": "Customer, property, service, and date are required"}, status=400)

    from customers.models import Customer
    customer = Customer.objects.filter(business=business, id=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)
    prop = Property.objects.filter(customer=customer, id=property_id).first()
    if not prop:
        return JsonResponse({"error": "Property not found"}, status=404)
    from pricing.models import ServiceTemplate
    service = ServiceTemplate.objects.filter(business=business, id=service_id, active=True).first()
    if not service:
        return JsonResponse({"error": "Service not found"}, status=404)

    try:
        sched_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid date format"}, status=400)

    sched_time = None
    if scheduled_time_str and ":" in str(scheduled_time_str):
        try:
            from datetime import time as dt_time
            parts = scheduled_time_str.split(":")
            sched_time = dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, TypeError):
            pass

    # Validate color
    job_color = None
    if color and isinstance(color, str):
        c = color.strip()
        if not c.startswith("#"):
            c = "#" + c
        if len(c) in (4, 7) and all(ch in "#0123456789abcdefABCDEF" for ch in c):
            job_color = c

    job = Job.objects.create(
        property=prop,
        scheduled_date=sched_date,
        scheduled_time=sched_time,
        status="scheduled",
        color=job_color,
        notes=(notes or "")[:2000],
    )

    # Assignment
    if assigned_crew_id:
        crew = Crew.objects.filter(business=business, id=assigned_crew_id).first()
        if crew:
            job.assigned_crew = crew
            job.save(update_fields=["assigned_crew"])
    elif assigned_to_id:
        user = User.objects.filter(business=business, role__in=["crew", "owner"], id=assigned_to_id).first()
        if user:
            job.assigned_to = user
            job.assigned_employees.add(user)
            job.save(update_fields=["assigned_to"])

    # Create service item with pricing
    unit, rate = get_effective_rate(prop, service)
    JobServiceItem.objects.create(
        job=job,
        service=service,
        description=service.name,
        quantity=1,
        unit=unit,
        unit_price=rate,
    )

    # Log assignment
    if job.assigned_crew or job.assigned_to:
        assignee = job.assigned_crew.name if job.assigned_crew else (job.assigned_to.get_full_name() if job.assigned_to else "Unassigned")
        JobAssignmentLog.objects.create(
            job=job,
            user=request.user,
            details=f"Job created and assigned to {assignee} (from calendar quick-create)",
        )

    return JsonResponse({"status": "ok", "job_id": job.id})


@require_GET
@role_required("owner", "manager")
def calendar_customer_search(request):
    """Search customers for calendar quick-create typeahead."""
    business = get_business(request)
    if not business:
        return JsonResponse({"customers": []})
    q = (request.GET.get("q") or "").strip()
    if len(q) < 1:
        return JsonResponse({"customers": []})
    from customers.models import Customer
    customers = Customer.objects.filter(
        business=business,
        name__icontains=q,
    ).prefetch_related("properties").order_by("name")[:10]
    out = []
    for c in customers:
        props = [{"id": p.id, "address": p.address} for p in c.properties.all()]
        out.append({"id": c.id, "name": c.name, "properties": props})
    return JsonResponse({"customers": out})


@require_GET
@role_required("owner", "manager")
def calendar_unscheduled_jobs(request):
    """List jobs with no scheduled_date (accepted but not yet on calendar)."""
    business = get_business(request)
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


@require_GET
@login_required
def calendar_meeting_data(request, meeting_id):
    """Return meeting details for calendar modal. Owner only."""
    business = get_business(request)
    if not business or getattr(request.user, "role", None) != "owner":
        return JsonResponse({"error": "Forbidden"}, status=403)
    meeting = get_object_or_404(Meeting, id=meeting_id, business=business)
    return JsonResponse({
        "id": meeting.id,
        "title": meeting.title,
        "scheduled_at": meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
        "duration_minutes": meeting.duration_minutes or 60,
        "customer": meeting.customer.name if meeting.customer else "",
        "customer_id": meeting.customer_id,
        "location": meeting.location or "",
        "notes": meeting.notes or "",
    })


@role_required("owner", "manager", "crew")
def daily_route_view(request):
    date_str = request.GET.get('date')
    if date_str:
        jobs = Job.objects.filter(scheduled_date=date_str)
    else:
        jobs = Job.objects.filter(scheduled_date=timezone.now().date())

    business = get_business(request) if request.user.is_authenticated else None
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
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    })


@require_POST
@role_required("owner", "manager")
def update_route_order(request):
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403)
    data = json.loads(request.body)
    for item in data:
        Job.objects.filter(id=item["id"], property__customer__business=business).update(route_order=item["order"])
    return JsonResponse({"status": "ok"})


@role_required("owner", "manager", "crew")
def crew_quick_view(request):
    """Three-tap optimized crew workflow screen."""
    today = timezone.now().date()
    jobs = Job.objects.filter(scheduled_date=today).select_related("property", "assigned_to", "assigned_crew")

    if request.user.role == "crew":
        from django.db.models import Q
        jobs = jobs.filter(
            Q(assigned_to=request.user) |
            Q(assigned_crew__members=request.user) |
            Q(assigned_crew__crew_leader=request.user)
        ).distinct()

    jobs = jobs.order_by("route_order", "scheduled_time")[:40]
    return render(request, "jobs/crew_quick.html", {"jobs": jobs})


@role_required("owner", "manager", "crew")
def crew_today_view(request):
    from time_tracking.models import TimeEntry
    from django.db.models import Count

    today = timezone.now().date()

    jobs = Job.objects.filter(scheduled_date=today).select_related("property", "assigned_to", "assigned_crew").annotate(
        site_photo_count=Count("site_photos"),
    )

    if request.user.role == "crew":
        from django.db.models import Q
        jobs = jobs.filter(
            Q(assigned_to=request.user) |
            Q(assigned_crew__members=request.user) |
            Q(assigned_crew__crew_leader=request.user)
        ).distinct()

    jobs = list(jobs.order_by("route_order"))
    job_ids_with_photos = set(
        JobCompletionPhoto.objects.filter(job__in=jobs).values_list("job_id", flat=True)
    ) if jobs else set()
    business = get_business(request)
    require_completion_photo = bool(business and getattr(business, "require_completion_photo", False))

    # For clock in/out widget
    time_clock_current_entry = TimeEntry.objects.filter(
        user=request.user, clock_out__isnull=True
    ).order_by('-clock_in').first() if request.user.is_authenticated else None

    return render(request, "jobs/crew_today.html", {
        "jobs": jobs,
        "time_clock_current_entry": time_clock_current_entry,
        "job_ids_with_photos": job_ids_with_photos,
        "require_completion_photo": require_completion_photo,
    })

def _user_can_access_job(user, job):
    """Crew can access if assigned to them or if they're in the assigned crew (or crew leader)."""
    if user.role in ("owner", "manager"):
        return True
    if job.assigned_to_id == user.id:
        return True
    if job.assigned_crew_id:
        if job.assigned_crew.crew_leader_id == user.id:
            return True
        if job.assigned_crew.members.filter(id=user.id).exists():
            return True
    return False


@require_POST
@role_required("owner", "manager", "crew")
def start_job(request, job_id):
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job.objects.select_related("assigned_crew"), id=job_id, property__customer__business=business)

    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        return redirect("crew_today")

    if job.status not in ("scheduled",):
        messages.warning(request, "This job cannot be started (already in progress, completed, or skipped).")
        return redirect("crew_today")

    job.status = "in_progress"
    job.save()
    return redirect("crew_today")


@require_POST
@role_required("owner", "manager", "crew")
def notify_en_route(request, job_id):
    """1-tap: mark job in_progress + notify customer crew is on the way."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(
        Job.objects.select_related("assigned_crew", "property", "property__customer"),
        id=job_id, property__customer__business=business,
    )
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Forbidden"}, status=403)
        return redirect("crew_today")

    job.status = "in_progress"
    job.en_route_at = timezone.now()
    job.save(update_fields=["status", "en_route_at"])

    customer = job.property.customer
    notified = False
    try:
        from customers.notifications import notify_customer
        notified = notify_customer(customer, "crew_en_route", job=job)
    except Exception:
        pass

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "status": "ok",
            "notified": notified,
            "message": f"{'Customer notified — ' if notified else ''}crew on the way",
        })

    if notified:
        messages.success(request, f"'{customer.name}' notified — crew on the way")
    else:
        messages.success(request, "Job started (client notification skipped — no contact info or SMS not configured)")
    return redirect("crew_today")


@require_POST
@role_required("owner", "manager", "crew")
def complete_job(request, job_id):
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(Job.objects.select_related("assigned_crew", "property", "property__customer"), id=job_id, property__customer__business=business)

    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Forbidden"}, status=403)
        return redirect("crew_today")

    business = getattr(job.property.customer, "business", None)
    if business and getattr(business, "require_completion_photo", False):
        if not job.completion_photos.exists():
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "Upload at least one completion photo before marking this job complete."}, status=400)
            messages.error(request, "Upload at least one completion photo before marking this job complete.")
            return redirect("crew_today")

    job.status = "completed"
    job.completed_by = request.user
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_by", "completed_at"])

    # Notify client that job is complete
    try:
        from customers.notifications import notify_customer
        customer = job.property.customer
        notify_customer(customer, "job_completed", job=job)
    except Exception:
        pass  # notification failures should never block completion

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "redirect": None})

    if request.user.role in ("owner", "manager"):
        customer = job.property.customer
        business = getattr(customer, "business", None)
        freq = (getattr(customer, "invoice_frequency", None) or "").strip()
        if not freq and business:
            freq = (getattr(business, "default_invoice_automation_mode", None) or "").strip()
        has_items = job.service_items.exists()

        if has_items and freq == "per_service":
            invoice = create_draft_invoice_for_job(job)
            send_behavior = (getattr(business, "auto_invoice_send_behavior", "draft") if business else "draft")
            if send_behavior == "send":
                import secrets
                from billing.models import InvoiceAuditLog
                invoice.status = "sent"
                if not invoice.payment_token:
                    invoice.payment_token = secrets.token_urlsafe(32)
                invoice.approved_at = timezone.now()
                invoice.approved_by = request.user
                invoice.save(update_fields=["status", "payment_token", "approved_at", "approved_by"])
                InvoiceAuditLog.objects.create(
                    invoice=invoice,
                    action="approved_sent",
                    user=request.user,
                    details={"source": "automation", "trigger": "job_completed"},
                )
                messages.success(request, f"Job completed. Invoice #{invoice.id} was automatically approved and sent.")
            else:
                messages.success(
                    request,
                    f"Job completed. Draft invoice #{invoice.id} created. Review and approve & send from Billing.",
                )
            return redirect("billing:invoice_detail", invoice_id=invoice.id)

        if has_items and freq == "monthly":
            d = job.scheduled_date or timezone.now().date()
            invoice = generate_monthly_invoice_for_customer(customer, d.year, d.month, include_job=job)
            messages.success(
                request,
                f"Job completed. Added to {customer.name}'s monthly invoice for {d.strftime('%B %Y')} (Invoice #{invoice.id}).",
            )
            return redirect("billing:invoice_detail", invoice_id=invoice.id)

        return redirect("job_billing_options", job_id=job_id)
    messages.success(request, "Job completed. The owner will handle billing.")
    return redirect("crew_today")


@role_required("owner", "manager", "crew")
def report_issue(request, job_id):
    """Crew or owner reports an issue on a job (type, description, optional photo)."""
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job.objects.select_related("property", "property__customer"), id=job_id, property__customer__business=business)
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        messages.error(request, "You don't have access to this job.")
        return redirect("crew_today")
    business = getattr(job.property.customer, "business", None)
    if request.method == "POST":
        form = ReportIssueForm(request.POST, request.FILES)
        if form.is_valid():
            issue = JobIssue.objects.create(
                job=job,
                reported_by=request.user,
                issue_type=form.cleaned_data["issue_type"],
                description=form.cleaned_data["description"].strip(),
            )
            photo = form.cleaned_data.get("photo")
            if photo:
                JobIssuePhoto.objects.create(job_issue=issue, image=photo)
            business = getattr(job.property.customer, "business", None)
            if business and request.user.role == "crew":
                owners = User.objects.filter(business=business, role="owner")
                desc_preview = (issue.description[:80] + "…") if len(issue.description) > 80 else issue.description
                msg = f"Job issue reported at {job.property.address}: {issue.get_issue_type_display()}. {desc_preview}"
                for owner in owners:
                    Notification.objects.create(
                        business=business,
                        from_user=request.user,
                        to_user=owner,
                        message=msg,
                    )
            messages.success(request, "Issue reported. The owner will be notified.")
            if request.user.role in ("owner", "manager"):
                return redirect("job_detail", job_id=job_id)
            return redirect("crew_today")
    else:
        form = ReportIssueForm()
    return render(request, "jobs/report_issue.html", {
        "job": job,
        "form": form,
    })


@require_POST
@role_required("owner", "manager")
def resolve_issue(request, issue_id):
    """Owner marks an issue as resolved with notes."""
    business = get_business(request)
    if not business:
        return redirect("/")
    issue = get_object_or_404(JobIssue, id=issue_id, job__property__customer__business=business)
    if request.user.business_id != business.id:
        messages.error(request, "Not allowed.")
        return redirect("job_detail", job_id=issue.job_id)
    issue.status = "resolved"
    issue.resolution_notes = (request.POST.get("resolution_notes") or "").strip()
    issue.resolved_at = timezone.now()
    issue.resolved_by = request.user
    issue.save()
    messages.success(request, "Issue marked resolved.")
    return redirect("job_detail", job_id=issue.job_id)


@role_required("owner", "manager", "crew")
def upload_completion_photo(request, job_id):
    """Crew or owner uploads a completion photo for a job (proof of work)."""
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job.objects.select_related("property", "property__customer"), id=job_id, property__customer__business=business)
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        messages.error(request, "You don't have access to this job.")
        return redirect("crew_today")
    if request.method == "POST":
        image = request.FILES.get("photo") or request.FILES.get("image")
        if not image:
            messages.error(request, "Please select a photo to upload.")
            return render(request, "jobs/upload_completion_photo.html", {"job": job})
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            messages.error(request, "Invalid file type. Please upload a JPEG, PNG, or WebP image.")
            return render(request, "jobs/upload_completion_photo.html", {"job": job})
        if image.size > MAX_UPLOAD_SIZE:
            messages.error(request, "File too large. Maximum size is 10 MB.")
            return render(request, "jobs/upload_completion_photo.html", {"job": job})
        JobCompletionPhoto.objects.create(job=job, image=image, uploaded_by=request.user)
        messages.success(request, "Completion photo uploaded.")
        if request.user.role in ("owner", "manager"):
            return redirect("job_detail", job_id=job_id)
        return redirect("crew_today")
    return render(request, "jobs/upload_completion_photo.html", {"job": job})


@require_POST
@role_required("owner", "manager", "crew")
def add_job_note(request, job_id):
    """Add a timestamped note to a job. Crew must be assigned to the job."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        return JsonResponse({"error": "Not assigned to this job"}, status=403)
    text = (request.POST.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "Note text is required"}, status=400)
    note = JobNote.objects.create(job=job, author=request.user, text=text)
    return JsonResponse({
        "id": note.id,
        "text": note.text,
        "author": note.author.get_full_name() or note.author.username,
        "created_at": note.created_at.isoformat(),
    })


@require_POST
@role_required("owner", "manager", "crew")
def add_property_note(request, job_id):
    """Add a note to the job's property (visible across all jobs at this address)."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        return JsonResponse({"error": "Not assigned to this job"}, status=403)
    text = (request.POST.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "Note text is required"}, status=400)
    note = PropertyNote.objects.create(property=job.property, author=request.user, text=text)
    return JsonResponse({
        "id": note.id,
        "text": note.text,
        "author": note.author.get_full_name() or note.author.username,
        "created_at": note.created_at.isoformat(),
        "property_address": job.property.address,
    })


@role_required("owner", "manager", "crew")
def upload_job_photo(request, job_id):
    """Upload a site photo for a job (before/during/after/issue/general)."""
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job.objects.select_related("property", "property__customer"), id=job_id, property__customer__business=business)
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        messages.error(request, "You don't have access to this job.")
        return redirect("crew_today")
    if request.method == "POST":
        image = request.FILES.get("photo") or request.FILES.get("image")
        if not image:
            messages.error(request, "Please select a photo to upload.")
            return render(request, "jobs/upload_job_photo.html", {"job": job})
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            messages.error(request, "Invalid file type. Please upload a JPEG, PNG, or WebP image.")
            return render(request, "jobs/upload_job_photo.html", {"job": job})
        if image.size > MAX_UPLOAD_SIZE:
            messages.error(request, "File too large. Maximum size is 10 MB.")
            return render(request, "jobs/upload_job_photo.html", {"job": job})
        category = request.POST.get("category", "general")
        if category not in dict(JobPhoto.CATEGORY_CHOICES):
            category = "general"
        caption = (request.POST.get("caption") or "").strip()[:255]
        JobPhoto.objects.create(
            job=job, image=image, category=category,
            caption=caption, uploaded_by=request.user,
        )
        messages.success(request, "Site photo uploaded.")
        if request.user.role in ("owner", "manager"):
            return redirect("job_detail", job_id=job_id)
        return redirect("crew_today")
    return render(request, "jobs/upload_job_photo.html", {"job": job})


@require_POST
@role_required("owner", "manager")
def delete_job_photo(request, job_id, photo_id):
    """Delete a site photo (owner/manager only)."""
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job.objects.select_related("property", "property__customer"), id=job_id, property__customer__business=business)
    photo = get_object_or_404(JobPhoto, id=photo_id, job=job)
    photo.image.delete(save=False)
    photo.delete()
    messages.success(request, "Photo deleted.")
    return redirect("job_detail", job_id=job_id)


@require_GET
@role_required("owner", "manager", "crew")
def get_job_notes(request, job_id):
    """Return all job notes and property notes for a job (JSON). Used by crew_today and job_detail."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(
        Job.objects.select_related("property"),
        id=job_id,
        property__customer__business=business,
    )
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        return JsonResponse({"error": "Not assigned to this job"}, status=403)
    job_notes = list(
        job.job_notes.select_related("author").values_list("id", "text", "author__first_name", "author__last_name", "author__username", "created_at")
    )
    property_notes = list(
        job.property.property_notes.select_related("author").values_list("id", "text", "author__first_name", "author__last_name", "author__username", "created_at")
    )
    def fmt(rows, note_type):
        out = []
        for nid, text, first, last, uname, created in rows:
            name = f"{first} {last}".strip() or uname
            out.append({"id": nid, "text": text, "author": name, "created_at": created.isoformat(), "type": note_type})
        return out
    return JsonResponse({
        "job_notes": fmt(job_notes, "job"),
        "property_notes": fmt(property_notes, "property"),
    })


@role_required("owner", "manager")
def create_job(request):
    """Create a new landscaping job from the dashboard."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to create jobs.")
        return redirect("owner_dashboard")

    estimate_id = None  # shared across GET / POST so render context always has it

    if request.method == "POST":
        form = CreateJobForm(request.POST, business=business)
        ServiceFormSet = get_job_service_formset(business)
        formset = ServiceFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            prop = form.cleaned_data["property"]
            atype = form.cleaned_data.get("assignee_type")
            assigned_to = None
            assigned_crew = None
            assigned_employees_list = []
            if atype == "crew":
                assigned_crew = form.cleaned_data.get("assigned_crew")
            elif atype == "employee":
                assigned_employees_list = list(form.cleaned_data.get("assigned_employees") or [])
                assigned_to = form.cleaned_data.get("assigned_to")
                # If multi-select used but no primary, use first selected
                if not assigned_to and assigned_employees_list:
                    assigned_to = assigned_employees_list[0]

            sched_date = form.cleaned_data.get("scheduled_date")
            sched_time = form.cleaned_data.get("scheduled_time") if sched_date else None
            color_val = (form.cleaned_data.get("color") or "").strip()
            if color_val and not color_val.startswith("#"):
                color_val = "#" + color_val
            if color_val and len(color_val) not in (4, 7):
                color_val = None
            repeat_freq = form.cleaned_data.get("repeat_frequency")
            custom_days = form.cleaned_data.get("custom_interval_days") if repeat_freq == "custom" else None

            # Build service snapshot for recurring (so we can create RecurringJob and generate future jobs with same services)
            service_snapshot = []
            for form_data in formset:
                if form_data.cleaned_data.get("service"):
                    service = form_data.cleaned_data["service"]
                    qty = form_data.cleaned_data["quantity"]
                    unit, rate = get_effective_rate(prop, service)
                    override_price = form_data.cleaned_data.get("unit_price")
                    if override_price is not None:
                        rate = override_price
                    unit = getattr(service, "default_unit", None) or unit
                    service_snapshot.append({
                        "service_id": service.pk,
                        "quantity": str(qty),
                        "unit": unit,
                        "unit_price": str(rate),
                    })

            recurring_job = None
            if repeat_freq and sched_date:
                recurring_job = RecurringJob.objects.create(
                    property=prop,
                    frequency=repeat_freq,
                    custom_interval_days=custom_days,
                    start_date=sched_date,
                    active=True,
                    assigned_to=assigned_to,
                    assigned_crew=assigned_crew,
                    notes=form.cleaned_data.get("notes") or "",
                    service_snapshot=service_snapshot,
                )

            job = Job.objects.create(
                property=prop,
                scheduled_date=sched_date,
                scheduled_time=sched_time,
                assigned_to=assigned_to,
                assigned_crew=assigned_crew,
                notes=form.cleaned_data.get("notes") or "",
                status="scheduled",
                color=color_val if color_val else None,
                recurring_job=recurring_job,
            )
            # Set M2M employees (after job is saved)
            if assigned_employees_list:
                job.assigned_employees.set(assigned_employees_list)
            elif assigned_to:
                job.assigned_employees.set([assigned_to])
            assignee_names = ", ".join(e.get_full_name() or e.username for e in assigned_employees_list) if assigned_employees_list else None
            assignee = assigned_crew.name if assigned_crew else (assignee_names or (assigned_to.get_full_name() or assigned_to.username if assigned_to else "Unassigned"))
            JobAssignmentLog.objects.create(job=job, user=request.user, details=f"Job created; assigned to {assignee}")
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
            if recurring_job:
                msg = f"Recurring job created for {prop.address} ({recurring_job.get_frequency_display()}); first date {sched_date}. Future dates will be generated automatically."
            else:
                msg = f"Job created for {prop.address}" + (f" on {job.scheduled_date}" if job.scheduled_date else " (unscheduled)")
            messages.success(request, msg + ".")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
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
        try:
            accepted_estimates = [
                {"id": e.id, "title": e.title, "total": e.base_total(), "customer_id": e.customer_id, "customer_name": e.customer.name}
                for e in Estimate.objects.filter(business=business, status="accepted")
                .select_related("customer").order_by("-accepted_at", "-id")[:20]
            ]
        except Exception:
            accepted_estimates = []
    return render(request, "jobs/job_create.html", {
        "form": form,
        "formset": formset,
        "next_value": request.GET.get("next", ""),
        "service_templates": service_templates,
        "customers_with_properties": customers_with_properties,
        "accepted_estimates": accepted_estimates,
        "loaded_estimate_id": estimate_id if estimate_id else None,
    })


@require_POST
@role_required("owner", "manager")
def job_delete(request, job_id):
    """Delete a job."""
    business = get_business(request)
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


# ---------- Meetings (owner-only) ----------

@role_required("owner", "manager")
def meeting_list(request):
    """List upcoming meetings for the business."""
    business = get_business(request)
    if not business:
        return redirect("/")
    now = timezone.now()
    meetings = Meeting.objects.filter(
        business=business,
        scheduled_at__gte=now,
    ).select_related("customer").order_by("scheduled_at")[:50]
    return render(request, "jobs/meeting_list.html", {"meetings": meetings})


@role_required("owner", "manager")
def meeting_create(request):
    """Create a new meeting (e.g. client meeting)."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    initial = {}
    date_param = request.GET.get("date")
    time_param = request.GET.get("time")
    if date_param:
        initial["scheduled_date"] = date_param
        initial["scheduled_time"] = time_param if time_param else "09:00"
    if request.method == "POST":
        form = MeetingForm(request.POST, business=business)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.business = business
            meeting.created_by = request.user
            meeting.save()
            messages.success(request, f"Meeting “{meeting.title}” added to your schedule.")
            return redirect("calendar")
        messages.error(request, "Please correct the errors below.")
    else:
        form = MeetingForm(initial=initial, business=business)
    return render(request, "jobs/meeting_form.html", {"form": form, "meeting": None})


@role_required("owner", "manager")
def meeting_edit(request, meeting_id):
    """Edit an existing meeting."""
    business = get_business(request)
    if not business:
        return redirect("/")
    meeting = get_object_or_404(Meeting, id=meeting_id, business=business)
    if request.method == "POST":
        form = MeetingForm(request.POST, instance=meeting, business=business)
        if form.is_valid():
            form.save()
            messages.success(request, f"Meeting “{meeting.title}” updated.")
            return redirect("calendar")
        messages.error(request, "Please correct the errors below.")
    else:
        form = MeetingForm(instance=meeting, business=business)
    return render(request, "jobs/meeting_form.html", {"form": form, "meeting": meeting})


@require_POST
@role_required("owner", "manager")
def meeting_delete(request, meeting_id):
    """Delete a meeting."""
    business = get_business(request)
    if not business:
        return redirect("/")
    meeting = get_object_or_404(Meeting, id=meeting_id, business=business)
    title = meeting.title
    meeting.delete()
    messages.success(request, f"Meeting “{title}” deleted.")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    return redirect("calendar")


@role_required("owner", "manager")
def job_billing_options(request, job_id):
    """After job completion: choose to send invoice now or add to monthly."""
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    if job.status != "completed":
        return redirect("job_detail", job_id=job_id)

    return render(request, "jobs/job_billing_options.html", {
        "job": job,
        "customer": job.property.customer,
    })


@require_POST
@role_required("owner", "manager")
def job_bill_now(request, job_id):
    """Create and send invoice immediately for completed job."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
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

    invoice = create_draft_invoice_for_job(job)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "invoice_id": invoice.id})
    messages.success(
        request,
        f"Draft invoice #{invoice.id} created. Review and approve & send from Billing.",
    )
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@require_POST
@role_required("owner", "manager")
def job_add_to_monthly(request, job_id):
    """Add completed job to customer's monthly invoice."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
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


@role_required("owner", "manager")
def job_detail(request, job_id):
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(
        Job.objects.prefetch_related("issues__photos", "completion_photos", "issues__reported_by"),
        id=job_id, property__customer__business=business,
    )

    form = AddJobServiceItemForm(business=business)

    has_unbilled = job.service_items.filter(billed_invoice__isnull=True).exists()

    from django.db.models import Sum
    from django.utils import timezone as tz
    from decimal import Decimal
    job_receipts = list(job.receipts.all().order_by("-receipt_date"))
    job_receipts_total = sum((r.amount or Decimal("0")) for r in job_receipts)
    job_total_cost = job_receipts_total + (job.labor_cost or Decimal("0")) + (job.material_cost or Decimal("0"))
    job_revenue = getattr(job.invoice, "total", None) if getattr(job, "invoice", None) else None
    job_profit = (job_revenue - job_total_cost) if job_revenue is not None else None
    today_iso = tz.now().date().isoformat()

    job_issues = list(job.issues.all())
    job_completion_photos = list(job.completion_photos.all())
    site_photos = list(job.site_photos.select_related("uploaded_by").all())

    return render(request, "jobs/job_detail.html", {
        "job": job,
        "form": form,
        "items": job.service_items.select_related("service").all(),
        "has_unbilled_items": has_unbilled,
        "job_receipts": job_receipts,
        "job_receipts_total": job_receipts_total,
        "job_total_cost": job_total_cost,
        "job_revenue": job_revenue,
        "job_profit": job_profit,
        "today_iso": today_iso,
        "job_issues": job_issues,
        "job_completion_photos": job_completion_photos,
        "site_photos": site_photos,
    })


@require_POST
@role_required("owner", "manager")
def add_job_service_item(request, job_id):
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)

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
@role_required("owner", "manager")
def remove_job_service_item(request, job_id, item_id):
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    JobServiceItem.objects.filter(id=item_id, job=job).delete()
    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner", "manager")
def job_update_costs(request, job_id):
    """Update labor_cost and material_cost for profit tracking."""
    from decimal import Decimal
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    try:
        labor = request.POST.get("labor_cost")
        material = request.POST.get("material_cost")
        if labor is not None and labor != "":
            job.labor_cost = Decimal(str(labor))
        if material is not None and material != "":
            job.material_cost = Decimal(str(material))
        job.save(update_fields=["labor_cost", "material_cost"])
        messages.success(request, "Job costs updated.")
    except Exception:
        messages.error(request, "Invalid cost values.")
    return redirect("job_detail", job_id=job.id)


def _fertilization_dates_for_year(year, n_services, start_month=3, end_month=10):
    """Return n_services dates spread across the growing season (start_month to end_month)."""
    from calendar import monthrange
    try:
        first = date(year, start_month, 1)
        last_day = monthrange(year, end_month)[1]
        last = date(year, end_month, last_day)
    except (ValueError, TypeError):
        first = date(year, 3, 1)
        last = date(year, 10, 31)
    if n_services < 1:
        return []
    if n_services == 1:
        return [first + (last - first) // 2]
    delta = (last - first).days
    step = delta / (n_services - 1) if n_services > 1 else 0
    return [first + timedelta(days=int(i * step)) for i in range(n_services)]


@role_required("owner", "manager")
def fertilization_schedule(request):
    """List properties with fertilization programs and create optimized schedule (same N = same dates)."""
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    from pricing.models import ServiceTemplate
    from django.db import transaction

    # Properties that have fertilization_services_per_year set
    properties = list(
        Property.objects.filter(
            customer__business=business,
            fertilization_services_per_year__isnull=False,
        )
        .select_related("customer")
        .order_by("fertilization_services_per_year", "customer__name", "address")
    )

    # Group by N (services per year) so we use the same dates for same N (optimization)
    from collections import defaultdict
    by_n = defaultdict(list)
    for p in properties:
        by_n[p.fertilization_services_per_year].append(p)

    start_m = getattr(business, "growing_season_start_month", None) or 3
    end_m = getattr(business, "growing_season_end_month", None) or 10
    year = timezone.now().year
    if request.GET.get("year"):
        try:
            year = int(request.GET.get("year"))
        except ValueError:
            pass

    # Build suggested dates per N
    dates_by_n = {}
    for n in by_n:
        dates_by_n[n] = _fertilization_dates_for_year(year, n, start_m, end_m)

    if request.method == "POST":
        service_id = request.POST.get("service_id")
        year_post = request.POST.get("year", str(year))
        try:
            year_post = int(year_post)
        except ValueError:
            year_post = year
        if not service_id:
            messages.error(request, "Select a service (e.g. Fertilization) to create jobs.")
            return redirect("fertilization_schedule")
        try:
            service = ServiceTemplate.objects.get(pk=service_id, business=business)
        except ServiceTemplate.DoesNotExist:
            messages.error(request, "Invalid service.")
            return redirect("fertilization_schedule")
        created = 0
        with transaction.atomic():
            for prop in properties:
                n = prop.fertilization_services_per_year
                for d in dates_by_n.get(n, []):
                    if d < timezone.now().date():
                        continue
                    job, created_job = Job.objects.get_or_create(
                        property=prop,
                        scheduled_date=d,
                        defaults={
                            "status": "scheduled",
                            "notes": f"Fertilization application {d}",
                        },
                    )
                    if created_job:
                        unit, rate = get_effective_rate(prop, service)
                        JobServiceItem.objects.create(
                            job=job,
                            service=service,
                            quantity=1,
                            unit=unit,
                            unit_price=rate,
                        )
                        created += 1
        messages.success(request, f"Created {created} fertilization jobs for {year_post}. Clients with the same number of applications share the same dates for efficiency.")
        return redirect("job_list")

    services = list(ServiceTemplate.objects.filter(business=business, active=True).order_by("name"))
    rows = [{"property": p, "dates": dates_by_n.get(p.fertilization_services_per_year, [])} for p in properties]

    # ------------------------------------------------------------------
    # Daily product-needs summary: for each date, sum up the total sqft
    # so the user knows how many pounds of product to buy.
    # ------------------------------------------------------------------
    daily_needs = {}  # date -> {total_sqft, property_count, properties_missing_sqft}
    for p in properties:
        for d in dates_by_n.get(p.fertilization_services_per_year, []):
            if d not in daily_needs:
                daily_needs[d] = {"total_sqft": 0, "property_count": 0, "missing_sqft": 0}
            daily_needs[d]["property_count"] += 1
            if p.yard_sqft:
                daily_needs[d]["total_sqft"] += p.yard_sqft
            else:
                daily_needs[d]["missing_sqft"] += 1
    daily_needs_sorted = sorted(daily_needs.items())

    return render(request, "jobs/fertilization_schedule.html", {
        "properties": properties,
        "rows": rows,
        "by_n": dict(by_n),
        "dates_by_n": dates_by_n,
        "year": year,
        "services": services,
        "start_month": start_m,
        "end_month": end_m,
        "daily_needs": daily_needs_sorted,
    })

# Real-time tracking API endpoints
@require_POST
@login_required
def update_job_location(request, job_id):
    """Update technician location and ETA for a job (for customer tracking)."""
    job = get_object_or_404(Job, id=job_id)

    # Verify user has access (assigned to job or is owner)
    business = get_business(request)
    if not business or job.property.customer.business != business:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if job.assigned_to != request.user and job.assigned_crew and request.user not in job.assigned_crew.members.all() and request.user.role != 'owner':
        return JsonResponse({"error": "Not assigned to this job"}, status=403)

    try:
        latitude = float(request.POST.get('latitude', 0))
        longitude = float(request.POST.get('longitude', 0))
        eta_minutes = int(request.POST.get('eta_minutes', 0))

        job.technician_latitude = latitude
        job.technician_longitude = longitude
        if eta_minutes > 0:
            job.estimated_arrival_time = timezone.now() + timedelta(minutes=eta_minutes)
        job.technician_location_updated_at = timezone.now()
        job.save(update_fields=['technician_latitude', 'technician_longitude', 'estimated_arrival_time', 'technician_location_updated_at'])

        return JsonResponse({"success": True, "eta": job.estimated_arrival_time.isoformat() if job.estimated_arrival_time else None})
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_GET
@role_required("owner", "manager")
def get_job_tracking(request, job_id):
    """Get real-time tracking info for a job (owner only - customers cannot track technicians)."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)

    job = get_object_or_404(Job, id=job_id)

    # Verify job belongs to business
    if job.property.customer.business != business:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    data = {
        "status": job.status,
        "has_location": bool(job.technician_latitude and job.technician_longitude),
        "latitude": float(job.technician_latitude) if job.technician_latitude else None,
        "longitude": float(job.technician_longitude) if job.technician_longitude else None,
        "location_updated_at": job.technician_location_updated_at.isoformat() if job.technician_location_updated_at else None,
        "estimated_arrival_time": job.estimated_arrival_time.isoformat() if job.estimated_arrival_time else None,
        "assigned_to": job.assigned_to.get_full_name() if job.assigned_to else None,
        "assigned_crew": job.assigned_crew.name if job.assigned_crew else None,
    }

    return JsonResponse(data)

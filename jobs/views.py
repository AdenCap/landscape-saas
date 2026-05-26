import json
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

from django.conf import settings
from django.db.models import Q, Sum, F, Prefetch
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
from billing.services import auto_charge_invoice_card, create_draft_invoice_for_job
from billing.monthly import generate_monthly_invoice_for_customer
from .models import Job, JobServiceItem, JobWorkVisit, Crew, RecurringJob, JobIssue, JobIssuePhoto, JobCompletionPhoto, JobPhoto, JobAssignmentLog, JobDayAssignment, Meeting, JobNote, PropertyNote
from .service_labels import clean_service_label
from customers.models import Property
from .forms import AddJobServiceItemForm, CreateJobForm, get_job_service_formset, ReportIssueForm, MeetingForm
from pricing.utils import get_effective_rate
from accounts.models import User

def _request_data(request):
    if (request.content_type or "").startswith("application/json"):
        try:
            return json.loads(request.body or "{}")
        except (TypeError, ValueError):
            return {}
    return request.POST


def _parse_calendar_datetime(value):
    """Parse FullCalendar local date/datetime strings into an aware datetime."""
    if not value:
        raise ValueError("Missing datetime")
    value = str(value).strip()
    if value.endswith("Z"):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _append_note_text(existing, text):
    existing = (existing or "").strip()
    text = (text or "").strip()
    if not text:
        return existing
    if text in existing.splitlines():
        return existing
    return f"{existing}\n{text}".strip() if existing else text


def _parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError("Invalid date.")


def _wants_json(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")


def _serialize_job_work_visit(visit):
    service_item = visit.service_item
    service_name = "Whole job"
    if service_item:
        service_name = service_item.description or (service_item.service.name if service_item.service else "Line item")
    return {
        "id": visit.id,
        "service_item_id": visit.service_item_id,
        "service_name": service_name,
        "scheduled_date": visit.scheduled_date.isoformat(),
        "scheduled_end_date": visit.scheduled_end_date.isoformat() if visit.scheduled_end_date else "",
        "notes": visit.notes or "",
        "status": visit.status,
    }


def _line_item_active_on(item, target_date):
    if item.scheduled_date is None:
        return True
    item_end = item.scheduled_end_date or item.scheduled_date
    return item.scheduled_date <= target_date <= item_end


def _job_date_range(job):
    if not job.scheduled_date:
        return []
    end_date = job.scheduled_end_date if job.scheduled_end_date and job.scheduled_end_date > job.scheduled_date else job.scheduled_date
    days = (end_date - job.scheduled_date).days
    return [job.scheduled_date + timedelta(days=i) for i in range(days + 1)]


def _assignment_name_for(day_assignment=None, job=None):
    source = day_assignment or job
    if not source:
        return "Unassigned"
    if getattr(source, "assigned_crew", None):
        return source.assigned_crew.name
    employees = list(source.assigned_employees.all()) if hasattr(source, "assigned_employees") else []
    if employees:
        return ", ".join((u.get_full_name() or u.username) for u in employees)
    if getattr(source, "assigned_to", None):
        return source.assigned_to.get_full_name() or source.assigned_to.username
    return "Unassigned"


def _user_matches_day_assignment(user, day_assignment):
    if day_assignment.assigned_to_id == user.id:
        return True
    if day_assignment.assigned_employees.filter(id=user.id).exists():
        return True
    if day_assignment.assigned_crew_id:
        crew = day_assignment.assigned_crew
        if crew.crew_leader_id == user.id:
            return True
        return crew.members.filter(id=user.id).exists()
    return False


def _visit_active_on(visit, target_date):
    visit_end = visit.scheduled_end_date or visit.scheduled_date
    return visit.scheduled_date <= target_date <= visit_end


def _expand_job_range_for_item(job, item_start, item_end):
    if not item_start:
        return
    item_end = item_end or item_start
    changed = []
    if job.scheduled_date is None or item_start < job.scheduled_date:
        job.scheduled_date = item_start
        changed.append("scheduled_date")
    current_end = job.scheduled_end_date or job.scheduled_date
    if current_end is None or item_end > current_end:
        job.scheduled_end_date = item_end if item_end > (job.scheduled_date or item_start) else None
        changed.append("scheduled_end_date")
    if changed:
        job.save(update_fields=list(dict.fromkeys(changed)))


def _business_today(business):
    """Get today's date in the business's timezone (not server UTC)."""
    from accounts.timezone_utils import business_today
    return business_today(business)


def _get_mowing_service(business):
    """Get the PRIMARY mowing service for a business.
    Prefers exact 'Mowing' match, falls back to first service containing 'mow'."""
    from pricing.models import ServiceTemplate
    svc = ServiceTemplate.objects.filter(business=business, active=True, name__iexact="mowing").first()
    if not svc:
        svc = ServiceTemplate.objects.filter(business=business, active=True, name__icontains="mow").first()
    return svc


def _get_mowing_service_ids(business):
    """Get IDs of ALL mowing-related services (for matching existing jobs).
    This is broader than _get_mowing_service — used for lookups, not creation."""
    from pricing.models import ServiceTemplate
    return set(ServiceTemplate.objects.filter(
        business=business, active=True, name__icontains="mow"
    ).values_list("id", flat=True))


CREW_COLORS = [
    '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
    '#ec4899', '#06b6d4', '#84cc16', '#22c55e',
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
        service_names = [si.description or (si.service.name if si.service else "Service") for si in services[:3]]
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
    today = _business_today(business)

    # Base queryset — avoid select_related on reverse OneToOne ('invoice')
    # as it can cause duplicate rows with data integrity issues in Postgres
    qs = Job.objects.filter(
        property__customer__business=business,
    ).select_related('property', 'property__customer', 'assigned_to', 'assigned_crew', 'completed_by').prefetch_related('service_items__service')
    
    # Crew filter: show jobs assigned to them via any assignment method
    if getattr(request.user, 'role', None) == 'crew':
        qs = qs.filter(
            Q(assigned_to=request.user) |
            Q(assigned_employees=request.user) |
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
        # Completed jobs — limit to most recent 100 for performance
        past_jobs = list(qs.filter(
            status='completed'
        ).order_by('-scheduled_date', 'scheduled_time', 'id')[:100])
        filter_label = "Completed Jobs (Recent 100)"
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
        # Limit upcoming to next 14 days to avoid loading entire season
        upcoming_end = today + timedelta(days=14)
        upcoming_qs = qs.filter(
            scheduled_date__gte=today, scheduled_date__lte=upcoming_end
        ).order_by('scheduled_date', 'scheduled_time', 'id')
        upcoming = list(upcoming_qs[:100])
        unscheduled_qs = qs.filter(
            scheduled_date__isnull=True,
        ).distinct().order_by('-created_at')[:50]
        for job in unscheduled_qs:
            details = _get_job_details(job)
            unscheduled_with_details.append({
                'job': job,
                'title': details['title'],
                'amount': details['amount'],
                'is_paid': details['is_paid'],
                'invoice_status': details['invoice_status'],
            })

    # Get counts for filter badges — single query with conditional aggregation
    from django.db.models import Count, Case, When, IntegerField
    month_start = today.replace(day=1)
    counts = qs.aggregate(
        completed_count=Count(Case(When(status='completed', then=1), output_field=IntegerField())),
        past_7=Count(Case(When(scheduled_date__gte=today - timedelta(days=7), scheduled_date__lt=today, then=1), output_field=IntegerField())),
        past_30=Count(Case(When(scheduled_date__gte=today - timedelta(days=30), scheduled_date__lt=today, then=1), output_field=IntegerField())),
        this_month=Count(Case(When(scheduled_date__gte=month_start, scheduled_date__lt=today, then=1), output_field=IntegerField())),
    )
    completed_count = counts['completed_count']
    past_7_days_count = counts['past_7']
    past_30_days_count = counts['past_30']
    this_month_past_count = counts['this_month']

    # Add job details — uses prefetched service_items (no extra queries)
    upcoming_with_details = [
        {**_get_job_details(job), 'job': job}
        for job in upcoming
    ]

    past_jobs_with_details = [
        {**_get_job_details(job), 'job': job}
        for job in past_jobs
    ]
    
    # Accepted estimates that need scheduling (no job created yet)
    from billing.models import Estimate
    needs_scheduling = []
    if not filter_type and getattr(request.user, 'role', None) in ('owner', 'manager'):
        accepted_estimates = Estimate.objects.filter(
            business=business,
            status='accepted',
            job_scheduled=False,
        ).select_related('customer', 'property').order_by('-accepted_at')[:20]
        for est in accepted_estimates:
            needs_scheduling.append(est)

    needs_scheduled_count = len(needs_scheduling) + len(unscheduled_with_details)

    return render(request, 'jobs/job_list.html', {
        'upcoming_jobs': upcoming_with_details,
        'past_jobs': past_jobs_with_details,
        'unscheduled_jobs': unscheduled_with_details,
        'needs_scheduling': needs_scheduling,
        'needs_scheduled_count': needs_scheduled_count,
        'today': today,
        'filter_type': filter_type,
        'filter_date': filter_date,
        'filter_label': filter_label,
        'completed_count': completed_count,
        'past_7_days_count': past_7_days_count,
        'past_30_days_count': past_30_days_count,
        'this_month_past_count': this_month_past_count,
        'upcoming_window_days': 14,
    })


@require_POST
@role_required("owner", "manager")
def schedule_from_estimate(request, estimate_id):
    """Create a job from an accepted estimate and mark estimate as scheduled."""
    business = get_business(request)
    if not business:
        return redirect("/")
    from billing.models import Estimate
    from pricing.utils import get_effective_rate

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business, status='accepted')

    schedule_date_str = request.POST.get("schedule_date", "")
    if not schedule_date_str:
        messages.error(request, "Please select a date.")
        return redirect("job_list")

    try:
        schedule_date = date.fromisoformat(schedule_date_str)
    except (ValueError, TypeError):
        messages.error(request, "Invalid date.")
        return redirect("job_list")

    prop = estimate.property
    if not prop:
        # Use customer's first property as fallback
        prop = estimate.customer.properties.first()
    if not prop:
        messages.error(request, f"No property found for {estimate.customer.name}.")
        return redirect("job_list")

    # Create the job
    job = Job.objects.create(
        property=prop,
        scheduled_date=schedule_date,
        status="scheduled",
        notes=_job_notes_from_estimate(estimate),
    )

    # Copy only accepted line items from estimate to job service items.
    # Declined optional add-ons stay attached to the estimate for future reference.
    for line in estimate.accepted_line_items():
        from pricing.models import ServiceTemplate
        svc = ServiceTemplate.objects.filter(business=business, name__icontains=line.description[:30]).first()
        if not svc:
            svc = ServiceTemplate.objects.filter(business=business, active=True).first()
        if not svc:
            svc = ServiceTemplate.objects.create(
                business=business,
                name=(line.description or estimate.title or "Estimate work")[:120],
                active=True,
                default_unit=line.unit or "visit",
                default_rate=_job_unit_price_from_estimate_line(line),
            )
        JobServiceItem.objects.create(
            job=job,
            service=svc,
            description=line.description,
            detail_description=getattr(line, "detail_description", "") or "",
            quantity=line.quantity or 1,
            unit=line.unit or "visit",
            unit_price=_job_unit_price_from_estimate_line(line),
        )

    # Attach the estimate photos to the scheduled job so the owner and crew can see
    # the same site/reference images that were quoted. The ImageField path is reused
    # instead of duplicating the media file.
    for estimate_image in estimate.images.all():
        JobPhoto.objects.create(
            job=job,
            image=estimate_image.image,
            category="before",
            caption=estimate_image.caption,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

    # Mark estimate as scheduled
    estimate.job_scheduled = True
    estimate.save(update_fields=['job_scheduled'])

    messages.success(request, f"Job scheduled for {schedule_date.strftime('%b %d')} from estimate #{estimate.id} ({estimate.customer.name}).")
    return redirect("job_list")


def _job_unit_price_from_estimate_line(line):
    """Return a per-unit price that preserves the accepted estimate line total.

    Estimate lines can be priced by unit_price, material/labor costs, or a total
    override. JobServiceItem only stores quantity + unit_price, so convert the
    accepted quoted total into the job's unit price snapshot.
    """
    quantity = Decimal(str(line.quantity or 1))
    if quantity == 0:
        quantity = Decimal("1")
    line_total = Decimal(str(line.line_total or 0))
    return (line_total / quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _job_notes_from_estimate(estimate):
    parts = [f"From estimate #{estimate.id}: {estimate.title}"]
    if (estimate.notes or "").strip():
        parts.append("Estimate notes:\n" + estimate.notes.strip())
    if (estimate.site_visit_notes or "").strip():
        parts.append("Site visit notes:\n" + estimate.site_visit_notes.strip())
    return "\n\n".join(parts)[:2000]


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
        crews = [
            {"id": c.id, "name": c.name, "color": c.color or CREW_COLORS[i % len(CREW_COLORS)]}
            for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))
        ]
        employees = [
            {"id": u.id, "name": u.get_full_name() or u.username, "color": (u.color or "").strip() or "#8b5cf6"}
            for u in User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name", "last_name")
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


def _build_user_colors(business):
    """Build a dict of user_id -> hex color for all crew/owner users.
    Users with a custom color get that; others get a unique palette color."""
    colors = {}
    for i, u in enumerate(User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name", "id")):
        if u.color and u.color.strip():
            colors[u.id] = u.color.strip()
        else:
            colors[u.id] = CREW_COLORS[i % len(CREW_COLORS)]
    return colors


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
    ).prefetch_related(
        'service_items__service',
        'assigned_employees',
        'crews',
        'work_visits__service_item__service',
    ).filter(Q(scheduled_date__isnull=False) | Q(work_visits__isnull=False)).distinct()

    # Filter by visible date range (critical for performance)
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")
    visible_start = None
    visible_end = None
    if start_date and end_date:
        try:
            visible_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            visible_end = datetime.strptime(end_date, "%Y-%m-%d").date()
            jobs = jobs.filter(
                Q(scheduled_date__gte=visible_start, scheduled_date__lte=visible_end)
                | Q(scheduled_date__lte=visible_end, scheduled_end_date__gte=visible_start)
                | Q(work_visits__scheduled_date__gte=visible_start, work_visits__scheduled_date__lte=visible_end)
                | Q(work_visits__scheduled_date__lte=visible_end, work_visits__scheduled_end_date__gte=visible_start)
            ).distinct()
        except (ValueError, TypeError):
            pass

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
            # Match jobs where the crew is either the primary (assigned_crew FK)
            # OR one of the additional crews (crews M2M). Wave 3: preserves existing
            # behavior for single-crew jobs — the 0029 data migration backfilled the
            # primary into the M2M, so both clauses match the same rows for legacy data.
            jobs = jobs.filter(
                Q(assigned_crew_id__in=cids) | Q(crews__id__in=cids)
            ).distinct()
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

    # Payment status filter
    payment_filter = request.GET.get("payment", "").strip()

    crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(Crew.objects.filter(business=business).order_by("name"))} if business else {}
    user_colors = _build_user_colors(business) if business else {}

    # Batch-load payment status for all jobs to avoid N+1 queries
    # job_id → payment_status: "paid", "invoiced" (sent), "draft", "not_invoiced"
    from billing.models import Invoice
    job_list = list(jobs)
    job_ids = [j.id for j in job_list]
    job_payment = {}
    if job_ids:
        # Check via Invoice.job (OneToOne) and Invoice.jobs (M2M)
        # OneToOne: Invoice.job_id → invoice status
        oto_invoices = Invoice.objects.filter(job_id__in=job_ids).values_list("job_id", "status")
        for jid, inv_status in oto_invoices:
            if inv_status == "paid":
                job_payment[jid] = "paid"
            elif inv_status == "sent":
                job_payment[jid] = "invoiced"
            elif inv_status == "draft":
                job_payment.setdefault(jid, "draft")
        # M2M: Invoice.jobs
        m2m_invoices = Invoice.objects.filter(jobs__id__in=job_ids).values_list("jobs__id", "status")
        for jid, inv_status in m2m_invoices:
            if inv_status == "paid":
                job_payment[jid] = "paid"
            elif inv_status == "sent":
                job_payment.setdefault(jid, "invoiced")
            elif inv_status == "draft":
                job_payment.setdefault(jid, "draft")
        # Also check via JobServiceItem.billed_invoice
        billed_items = JobServiceItem.objects.filter(
            job_id__in=job_ids, billed_invoice__isnull=False
        ).select_related("billed_invoice").values_list("job_id", "billed_invoice__status")
        for jid, inv_status in billed_items:
            if inv_status == "paid":
                job_payment[jid] = "paid"
            elif inv_status == "sent":
                job_payment.setdefault(jid, "invoiced")
            elif inv_status == "draft":
                job_payment.setdefault(jid, "draft")

    PAYMENT_COLORS = {
        "paid": "#10b981",       # Green — money received
        "invoiced": "#3b82f6",   # Blue — invoice sent, awaiting payment
        "draft": "#f59e0b",      # Amber — invoice drafted but not sent
        "not_invoiced": "#6b7280",  # Gray — no invoice created
    }

    events = []
    for job in job_list:
        # Determine payment status
        pay_status = job_payment.get(job.id, "not_invoiced")
        # Apply payment filter
        if payment_filter and payment_filter != "all":
            if payment_filter == "paid" and pay_status != "paid":
                continue
            elif payment_filter == "unpaid" and pay_status == "paid":
                continue
            elif payment_filter == "invoiced" and pay_status not in ("invoiced", "draft"):
                continue
            elif payment_filter == "not_invoiced" and pay_status != "not_invoiced":
                continue

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
        # Use prefetched data — prefer description (user-facing label) over service.name (internal template name)
        service_names = list({si.description or (si.service.name if si.service else "Service") for si in job.service_items.all()})
        services_str = ", ".join(service_names) if service_names else "No services"

        # Title: service type + customer name (e.g. "Mowing · John Smith")
        if service_names:
            title = ", ".join(service_names[:2]) + " · " + customer_name
        else:
            title = customer_name or job.property.address
        if is_completed:
            title = '✓ ' + title

        # Multi-day jobs: render as all-day spanning events
        is_multi_day = bool(job.scheduled_date and job.scheduled_end_date and job.scheduled_end_date > job.scheduled_date)

        # Wave 3: additional crews (excluding primary, which is already shown as the main crew)
        # Uses prefetched .crews — no extra queries. Empty list for single-crew jobs.
        additional_crews = []
        if job.assigned_crew_id:
            for c in job.crews.all():
                if c.id != job.assigned_crew_id:
                    additional_crews.append({
                        "id": c.id,
                        "name": c.name,
                        "color": crew_colors.get(c.id, UNASSIGNED_COLOR),
                    })

        # Build shared extended props (same for all event types)
        ext_props = {
            "status": job.status, "crew": assignee_name, "jobId": job.id,
            "customer": customer_name, "services": services_str,
            "crewColor": crew_dot_color,
            "statusColor": STATUS_COLORS.get(job.status, '#3b82f6'),
            "assigneeColor": crew_dot_color,
            "jobColorOverride": (job.color or "").strip() or None,
            "serviceAbbr": service_names[0] if service_names else "",
            "recurring": bool(job.recurring_job_id) or "[Mowing]" in (job.notes or "") or "[Fertilization]" in (job.notes or ""),
            "frequency": job.recurring_job.frequency if job.recurring_job_id else None,
            "startedAt": job.started_at.isoformat() if job.started_at else None,
            "completedAt": job.completed_at.isoformat() if job.completed_at else None,
            "duration": job.duration_display,
            "paymentStatus": pay_status,
            "paymentColor": PAYMENT_COLORS.get(pay_status, '#6b7280'),
            "multiDay": is_multi_day,
            "additionalCrews": additional_crews,
        }

        if not job.scheduled_date:
            evt = None
        elif is_multi_day:
            # Multi-day: all-day event spanning from start date to end date
            # FullCalendar uses exclusive end dates, so add 1 day
            start_str = job.scheduled_date.strftime("%Y-%m-%d")
            end_str = (job.scheduled_end_date + timedelta(days=1)).strftime("%Y-%m-%d")
            evt = {
                "id": str(job.id),
                "title": title,
                "start": start_str,
                "end": end_str,
                "allDay": True,
                "backgroundColor": bg,
                "borderColor": bg,
                "extendedProps": ext_props,
            }
        elif job.scheduled_time:
            # Timed event (week/day view). The calendar is the planned schedule,
            # so render from scheduled fields only. Actual started/completed
            # timestamps are still shown in job details/duration, but using them
            # here makes completed or in-progress jobs appear in random actual-work
            # slots and then snap back after a user drags them to a new time.
            dt = datetime.combine(job.scheduled_date, job.scheduled_time)
            start_str = dt.strftime("%Y-%m-%dT%H:%M:%S")
            # End time: scheduled_end_time > default 1 hour
            if job.scheduled_end_time:
                end_str = datetime.combine(job.scheduled_date, job.scheduled_end_time).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                end_dt = dt + timedelta(hours=1)
                end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            evt = {
                "id": str(job.id),
                "title": title,
                "start": start_str,
                "end": end_str,
                "backgroundColor": bg,
                "borderColor": bg,
                "extendedProps": ext_props,
            }
        else:
            # No scheduled_time — show as a timed event at 8 AM
            default_start = datetime.combine(job.scheduled_date, datetime.min.time().replace(hour=8))
            start_str = default_start.strftime("%Y-%m-%dT%H:%M:%S")
            if job.scheduled_end_time:
                end_str = datetime.combine(job.scheduled_date, job.scheduled_end_time).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                end_str = (default_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
            ext_props["noTimeSet"] = True
            evt = {
                "id": str(job.id),
                "title": title,
                "start": start_str,
                "end": end_str,
                "backgroundColor": bg,
                "borderColor": bg,
                "extendedProps": ext_props,
            }
        if evt:
            events.append(evt)

        for visit in job.work_visits.all():
            visit_end = visit.scheduled_end_date or visit.scheduled_date
            if visible_start and visible_end and (visit.scheduled_date > visible_end or visit_end < visible_start):
                continue
            visit_title = title
            if visit.service_item:
                item_label = visit.service_item.description or (visit.service_item.service.name if visit.service_item.service else "")
                if item_label:
                    visit_title = f"Return: {item_label} · {customer_name}"
            visit_ext_props = dict(ext_props)
            visit_ext_props.update({
                "returnVisit": True,
                "visitId": visit.id,
                "serviceItemId": visit.service_item_id,
                "visitNotes": visit.notes or "",
                "multiDay": bool(visit.scheduled_end_date and visit.scheduled_end_date > visit.scheduled_date),
            })
            if visit.scheduled_end_date and visit.scheduled_end_date > visit.scheduled_date:
                visit_evt = {
                    "id": f"visit-{job.id}-{visit.service_item_id or 'job'}-{visit.scheduled_date.isoformat()}",
                    "title": visit_title,
                    "start": visit.scheduled_date.strftime("%Y-%m-%d"),
                    "end": (visit.scheduled_end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "allDay": True,
                    "backgroundColor": bg,
                    "borderColor": bg,
                    "extendedProps": visit_ext_props,
                }
            else:
                visit_start = datetime.combine(visit.scheduled_date, job.scheduled_time or datetime.min.time().replace(hour=8))
                visit_evt = {
                    "id": f"visit-{job.id}-{visit.service_item_id or 'job'}-{visit.scheduled_date.isoformat()}",
                    "title": visit_title,
                    "start": visit_start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": (visit_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
                    "backgroundColor": bg,
                    "borderColor": bg,
                    "extendedProps": visit_ext_props,
                }
            events.append(visit_evt)

    # Owner-only: add meetings to calendar (filtered by date range)
    if business and getattr(request.user, "role", None) in ("owner", "manager"):
        meetings = Meeting.objects.filter(business=business).select_related("customer").order_by("scheduled_at")
        if start_date and end_date:
            try:
                meetings = meetings.filter(
                    scheduled_at__date__gte=datetime.strptime(start_date, "%Y-%m-%d").date(),
                    scheduled_at__date__lte=datetime.strptime(end_date, "%Y-%m-%d").date(),
                )
            except (ValueError, TypeError):
                pass
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
        .prefetch_related(
            'service_items__service',
            'work_visits__service_item__service',
            'assigned_employees',
            'day_assignments__assigned_crew',
            'day_assignments__assigned_to',
            'day_assignments__assigned_employees',
        ),
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

    # Services list — use prefetched data, don't re-query
    services = [
        {
            "id": si.id,
            "name": si.description or (si.service.name if si.service else "Service"),
            "service_name": si.service.name if si.service else "",
            "description": si.description or "",
            "detail_description": si.detail_description or "",
            "quantity": str(si.quantity),
            "unit": si.unit or "visit",
            "scheduled_date": si.scheduled_date.isoformat() if si.scheduled_date else "",
            "scheduled_end_date": si.scheduled_end_date.isoformat() if si.scheduled_end_date else "",
        }
        for si in job.service_items.all()
    ]
    work_visits = [
        _serialize_job_work_visit(visit)
        for visit in job.work_visits.select_related("service_item__service").all()
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
            "customer_name": job.property.customer.name if job.property.customer else "",
            "scheduled_date": job.scheduled_date.isoformat() if job.scheduled_date else "",
            "scheduled_end_date": job.scheduled_end_date.isoformat() if job.scheduled_end_date else "",
            "scheduled_time": job.scheduled_time.strftime("%H:%M") if job.scheduled_time else "",
            "scheduled_end_time": job.scheduled_end_time.strftime("%H:%M") if job.scheduled_end_time else "",
            "status": job.status,
            "notes": job.notes or "",
            "services": services,
            "work_visits": work_visits,
            "images": images,
            "is_recurring": bool(job.recurring_job_id),
            "recurring_job_id": job.recurring_job_id if is_owner else None,
            "assigned_crew_id": job.assigned_crew_id if is_owner else None,
            "assigned_to_id": job.assigned_to_id if is_owner else None,
            "assigned_employee_ids": list(job.assigned_employees.values_list('id', flat=True)) if is_owner else [],
            "assigned_crew_name": job.assigned_crew.name if job.assigned_crew else "",
            "assigned_to_name": (job.assigned_to.get_full_name() or job.assigned_to.username) if job.assigned_to else "",
            "assigned_employee_names": [
                u.get_full_name() or u.username
                for u in job.assigned_employees.all()
            ],
            "assignment_days": [d.isoformat() for d in _job_date_range(job)],
            "day_assignments": [
                {
                    "id": day_assignment.id,
                    "date": day_assignment.date.isoformat(),
                    "assigned_crew_id": day_assignment.assigned_crew_id,
                    "assigned_to_id": day_assignment.assigned_to_id,
                    "assigned_employee_ids": list(day_assignment.assigned_employees.values_list('id', flat=True)),
                    "assignment_name": _assignment_name_for(day_assignment=day_assignment),
                    "notes": day_assignment.notes or "",
                }
                for day_assignment in job.day_assignments.all()
            ] if is_owner else [],
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
        Job.objects.select_related('property', 'property__customer', 'recurring_job'),
        id=job_id,
        property__customer__business=business,
    )
    data = json.loads(request.body) if request.body else {}
    assignment_fields_present = any(k in data for k in ("assigned_crew_id", "assigned_to_id", "assigned_employee_ids"))
    apply_assignment_to_future = bool(data.get("apply_assignment_to_future"))
    selected_crew = None
    selected_employee = None
    selected_employees = None
    # Crew and employee are mutually exclusive
    if "assigned_crew_id" in data:
        vid = data["assigned_crew_id"]
        if vid is None or vid == "":
            job.assigned_crew = None
            job.assigned_to = None
            job.assigned_employees.clear()
        else:
            crew = Crew.objects.filter(business=business, id=vid).first()
            job.assigned_crew = crew
            job.assigned_to = None  # clear employee when crew selected
            job.assigned_employees.clear()
            selected_crew = crew
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
            selected_employee = user
    if "assigned_employee_ids" in data:
        eids = data["assigned_employee_ids"]
        if isinstance(eids, list):
            employees = User.objects.filter(business=business, role__in=["crew", "owner"], id__in=eids)
            selected_employees = list(employees)
            job.assigned_employees.set(employees)
            if employees.exists():
                job.assigned_to = employees.first()
                job.assigned_crew = None
            else:
                job.assigned_to = None
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
    # Handle status changes (skip from calendar)
    if "status" in data:
        new_status = data["status"]
        if new_status in ("scheduled", "skipped"):
            old_status = job.status
            job.status = new_status
            # Sync fertilization rounds when skipping
            if new_status == "skipped":
                try:
                    from fertilization.models import ScheduledRound as FertScheduledRound
                    for sr in FertScheduledRound.objects.filter(job=job):
                        sr.status = 'skipped'
                        sr.save(update_fields=['status'])
                except Exception:
                    pass
    job.save()

    future_assignment_updated = 0
    if apply_assignment_to_future and assignment_fields_present and job.recurring_job_id and job.scheduled_date:
        recurring_job = job.recurring_job
        if "assigned_employee_ids" in data:
            recurring_job.assigned_crew = None
            recurring_job.assigned_to = selected_employees[0] if selected_employees else None
            recurring_job.save(update_fields=["assigned_crew", "assigned_to"])
        elif "assigned_crew_id" in data:
            recurring_job.assigned_crew = selected_crew
            recurring_job.assigned_to = None
            recurring_job.save(update_fields=["assigned_crew", "assigned_to"])
        elif "assigned_to_id" in data:
            recurring_job.assigned_crew = None
            recurring_job.assigned_to = selected_employee
            recurring_job.save(update_fields=["assigned_crew", "assigned_to"])

        future_jobs = Job.objects.filter(
            recurring_job=recurring_job,
            scheduled_date__gt=job.scheduled_date,
            status__in=["scheduled", "en_route"],
        )
        for future_job in future_jobs:
            if "assigned_employee_ids" in data:
                future_job.assigned_crew = None
                future_job.assigned_to = selected_employees[0] if selected_employees else None
                future_job.save(update_fields=["assigned_crew", "assigned_to"])
                future_job.assigned_employees.set(selected_employees or [])
            elif "assigned_crew_id" in data:
                future_job.assigned_crew = selected_crew
                future_job.assigned_to = None
                future_job.save(update_fields=["assigned_crew", "assigned_to"])
                future_job.assigned_employees.clear()
            elif "assigned_to_id" in data:
                future_job.assigned_crew = None
                future_job.assigned_to = selected_employee
                future_job.save(update_fields=["assigned_crew", "assigned_to"])
                future_job.assigned_employees.set([selected_employee] if selected_employee else [])
            future_assignment_updated += 1

    if "assigned_crew_id" in data or "assigned_to_id" in data or "assigned_employee_ids" in data:
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
        user_colors = _build_user_colors(business)
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
        "future_assignment_updated": future_assignment_updated,
    })


@require_POST
@role_required("owner", "manager")
def calendar_job_day_assignment_update(request, job_id):
    """Set a crew/employee assignment for one date of a multi-day job.

    This intentionally stores a per-day override instead of changing the parent Job,
    so previous days and other days in the span keep their original crew.
    """
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(
        Job.objects.select_related("property", "property__customer"),
        id=job_id,
        property__customer__business=business,
    )
    data = json.loads(request.body) if request.body else {}
    try:
        assignment_date = _parse_iso_date(data.get("date"))
    except ValueError:
        return JsonResponse({"error": "Invalid date."}, status=400)
    if not assignment_date:
        return JsonResponse({"error": "Missing date."}, status=400)
    job_days = _job_date_range(job)
    if assignment_date not in job_days:
        return JsonResponse({"error": "Date is outside this job's scheduled range."}, status=400)

    crew = None
    employee_ids = data.get("assigned_employee_ids") or []
    employees = User.objects.none()
    if data.get("assigned_crew_id"):
        crew = Crew.objects.filter(business=business, id=data.get("assigned_crew_id")).first()
        if not crew:
            return JsonResponse({"error": "Crew not found."}, status=404)
        employee_ids = []
    elif employee_ids:
        if not isinstance(employee_ids, list):
            return JsonResponse({"error": "assigned_employee_ids must be a list."}, status=400)
        employees = User.objects.filter(business=business, role__in=["crew", "owner"], id__in=employee_ids)
        found_ids = set(employees.values_list("id", flat=True))
        if set(int(eid) for eid in employee_ids) - found_ids:
            return JsonResponse({"error": "One or more employees were not found."}, status=404)

    day_assignment, _created = JobDayAssignment.objects.get_or_create(job=job, date=assignment_date)
    day_assignment.assigned_crew = crew
    day_assignment.assigned_to = employees.first() if employee_ids else None
    day_assignment.notes = (data.get("notes") or "")[:500]
    day_assignment.save()
    day_assignment.assigned_employees.set(employees if employee_ids else [])

    JobAssignmentLog.objects.create(
        job=job,
        user=request.user,
        details=f"{assignment_date.isoformat()} assignment set to {_assignment_name_for(day_assignment=day_assignment)}",
    )
    return JsonResponse({
        "status": "ok",
        "date": assignment_date.isoformat(),
        "assignment_name": _assignment_name_for(day_assignment=day_assignment),
        "assigned_crew_id": day_assignment.assigned_crew_id,
        "assigned_to_id": day_assignment.assigned_to_id,
        "assigned_employee_ids": list(day_assignment.assigned_employees.values_list("id", flat=True)),
    })


@require_POST
@role_required("owner", "manager")
def calendar_job_reschedule(request, job_id):
    """Update job scheduled_date when dragged to new date.
    For recurring jobs, supports apply_to_future to shift all future jobs."""
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

        old_date = job.scheduled_date
        new_parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        apply_to_future = data.get("apply_to_future", False)
        all_day = data.get("all_day", False)

        job.scheduled_date = new_parsed
        if all_day:
            job.scheduled_time = None
            job.scheduled_end_time = None
        # Only update time if one was provided — don't clear existing time on date-only drags
        elif time_obj is not None:
            job.scheduled_time = time_obj

        # Clear actual tracking timestamps whenever an active/scheduled job is manually
        # moved on the calendar. Calendar event rendering intentionally prefers
        # started_at/completed_at for active jobs, so leaving stale actual times makes
        # a successfully rescheduled event refetch back to its previous slot.
        if job.status in ("scheduled", "en_route", "in_progress"):
            job.started_at = None
            job.completed_at = None

        # Parse end date for multi-day jobs (from drag in month view)
        new_end_date_provided = "scheduled_end_date" in data
        new_end_date_str = data.get("scheduled_end_date")
        if new_end_date_provided:
            try:
                if new_end_date_str:
                    end_date_parsed = datetime.strptime(new_end_date_str, "%Y-%m-%d").date()
                    # Only set if it's actually a different day (multi-day)
                    if end_date_parsed > new_parsed:
                        job.scheduled_end_date = end_date_parsed
                    else:
                        job.scheduled_end_date = None  # Same day = single-day job
                else:
                    job.scheduled_end_date = None
            except (ValueError, TypeError):
                pass

        # Parse end time if provided (from resize or drag)
        new_end = data.get("scheduled_end")
        if new_end and isinstance(new_end, str) and "T" in new_end:
            end_parts = new_end.split("T")
            if len(end_parts) > 1 and end_parts[1]:
                end_time_part = end_parts[1][:8]
                if ":" in end_time_part:
                    etparts = (end_time_part + ":0:0").split(":")[:3]
                    eh, em, es = int(etparts[0] or 0), int(etparts[1] or 0), int(etparts[2] or 0)
                    job.scheduled_end_time = dt_time(eh, em, es)

        job.save()

        # If recurring and user chose to apply to all future jobs
        future_moved = 0
        parent_shifted = False
        notes = job.notes or ""
        is_recurring = bool(job.recurring_job_id) or "[Mowing]" in notes or "[Fertilization]" in notes
        if is_recurring and apply_to_future and old_date:
            day_delta = (new_parsed - old_date).days
            future_schedule_changed = (
                day_delta != 0
                or time_obj is not None
                or (new_end and isinstance(new_end, str) and "T" in new_end)
                or new_end_date_provided
            )
            if future_schedule_changed:
                if job.recurring_job_id:
                    # Find by recurring_job FK
                    future_jobs = Job.objects.filter(
                        recurring_job_id=job.recurring_job_id,
                        scheduled_date__gt=old_date,
                        status__in=["scheduled", "en_route"],
                    ).exclude(id=job.id)
                else:
                    # Legacy: find by same property + same service types
                    svc_ids = list(job.service_items.values_list("service_id", flat=True))
                    future_jobs = Job.objects.filter(
                        property=job.property,
                        scheduled_date__gt=old_date,
                        status__in=["scheduled", "en_route"],
                        service_items__service_id__in=svc_ids,
                    ).exclude(id=job.id).distinct() if svc_ids else Job.objects.none()
                for fj in future_jobs:
                    update_fields = []
                    if day_delta != 0:
                        fj.scheduled_date = fj.scheduled_date + timedelta(days=day_delta)
                        update_fields.append("scheduled_date")
                    if new_end_date_provided:
                        if job.scheduled_end_date:
                            duration_days = (job.scheduled_end_date - job.scheduled_date).days
                            fj.scheduled_end_date = fj.scheduled_date + timedelta(days=duration_days)
                        else:
                            fj.scheduled_end_date = None
                        update_fields.append("scheduled_end_date")
                    if time_obj is not None:
                        fj.scheduled_time = time_obj
                        update_fields.append("scheduled_time")
                    elif all_day:
                        fj.scheduled_time = None
                        update_fields.append("scheduled_time")
                    if new_end and isinstance(new_end, str) and "T" in new_end:
                        fj.scheduled_end_time = job.scheduled_end_time
                        update_fields.append("scheduled_end_time")
                    elif all_day:
                        fj.scheduled_end_time = None
                        update_fields.append("scheduled_end_time")
                    if update_fields:
                        fj.save(update_fields=update_fields)
                        future_moved += 1

                # Shift parent RecurringJob.start_date by the same delta so that
                # generate_jobs() does NOT recreate jobs at the original cadence.
                # Without this, moving all future jobs forward N days would cause
                # the next generation cycle to insert duplicates at the old dates.
                rj_to_shift = None
                if day_delta != 0:
                    if job.recurring_job_id:
                        rj_to_shift = job.recurring_job
                    elif "[Mowing]" in notes or "[Fertilization]" in notes:
                        # Wave 6: legacy mowing/fertilization jobs that were bulk-scheduled
                        # before Fix A1 don't have recurring_job_id set. Find the RecurringJob
                        # for this property (active, same service family) and shift its
                        # start_date too, so generate_jobs() respects the new cadence.
                        rj_to_shift = RecurringJob.objects.filter(
                            property=job.property,
                            active=True,
                        ).order_by('-id').first()
                    if rj_to_shift and rj_to_shift.start_date:
                        rj_to_shift.start_date = rj_to_shift.start_date + timedelta(days=day_delta)
                        rj_to_shift.save(update_fields=["start_date"])
                        parent_shifted = True

        # Sync linked fertilization round date
        try:
            from fertilization.models import ScheduledRound as FertScheduledRound
            for sr in FertScheduledRound.objects.filter(job=job):
                sr.scheduled_date = job.scheduled_date
                sr.save(update_fields=['scheduled_date'])
        except Exception:
            pass

        return JsonResponse({
            "status": "ok",
            "scheduled_date": date_str,
            "is_recurring": is_recurring,
            "future_moved": future_moved,
            "parent_shifted": parent_shifted,
        })
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
    moved_job_ids = list(jobs.values_list('id', flat=True))
    count = jobs.update(scheduled_date=to_d)
    # Sync linked fertilization round dates
    if moved_job_ids:
        try:
            from fertilization.models import ScheduledRound as FertScheduledRound
            FertScheduledRound.objects.filter(job_id__in=moved_job_ids).update(scheduled_date=to_d)
        except Exception:
            pass
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

    services_list = data.get("services", [])
    has_service = service_id or any(s.get("service_id") or s.get("service_name") for s in services_list)

    if not customer_id or not property_id or not scheduled_date_str or not has_service:
        return JsonResponse({"error": "Customer, property, service, and date are required"}, status=400)

    from customers.models import Customer
    customer = Customer.objects.filter(business=business, id=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)
    prop = Property.objects.filter(customer=customer, id=property_id).first()
    if not prop:
        return JsonResponse({"error": "Property not found"}, status=404)
    from pricing.models import ServiceTemplate
    service = None
    if service_id:
        service = ServiceTemplate.objects.filter(business=business, id=service_id, active=True).first()

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

    # Create service items (supports multiple line items + typed service names)
    if services_list:
        for svc_item in services_list:
            svc_id = svc_item.get("service_id")
            svc_name = svc_item.get("service_name", "").strip()
            svc_detail = (svc_item.get("detail_description") or "").strip()
            svc_qty = svc_item.get("quantity", 1)
            svc_price_override = svc_item.get("unit_price")

            svc = None
            if svc_id:
                svc = ServiceTemplate.objects.filter(business=business, id=svc_id, active=True).first()
            elif svc_name:
                # Try to match by name, or create a new service template
                svc = ServiceTemplate.objects.filter(business=business, name__iexact=svc_name, active=True).first()
                if not svc:
                    svc = ServiceTemplate.objects.create(
                        business=business, name=svc_name, default_unit="visit",
                        default_rate=svc_price_override or 0, pricing_method="flat", active=True,
                    )

            if svc:
                unit, rate = get_effective_rate(prop, svc)
                if svc_price_override is not None:
                    from decimal import Decimal
                    rate = Decimal(str(svc_price_override))
                JobServiceItem.objects.create(
                    job=job, service=svc, description=clean_service_label(service=svc),
                    detail_description=svc_detail[:1000],
                    quantity=svc_qty, unit=unit, unit_price=rate,
                )
    elif service:
        # Fallback: single service_id
        unit, rate = get_effective_rate(prop, service)
        JobServiceItem.objects.create(
            job=job, service=service, description=clean_service_label(service=service),
            quantity=1, unit=unit, unit_price=rate,
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
    """List unscheduled jobs AND accepted estimates that need scheduling."""
    business = get_business(request)
    if not business:
        return JsonResponse({"jobs": []})

    out = []

    # Unscheduled jobs (created but no date set)
    jobs = Job.objects.filter(
        property__customer__business=business,
        scheduled_date__isnull=True,
    ).select_related('property', 'property__customer').prefetch_related('service_items__service').order_by('-created_at')[:30]
    for j in jobs:
        services = list({si.service.name for si in j.service_items.all() if si.service})
        out.append({
            "id": j.id,
            "type": "job",
            "address": j.property.address,
            "customer": j.property.customer.name if j.property.customer else "",
            "services": ", ".join(services) if services else "No services",
            "status": j.status,
        })

    # Accepted estimates not yet scheduled as jobs
    from billing.models import Estimate
    accepted_estimates = Estimate.objects.filter(
        business=business,
        status="accepted",
        job_scheduled=False,
    ).select_related("customer").order_by("-accepted_at")[:20]
    for est in accepted_estimates:
        out.append({
            "id": est.id,
            "type": "estimate",
            "address": "",
            "customer": est.customer.name,
            "services": est.title,
            "status": "accepted",
            "estimate_id": est.id,
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


@require_POST
@role_required("owner", "manager")
def calendar_meeting_reschedule(request, meeting_id):
    """Move a meeting from FullCalendar drag/drop while preserving the exact time."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403)
    meeting = get_object_or_404(Meeting, id=meeting_id, business=business)
    data = json.loads(request.body) if request.body else {}
    scheduled_at_raw = data.get("scheduled_at") or data.get("scheduled_date") or data.get("date")
    if not scheduled_at_raw:
        return JsonResponse({"error": "Missing scheduled_at"}, status=400)
    try:
        meeting.scheduled_at = _parse_calendar_datetime(scheduled_at_raw)
        if "duration_minutes" in data:
            try:
                meeting.duration_minutes = max(1, int(data.get("duration_minutes") or 60))
            except (TypeError, ValueError):
                pass
        meeting.save(update_fields=["scheduled_at", "duration_minutes"])
    except (TypeError, ValueError) as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({
        "status": "ok",
        "scheduled_at": timezone.localtime(meeting.scheduled_at).strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_minutes": meeting.duration_minutes or 60,
    })


@role_required("owner", "manager", "crew")
def daily_route_view(request):
    business = get_business(request) if request.user.is_authenticated else None
    date_str = request.GET.get('date')
    if date_str:
        jobs = Job.objects.filter(scheduled_date=date_str)
    else:
        jobs = Job.objects.filter(scheduled_date=_business_today(business))
    if business:
        jobs = jobs.filter(property__customer__business=business)
    # Only show active jobs in route — exclude completed/skipped/cancelled
    jobs = jobs.filter(status__in=["scheduled", "en_route", "in_progress"]).distinct()

    # Filters: crew, employee, service type
    crew_filter = request.GET.get('crew', '').strip()
    emp_filter = request.GET.get('employee', '').strip()
    svc_filter = request.GET.get('service', '').strip()
    if crew_filter:
        jobs = jobs.filter(assigned_crew_id=crew_filter)
    if emp_filter:
        jobs = jobs.filter(Q(assigned_to_id=emp_filter) | Q(assigned_employees__id=emp_filter)).distinct()
    if svc_filter:
        jobs = jobs.filter(service_items__service__name__icontains=svc_filter).distinct()

    jobs = jobs.select_related('property', 'assigned_to', 'assigned_crew').prefetch_related('service_items__service').order_by('route_order')
    date_param = date_str or timezone.now().strftime('%Y-%m-%d')

    # Build filter options for the template
    crews = list(Crew.objects.filter(business=business).order_by("name")) if business else []
    employees = list(User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name")) if business else []
    # Get unique service names for the day
    from pricing.models import ServiceTemplate
    service_types = list(ServiceTemplate.objects.filter(business=business, active=True).order_by("name").values_list("name", flat=True)) if business else []

    crew_colors = {c.id: (c.color or CREW_COLORS[i % len(CREW_COLORS)]) for i, c in enumerate(crews)} if business else {}
    user_colors = _build_user_colors(business) if business else {}

    # Calculate average duration per property for route time estimation
    from django.db.models import Avg, F, ExpressionWrapper, DurationField
    property_ids = [j.property_id for j in jobs]
    prop_avg_durations = {}
    if property_ids:
        avgs = Job.objects.filter(
            property_id__in=property_ids,
            status="completed",
            started_at__isnull=False,
            completed_at__isnull=False,
        ).values('property_id').annotate(
            avg_dur=Avg(ExpressionWrapper(F('completed_at') - F('started_at'), output_field=DurationField()))
        )
        for row in avgs:
            dur = row['avg_dur']
            if dur:
                prop_avg_durations[row['property_id']] = int(dur.total_seconds() / 60)

    jobs_with_colors = [
        {
            "job": j,
            "color": _color_for_assignee(j, crew_colors, user_colors),
            "est_minutes": prop_avg_durations.get(j.property_id),
        }
        for j in jobs
    ]

    total_est_minutes = sum(item.get("est_minutes") or 0 for item in jobs_with_colors)
    if total_est_minutes:
        _hrs, _mins_rem = divmod(total_est_minutes, 60)
        est_work_display = f"{_hrs}h {_mins_rem}m" if _hrs else f"{_mins_rem}m"
    else:
        est_work_display = ""

    return render(request, 'jobs/daily_route.html', {
        "jobs": jobs,
        "jobs_with_colors": jobs_with_colors,
        "date_param": date_param,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "shop_address": business.shop_address if business else "",
        "total_est_minutes": total_est_minutes,
        "est_work_display": est_work_display,
        "crews": crews,
        "employees": employees,
        "service_types": service_types,
        "crew_filter": crew_filter,
        "emp_filter": emp_filter,
        "svc_filter": svc_filter,
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


@require_POST
@role_required("owner", "manager")
def apply_route_to_calendar(request):
    """After route optimization, update scheduled_time on each job based on route order and estimated durations."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403)
    data = json.loads(request.body) if request.body else {}
    job_ids = data.get("job_ids", [])
    start_time_str = data.get("start_time", "08:00")
    travel_minutes = int(data.get("travel_minutes_between", 15))
    apply_to_future = data.get("apply_to_future", False)

    if not job_ids:
        return JsonResponse({"error": "No jobs"}, status=400)

    from datetime import time as dt_time
    try:
        parts = start_time_str.split(":")
        current_hour = int(parts[0])
        current_min = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        current_hour, current_min = 8, 0

    # Get average durations per property
    from django.db.models import Avg, F, ExpressionWrapper, DurationField
    jobs = list(Job.objects.filter(id__in=job_ids, property__customer__business=business).select_related('property').order_by('route_order'))
    prop_ids = [j.property_id for j in jobs]
    prop_avg = {}
    if prop_ids:
        avgs = Job.objects.filter(
            property_id__in=prop_ids, status="completed",
            started_at__isnull=False, completed_at__isnull=False,
        ).values('property_id').annotate(
            avg_dur=Avg(ExpressionWrapper(F('completed_at') - F('started_at'), output_field=DurationField()))
        )
        for row in avgs:
            if row['avg_dur']:
                prop_avg[row['property_id']] = int(row['avg_dur'].total_seconds() / 60)

    # Sort jobs in order they appear in job_ids (optimized order)
    job_map = {j.id: j for j in jobs}
    ordered = [job_map[jid] for jid in job_ids if jid in job_map]

    def round_to_15(h, m):
        """Round minutes to nearest 15-minute mark (0, 15, 30, 45)."""
        m = int(round(m / 15.0)) * 15
        while m >= 60:
            m -= 60
            h += 1
        return h, m

    # Round start time to nearest 15
    current_hour, current_min = round_to_15(current_hour, current_min)

    updated = 0
    for i, job in enumerate(ordered):
        job.scheduled_time = dt_time(min(current_hour, 20), current_min)
        # Set end time based on estimated duration
        est_dur = prop_avg.get(job.property_id, 30)  # default 30 min if no history
        end_min = current_min + est_dur
        end_hour = current_hour
        while end_min >= 60:
            end_min -= 60
            end_hour += 1
        end_hour, end_min = round_to_15(end_hour, end_min)
        job.scheduled_end_time = dt_time(min(end_hour, 21), end_min)
        job.route_order = i
        job.save(update_fields=["scheduled_time", "scheduled_end_time", "route_order"])
        updated += 1
        # Advance to next job: end time + travel
        total_advance = est_dur + (travel_minutes if i < len(ordered) - 1 else 0)
        current_min += total_advance
        while current_min >= 60:
            current_min -= 60
            current_hour += 1
        # Round to 15-minute boundary
        current_hour, current_min = round_to_15(current_hour, current_min)
        if current_hour >= 21:
            current_hour = 21
            current_min = 0

    # Apply same times to all future recurring jobs for these properties
    future_updated = 0
    if apply_to_future and ordered:
        # Build a map: property_id -> {scheduled_time, scheduled_end_time, route_order}
        prop_schedule = {}
        for job in ordered:
            prop_schedule[job.property_id] = {
                "time": job.scheduled_time,
                "end_time": job.scheduled_end_time,
                "route_order": job.route_order,
            }

        # Find the date of the jobs we just updated
        today_date = ordered[0].scheduled_date
        prop_ids = list(prop_schedule.keys())

        # Get all future scheduled jobs for these properties
        future_jobs = Job.objects.filter(
            property_id__in=prop_ids,
            property__customer__business=business,
            scheduled_date__gt=today_date,
            status__in=["scheduled"],
        ).select_related("property")

        for fj in future_jobs:
            sched = prop_schedule.get(fj.property_id)
            if sched:
                fj.scheduled_time = sched["time"]
                fj.scheduled_end_time = sched["end_time"]
                fj.route_order = sched["route_order"]
                fj.save(update_fields=["scheduled_time", "scheduled_end_time", "route_order"])
                future_updated += 1

    return JsonResponse({"status": "ok", "updated": updated, "future_updated": future_updated})


@role_required("owner", "manager", "crew")
def crew_quick_view(request):
    """Three-tap optimized crew workflow screen."""
    today = _business_today(get_business(request))
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

    business = get_business(request)
    # Use business timezone for "today" — server may be in UTC
    today = _business_today(business)

    # Wave 5: include multi-day jobs where today falls between scheduled_date and
    # scheduled_end_date, not just single-day jobs starting today. Single-day jobs
    # continue to match via the first Q clause (scheduled_end_date is NULL, second
    # clause never matches them).
    jobs = Job.objects.filter(
        Q(scheduled_date=today) |
        Q(scheduled_date__lte=today, scheduled_end_date__gte=today) |
        Q(work_visits__scheduled_date=today) |
        Q(work_visits__scheduled_date__lte=today, work_visits__scheduled_end_date__gte=today)
    ).select_related(
        "property", "property__customer", "assigned_to", "assigned_crew", "recurring_job"
    ).prefetch_related(
        "service_items__service",
        "work_visits__service_item__service",
        "assigned_employees",
        "job_notes__author",
        Prefetch(
            "site_photos",
            queryset=JobPhoto.objects.select_related("uploaded_by").order_by("-uploaded_at"),
            to_attr="crew_site_photos",
        ),
        "day_assignments__assigned_crew__members",
        "day_assignments__assigned_crew__crew_leader",
        "day_assignments__assigned_to",
        "day_assignments__assigned_employees",
        Prefetch(
            "property__property_notes",
            queryset=PropertyNote.objects.filter(visibility=PropertyNote.VISIBILITY_CREW).select_related("author"),
            to_attr="crew_visible_notes",
        ),
    ).annotate(
        site_photo_count=Count("site_photos"),
    ).distinct()

    # Always filter by business first
    if business:
        jobs = jobs.filter(property__customer__business=business)

    if request.user.role == "crew":
        # Show jobs assigned to this user via ANY assignment method
        jobs = jobs.filter(
            Q(assigned_to=request.user) |                    # Direct assignment
            Q(assigned_employees=request.user) |             # M2M assignment
            Q(assigned_crew__members=request.user) |         # Crew member
            Q(assigned_crew__crew_leader=request.user) |      # Crew leader
            Q(day_assignments__date=today, day_assignments__assigned_to=request.user) |
            Q(day_assignments__date=today, day_assignments__assigned_employees=request.user) |
            Q(day_assignments__date=today, day_assignments__assigned_crew__members=request.user) |
            Q(day_assignments__date=today, day_assignments__assigned_crew__crew_leader=request.user)
        ).distinct()

    # Sort to match the owner's calendar order, but push done jobs to bottom.
    # FullCalendar shows timed jobs by scheduled_time; route_order is the tie-breaker
    # for jobs at the same time or jobs without explicit times.
    from django.db.models import Case, When, IntegerField, Value
    jobs = list(jobs.annotate(
        is_done=Case(
            When(status__in=["completed", "skipped", "cancelled"], then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by("is_done", "scheduled_time", "route_order", "id"))

    if request.user.role == "crew":
        filtered_jobs = []
        for job in jobs:
            today_override = next((da for da in job.day_assignments.all() if da.date == today), None)
            if today_override:
                if _user_matches_day_assignment(request.user, today_override):
                    job.effective_day_assignment = today_override
                    filtered_jobs.append(job)
            else:
                filtered_jobs.append(job)
        jobs = filtered_jobs

    # For each job, compute filtered_service_items for today.
    #   - Single-day job: all items (same as before)
    #   - Multi-day job: items scheduled for today, spanning today, or blank
    # Uses prefetched service_items — no extra queries per job.
    for job in jobs:
        all_items = list(job.service_items.all())
        active_visits = [visit for visit in job.work_visits.all() if _visit_active_on(visit, today)]
        if job.scheduled_date and job.scheduled_end_date and job.scheduled_end_date > job.scheduled_date:
            # Multi-day: filter by today. Items with scheduled_date=None span the whole job.
            job.filtered_service_items = [
                si for si in all_items
                if _line_item_active_on(si, today)
            ]
        else:
            # Single-day: all items (unchanged behavior)
            job.filtered_service_items = all_items
        if active_visits:
            visit_items = [visit.service_item for visit in active_visits if visit.service_item_id]
            if visit_items:
                existing_ids = {item.id for item in job.filtered_service_items}
                job.filtered_service_items = list(job.filtered_service_items) + [
                    item for item in visit_items if item.id not in existing_ids
                ]
            elif job.scheduled_date != today and not (job.scheduled_end_date and job.scheduled_date and job.scheduled_date <= today <= job.scheduled_end_date):
                job.filtered_service_items = all_items
        job.active_return_visits = active_visits
        property_alerts = []
        if job.property.gate_code:
            property_alerts.append({"label": "Gate code", "text": job.property.gate_code})
        if job.property.has_dog:
            property_alerts.append({"label": "Dog on site", "text": "Check before entering the yard."})
        if (job.property.notes or "").strip():
            property_alerts.append({"label": "Property note", "text": job.property.notes.strip()})
        for note in getattr(job.property, "crew_visible_notes", [])[:3]:
            property_alerts.append({"label": "Permanent note", "text": note.text})
        job.property_alerts = property_alerts

        note_previews = []
        seen_note_texts = set()

        def add_note_preview(label, text):
            normalized = (text or "").strip()
            if not normalized or normalized in seen_note_texts:
                return
            seen_note_texts.add(normalized)
            note_previews.append({"label": label, "text": normalized})

        if job.recurring_job_id:
            add_note_preview("Recurring note", getattr(job.recurring_job, "notes", ""))
        add_note_preview("Crew note", job.notes)
        visible_job_notes = list(job.job_notes.all())
        if request.user.role == "crew":
            visible_job_notes = [note for note in visible_job_notes if note.visibility == JobNote.VISIBILITY_CREW]
        for note in visible_job_notes[:3]:
            add_note_preview("Job note", note.text)
        job.note_previews = note_previews

        site_photos = list(getattr(job, "crew_site_photos", []))
        job.photo_previews = site_photos[:4]
        job.extra_photo_count = max(len(site_photos) - len(job.photo_previews), 0)

    job_ids_with_photos = set(
        JobCompletionPhoto.objects.filter(job__in=jobs).values_list("job_id", flat=True)
    ) if jobs else set()
    require_completion_photo = bool(business and getattr(business, "require_completion_photo", False))
    total_jobs = len(jobs)
    completed_jobs = sum(1 for job in jobs if job.status in {"completed", "skipped"})
    remaining_jobs = max(total_jobs - completed_jobs, 0)
    next_job = next((job for job in jobs if job.status not in {"completed", "skipped"}), None)
    route_name = ""
    for job in jobs:
        if job.assigned_crew:
            route_name = job.assigned_crew.name
            break
    if not route_name:
        route_name = request.user.get_full_name() or request.user.username
    route_progress_percent = int((completed_jobs / total_jobs) * 100) if total_jobs else 0

    # For clock in/out widget
    time_clock_current_entry = TimeEntry.objects.filter(
        user=request.user, clock_out__isnull=True
    ).order_by('-clock_in').first() if request.user.is_authenticated else None

    return render(request, "jobs/crew_today.html", {
        "jobs": jobs,
        "today": today,
        "time_clock_current_entry": time_clock_current_entry,
        "job_ids_with_photos": job_ids_with_photos,
        "require_completion_photo": require_completion_photo,
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "remaining_jobs": remaining_jobs,
        "next_job": next_job,
        "route_name": route_name,
        "route_progress_percent": route_progress_percent,
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
    for day_assignment in job.day_assignments.select_related("assigned_crew", "assigned_to").prefetch_related("assigned_crew__members", "assigned_employees"):
        if _user_matches_day_assignment(user, day_assignment):
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
    job.started_at = timezone.now()
    # Update scheduled_time to actual start time for calendar accuracy
    job.scheduled_time = timezone.now().time()
    # Capture GPS if provided
    lat = request.POST.get("latitude", "").strip()
    lng = request.POST.get("longitude", "").strip()
    if lat and lng:
        try:
            job.technician_latitude = float(lat)
            job.technician_longitude = float(lng)
            job.technician_location_updated_at = timezone.now()
        except (ValueError, TypeError):
            pass
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
    # Capture GPS on completion
    lat = request.POST.get("latitude", "").strip()
    lng = request.POST.get("longitude", "").strip()
    update_fields = ["status", "completed_by", "completed_at"]
    if lat and lng:
        try:
            job.technician_latitude = float(lat)
            job.technician_longitude = float(lng)
            job.technician_location_updated_at = timezone.now()
            update_fields.extend(["technician_latitude", "technician_longitude", "technician_location_updated_at"])
        except (ValueError, TypeError):
            pass
    job.save(update_fields=update_fields)

    # Auto-complete any linked fertilization scheduled rounds
    try:
        from fertilization.models import ScheduledRound as FertScheduledRound
        # 1. Find rounds linked by job FK
        linked_rounds = list(FertScheduledRound.objects.filter(job=job, status__in=['pending', 'scheduled']))
        # 2. Fallback: match by property for unlinked rounds (legacy data)
        if not linked_rounds and '[Fertilization]' in (job.notes or ''):
            # Try exact property + date
            linked_rounds = list(FertScheduledRound.objects.filter(
                enrollment__property=job.property,
                scheduled_date=job.scheduled_date,
                status__in=['pending', 'scheduled'],
            ).order_by('round_number')[:1])
            # If no date match, find next pending round for this property
            if not linked_rounds:
                linked_rounds = list(FertScheduledRound.objects.filter(
                    enrollment__property=job.property,
                    status__in=['pending', 'scheduled'],
                ).order_by('round_number')[:1])
        # 3. Link and complete
        for sr in linked_rounds:
            sr.job = job
            sr.status = 'completed'
            sr.save(update_fields=['status', 'job'])
            # Update enrollment status based on round progress
            enrollment = sr.enrollment
            completed_count = enrollment.scheduled_rounds.filter(status='completed').count()
            total_count = enrollment.scheduled_rounds.count()
            if completed_count >= total_count and enrollment.status in ('enrolled', 'in_progress'):
                enrollment.status = 'completed'
            elif completed_count > 0 and enrollment.status == 'enrolled':
                enrollment.status = 'in_progress'
            enrollment.save(update_fields=['status'])
    except Exception:
        pass  # fertilization updates should never block job completion

    # Notify client that job is complete
    try:
        from customers.notifications import notify_customer
        customer = job.property.customer
        notify_customer(customer, "job_completed", job=job)
    except Exception:
        pass  # notification failures should never block completion

    customer = job.property.customer
    business = getattr(customer, "business", None)
    freq = (getattr(customer, "invoice_frequency", None) or "").strip()
    if not freq and business:
        freq = (getattr(business, "default_invoice_automation_mode", None) or "").strip()
    has_items = job.service_items.exists()
    monthly_invoice = None
    if has_items and freq == "monthly":
        d = job.scheduled_date or _business_today(business)
        monthly_invoice = generate_monthly_invoice_for_customer(customer, d.year, d.month, include_job=job)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        payload = {"status": "ok", "redirect": None}
        if monthly_invoice:
            payload.update({
                "billing_status": "monthly_invoice_queued",
                "invoice_id": monthly_invoice.id,
            })
        return JsonResponse(payload)

    if request.user.role in ("owner", "manager"):
        if has_items and freq == "per_service":
            invoice = create_draft_invoice_for_job(job)
            if invoice is None:
                # Prepaid service agreement covers all services — no invoice needed
                messages.success(request, f"Job completed. All services covered by a prepaid agreement — no invoice created.")
                return redirect("job_detail", job_id=job_id)
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
                charged, charged_msg = auto_charge_invoice_card(invoice, user=request.user, source="job_completed")
                if charged:
                    messages.success(request, f"Job completed. Invoice #{invoice.id} sent. {charged_msg}")
                else:
                    messages.success(request, f"Job completed. Invoice #{invoice.id} sent.")
                    if customer.should_auto_charge_invoice(invoice):
                        messages.warning(request, charged_msg)
            else:
                messages.success(
                    request,
                    f"Job completed. Draft invoice #{invoice.id} created. Review and approve & send from Billing.",
                )
            return redirect("billing:invoice_detail", invoice_id=invoice.id)

        if monthly_invoice:
            d = job.scheduled_date or _business_today(business)
            messages.success(
                request,
                f"Job completed. Added to {customer.name}'s monthly invoice for {d.strftime('%B %Y')} (Invoice #{monthly_invoice.id}).",
            )
            return redirect("billing:invoice_detail", invoice_id=monthly_invoice.id)

        return redirect("job_billing_options", job_id=job_id)
    if monthly_invoice:
        messages.success(request, "Job completed and queued for monthly billing.")
        return redirect("crew_today")
    messages.success(request, "Job completed. The owner will handle billing.")
    return redirect("crew_today")


@require_POST
@role_required("owner", "manager")
def uncomplete_job(request, job_id):
    """Revert a completed or in-progress job back to scheduled status."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)

    if job.status not in ("completed", "in_progress"):
        msg = "Job is not completed or in progress — nothing to undo."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": msg}, status=400)
        messages.warning(request, msg)
        return redirect("job_detail", job_id=job.id)

    job.status = "scheduled"
    job.completed_by = None
    job.completed_at = None
    job.started_at = None
    job.save(update_fields=["status", "completed_by", "completed_at", "started_at"])

    # Revert any linked fertilization rounds back to scheduled
    try:
        from fertilization.models import ScheduledRound as FertScheduledRound
        for sr in FertScheduledRound.objects.filter(job=job, status='completed'):
            sr.status = 'scheduled'
            sr.save(update_fields=['status'])
    except Exception:
        pass

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})

    messages.success(request, "Job reverted to scheduled.")
    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner", "manager", "crew")
def skip_job(request, job_id):
    """Skip a job with a required reason. Optionally push to next day or next week."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if is_ajax:
        data = json.loads(request.body) if request.body else {}
        reason = (data.get("reason") or "").strip()
        action = (data.get("action") or "skip").strip()  # skip, push_tomorrow, push_next_week
    else:
        reason = request.POST.get("reason", "").strip()
        action = request.POST.get("action", "skip").strip()

    if not reason:
        if is_ajax:
            return JsonResponse({"error": "A reason is required to skip a job."}, status=400)
        messages.error(request, "A reason is required to skip a job.")
        return redirect("job_detail", job_id=job.id)

    # Mark this job as skipped
    job.status = "skipped"
    job.skip_reason = reason
    job.skipped_at = timezone.now()
    job.save(update_fields=["status", "skip_reason", "skipped_at"])

    # Sync any linked fertilization rounds
    try:
        from fertilization.models import ScheduledRound as FertScheduledRound
        for sr in FertScheduledRound.objects.filter(job=job, status__in=["pending", "scheduled"]):
            sr.status = "skipped"
            sr.save(update_fields=["status"])
    except Exception:
        pass

    # If pushing to another day, create a new job
    new_job = None
    if action in ("push_tomorrow", "push_next_week"):
        if action == "push_tomorrow":
            new_date = job.scheduled_date + timedelta(days=1)
        else:
            new_date = job.scheduled_date + timedelta(days=7)

        new_job = Job.objects.create(
            property=job.property,
            scheduled_date=new_date,
            scheduled_time=job.scheduled_time,
            scheduled_end_time=job.scheduled_end_time,
            status="scheduled",
            notes=job.notes,
            assigned_crew=job.assigned_crew,
            assigned_to=job.assigned_to,
            recurring_job=job.recurring_job,
        )
        # Copy service items
        for si in job.service_items.all():
            JobServiceItem.objects.create(
                job=new_job,
                service=si.service,
                description=si.description,
                detail_description=getattr(si, "detail_description", "") or "",
                quantity=si.quantity,
                unit=si.unit,
                unit_price=si.unit_price,
                material_cost=si.material_cost,
                labor_cost=si.labor_cost,
                scheduled_date=si.scheduled_date,
                scheduled_end_date=si.scheduled_end_date,
            )

    if is_ajax:
        result = {"status": "ok", "skipped": True}
        if new_job:
            result["new_job_id"] = new_job.id
            result["new_date"] = new_job.scheduled_date.isoformat()
            result["action"] = action
        return JsonResponse(result)

    if new_job:
        action_label = "tomorrow" if action == "push_tomorrow" else "next week"
        messages.success(request, f"Job skipped ({reason}). Rescheduled to {action_label} ({new_job.scheduled_date.strftime('%b %d')}).")
    else:
        messages.success(request, f"Job skipped ({reason}).")
    return redirect("job_detail", job_id=job.id)


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


@require_POST
@role_required("owner", "manager", "crew")
def crew_field_request(request, job_id):
    """Crew submits a field request (customer wants a quote, extra work noticed, etc.).
    Creates a notification for all owners/managers with the details."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    req_type = data.get("type", "quote")  # quote, extra_work, other
    description = (data.get("description") or "").strip()
    if not description:
        return JsonResponse({"error": "Description is required"}, status=400)

    from accounts.models import Notification, User
    customer_name = job.property.customer.name
    crew_name = request.user.get_full_name() or request.user.username
    address = job.property.address or ""

    type_labels = {"quote": "Quote Request", "extra_work": "Extra Work", "other": "Field Request"}
    type_label = type_labels.get(req_type, "Field Request")

    msg = f"[{type_label}] {crew_name} at {customer_name} ({address}): {description}"

    owners_managers = User.objects.filter(
        business=business, role__in=["owner", "manager"]
    ).exclude(id=request.user.id)
    for om in owners_managers:
        Notification.objects.create(
            business=business,
            from_user=request.user,
            to_user=om,
            message=msg,
        )

    # Also add as a job note for record-keeping
    JobNote.objects.create(
        job=job,
        author=request.user,
        text=f"[{type_label}] {description}",
    )

    return JsonResponse({"status": "ok", "message": "Request sent to owner"})


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
    """Add a note scoped to this job, the recurring series, or the property."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    if request.user.role == "crew" and not _user_can_access_job(request.user, job):
        return JsonResponse({"error": "Not assigned to this job"}, status=403)
    data = _request_data(request)
    text = (data.get("text") or "").strip()
    scope = (data.get("scope") or "job").strip().lower()
    if not text:
        return JsonResponse({"error": "Note text is required"}, status=400)
    visibility = (data.get("visibility") or PropertyNote.VISIBILITY_CREW).strip().lower()
    if visibility not in {PropertyNote.VISIBILITY_CREW, PropertyNote.VISIBILITY_INTERNAL}:
        visibility = PropertyNote.VISIBILITY_CREW
    if request.user.role == "crew":
        visibility = PropertyNote.VISIBILITY_CREW
    if scope == "property":
        note = PropertyNote.objects.create(property=job.property, author=request.user, text=text, visibility=visibility)
        return JsonResponse({
            "status": "ok",
            "scope": "property",
            "id": note.id,
            "text": note.text,
            "visibility": note.visibility,
            "author": note.author.get_full_name() or note.author.username,
            "created_at": note.created_at.isoformat(),
            "property_address": job.property.address,
        })
    if scope == "recurring":
        if visibility == PropertyNote.VISIBILITY_INTERNAL:
            return JsonResponse({"error": "Internal notes can be saved to this job or property, but not pushed to recurring future visits."}, status=400)
        if not job.recurring_job_id:
            return JsonResponse({"error": "This job is not linked to a recurring schedule"}, status=400)
        recurring_job = job.recurring_job
        recurring_job.notes = _append_note_text(recurring_job.notes, text)
        recurring_job.save(update_fields=["notes"])
        future_jobs = Job.objects.filter(
            recurring_job=recurring_job,
            scheduled_date__gte=job.scheduled_date,
            status__in=["scheduled", "en_route"],
        )
        for future_job in future_jobs:
            future_job.notes = _append_note_text(future_job.notes, text)
            future_job.save(update_fields=["notes"])
        return JsonResponse({
            "status": "ok",
            "scope": "recurring",
            "id": recurring_job.id,
            "text": text,
            "author": request.user.get_full_name() or request.user.username,
            "created_at": "",
            "future_updated": future_jobs.count(),
        })
    note = JobNote.objects.create(job=job, author=request.user, text=text, visibility=visibility)
    return JsonResponse({
        "status": "ok",
        "scope": "job",
        "id": note.id,
        "text": note.text,
        "visibility": note.visibility,
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
    job_notes_qs = job.job_notes.select_related("author")
    property_notes_qs = job.property.property_notes.select_related("author")
    if request.user.role == "crew":
        job_notes_qs = job_notes_qs.filter(visibility=JobNote.VISIBILITY_CREW)
        property_notes_qs = property_notes_qs.filter(visibility=PropertyNote.VISIBILITY_CREW)
    job_notes = list(
        job_notes_qs.values_list("id", "text", "visibility", "author__first_name", "author__last_name", "author__username", "created_at")
    )
    property_notes = list(
        property_notes_qs.values_list("id", "text", "visibility", "author__first_name", "author__last_name", "author__username", "created_at")
    )
    def fmt(rows, note_type):
        out = []
        for nid, text, visibility, first, last, uname, created in rows:
            name = f"{first} {last}".strip() or uname
            out.append({"id": nid, "text": text, "visibility": visibility, "author": name, "created_at": created.isoformat(), "type": note_type, "note_type": note_type})
        return out
    recurring_notes = []
    if job.recurring_job_id and (job.recurring_job.notes or "").strip():
        recurring_notes.append({
            "id": job.recurring_job_id,
            "text": job.recurring_job.notes.strip(),
            "author": "Recurring schedule",
            "created_at": "",
            "type": "recurring",
            "note_type": "recurring",
        })
    job_note_items = fmt(job_notes, "job")
    property_note_items = fmt(property_notes, "property")
    return JsonResponse({
        "job_notes": job_note_items,
        "property_notes": property_note_items,
        "recurring_notes": recurring_notes,
        "notes": recurring_notes + property_note_items + job_note_items,
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
            sched_end_date = form.cleaned_data.get("scheduled_end_date")
            sched_time = form.cleaned_data.get("scheduled_time") if sched_date else None
            schedule_by = form.cleaned_data.get("schedule_by_date") if not sched_date else None
            total_price_override = form.cleaned_data.get("total_price")
            from decimal import Decimal
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
                        "detail_description": form_data.cleaned_data.get("detail_description") or "",
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

            # Create single job — if end date is set, it spans multiple days
            jobs_created = []
            job = Job.objects.create(
                    property=prop,
                    scheduled_date=sched_date,
                    scheduled_end_date=sched_end_date if (sched_date and sched_end_date and sched_end_date > sched_date) else None,
                    scheduled_time=sched_time,
                    schedule_by_date=schedule_by,
                    assigned_to=assigned_to,
                    assigned_crew=assigned_crew,
                    notes=form.cleaned_data.get("notes") or "",
                    status="scheduled",
                    color=color_val if color_val else None,
                    recurring_job=recurring_job,
                )
            jobs_created.append(job)
            # Set M2M employees (after job is saved)
            if assigned_employees_list:
                job.assigned_employees.set(assigned_employees_list)
            elif assigned_to:
                job.assigned_employees.set([assigned_to])
            # Wave 3: multi-crew M2M. Seed with primary crew (if any), then add
            # any additional crews from the form. Keeps the invariant that the
            # primary crew is always in the crews M2M.
            crew_list = list(form.cleaned_data.get("crews") or [])
            if assigned_crew and assigned_crew not in crew_list:
                crew_list = [assigned_crew] + crew_list
            if crew_list:
                job.crews.set(crew_list)
            assignee_names = ", ".join(e.get_full_name() or e.username for e in assigned_employees_list) if assigned_employees_list else None
            assignee = assigned_crew.name if assigned_crew else (assignee_names or (assigned_to.get_full_name() or assigned_to.username if assigned_to else "Unassigned"))
            if len(crew_list) > 1:
                assignee += f" (+{len(crew_list) - 1} more crews)"
            JobAssignmentLog.objects.create(job=job, user=request.user, details=f"Job created; assigned to {assignee}")
            # Create service items
            first_item = True
            for form_data in formset:
                if form_data.cleaned_data.get("service"):
                    service = form_data.cleaned_data["service"]
                    qty = form_data.cleaned_data["quantity"]
                    unit, rate = get_effective_rate(prop, service)
                    override_price = form_data.cleaned_data.get("unit_price")
                    if override_price is not None:
                        rate = override_price
                    # Total price override: apply to first item, zero out the rest
                    if total_price_override and first_item:
                        rate = total_price_override
                        first_item = False
                    elif total_price_override:
                        rate = Decimal("0")
                    unit = getattr(service, "default_unit", None) or unit
                    item_start = form_data.cleaned_data.get("scheduled_date")
                    item_end = form_data.cleaned_data.get("scheduled_end_date")
                    if item_start and item_end and item_end < item_start:
                        messages.error(request, "Line item end date cannot be before the start date.")
                        return redirect("create_job")
                    JobServiceItem.objects.create(
                        job=job,
                        service=service,
                        description=clean_service_label(service=service),
                        detail_description=form_data.cleaned_data.get("detail_description") or "",
                        quantity=qty,
                        unit=unit,
                        unit_price=rate,
                        scheduled_date=item_start,
                        scheduled_end_date=item_end if item_start and item_end and item_end > item_start else None,
                    )
                    _expand_job_range_for_item(job, item_start, item_end)
            if job.scheduled_end_date:
                msg = f"Multi-day job created for {prop.address} ({sched_date.strftime('%b %d')} — {job.scheduled_end_date.strftime('%b %d')})"
            elif recurring_job:
                msg = f"Recurring job created for {prop.address} ({recurring_job.get_frequency_display()}); first date {sched_date}. Future dates will be generated automatically."
            else:
                msg = f"Job created for {prop.address}" + (f" on {job.scheduled_date}" if job.scheduled_date else " (unscheduled)")
            messages.success(request, msg + ".")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect("job_detail", job_id=job.id)
        else:
            # Form had errors — show them
            error_fields = list(form.errors.keys()) + list(formset.errors[0].keys() if formset.errors else [])
            if error_fields:
                messages.error(request, f"Please fix errors in: {', '.join(error_fields)}")
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
                initial["notes"] = _job_notes_from_estimate(est)
                props = list(est.customer.properties.all().order_by("address")[:1])
                if len(props) == 1:
                    initial["property"] = props[0].id
                for item in est.accepted_line_items():
                    if item.material_cost or item.labor_cost:
                        price = (item.material_cost or 0) + (item.labor_cost or 0)
                        if item.quantity and item.quantity > 0:
                            price = price / item.quantity
                    else:
                        price = item.unit_price
                    formset_initial.append({
                        "service_name": item.description[:120],
                        "detail_description": getattr(item, "detail_description", "") or "",
                        "quantity": item.quantity,
                        "unit_price": price,
                        "scheduled_date": "",
                        "scheduled_end_date": "",
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
    # Revert any linked fertilization rounds to pending before deleting
    try:
        from fertilization.models import ScheduledRound as FertScheduledRound
        # Find by job FK
        linked_fert = list(FertScheduledRound.objects.filter(job=job))
        # Fallback: match by property + date for unlinked rounds
        if not linked_fert and '[Fertilization]' in (job.notes or ''):
            linked_fert = list(FertScheduledRound.objects.filter(
                enrollment__property=job.property,
                scheduled_date=job.scheduled_date,
                status__in=['scheduled', 'completed'],
            ))
        for sr in linked_fert:
            sr.job = None
            sr.status = 'pending'
            sr.save(update_fields=['job', 'status'])
            # Revert enrollment status
            enrollment = sr.enrollment
            completed_count = enrollment.scheduled_rounds.filter(status='completed').count()
            if completed_count == 0:
                enrollment.status = 'enrolled'
            else:
                enrollment.status = 'in_progress'
            enrollment.save(update_fields=['status'])
    except Exception:
        pass

    customer_id = job.property.customer_id
    job.delete()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    messages.success(request, "Job deleted.")
    # Redirect back to referring page if available, otherwise calendar
    referer = request.META.get("HTTP_REFERER", "")
    if referer and "/clients/" in referer:
        return redirect("customer_detail", customer_id=customer_id)
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
    """Create a new meeting or calendar note."""
    business = get_business(request)
    if not business:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse({"error": "No business"}, status=403)
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    # JSON API (from quick-create popover)
    if request.method == "POST" and request.content_type == "application/json":
        data = json.loads(request.body) if request.body else {}
        title = (data.get("title") or "").strip()
        if not title:
            return JsonResponse({"error": "Title is required"}, status=400)
        from customers.models import Customer
        customer = None
        cid = data.get("customer_id")
        if cid:
            customer = Customer.objects.filter(id=cid, business=business).first()
        sched_date = data.get("scheduled_date")
        sched_time = data.get("scheduled_time")
        from datetime import time as dt_time
        time_obj = None
        if sched_time and ":" in str(sched_time):
            parts = str(sched_time).split(":")
            time_obj = dt_time(int(parts[0]), int(parts[1] if len(parts) > 1 else 0))
        meeting = Meeting.objects.create(
            business=business,
            title=title,
            customer=customer,
            scheduled_at=timezone.now(),
            created_by=request.user,
            notes=f"Scheduled for {sched_date}" + (f" at {sched_time}" if sched_time else ""),
        )
        # Store the date/time so it shows on the calendar
        if sched_date:
            try:
                d = datetime.strptime(sched_date, "%Y-%m-%d").date()
                if time_obj:
                    meeting.scheduled_at = timezone.make_aware(datetime.combine(d, time_obj))
                else:
                    meeting.scheduled_at = timezone.make_aware(datetime.combine(d, dt_time(9, 0)))
                meeting.save(update_fields=["scheduled_at"])
            except (ValueError, TypeError):
                pass
        return JsonResponse({"status": "ok", "id": meeting.id})

    # Standard form POST
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
            messages.success(request, f"Meeting added to your schedule.")
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
            messages.success(request, f"Meeting '{meeting.title}' updated.")
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
    messages.success(request, f"Meeting '{title}' deleted.")
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
def mark_job_paid(request, job_id):
    """Quick mark a job as paid — creates a paid invoice with the selected payment method."""
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    payment_method = request.POST.get("payment_method", "cash")

    # Create a paid invoice from this job
    invoice = create_draft_invoice_for_job(job)
    if invoice:
        invoice.status = "paid"
        invoice.payment_method = payment_method
        invoice.paid_at = timezone.now()
        invoice.approved_at = timezone.now()
        invoice.approved_by = request.user
        invoice.save(update_fields=["status", "payment_method", "paid_at", "approved_at", "approved_by"])
        from billing.models import InvoiceAuditLog
        InvoiceAuditLog.objects.create(
            invoice=invoice,
            action="paid",
            user=request.user,
            details={"payment_method": payment_method, "source": "quick_mark_paid"},
        )
        method_label = dict(invoice.PAYMENT_METHOD_CHOICES).get(payment_method, payment_method)
        messages.success(request, f"Job marked as paid via {method_label}. Invoice #{invoice.id} created.")
    else:
        messages.warning(request, "Could not create invoice — no service items on this job.")
    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner", "manager")
def job_bill_now(request, job_id):
    """Create a draft invoice from a job's unbilled service items."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403) if request.headers.get("X-Requested-With") == "XMLHttpRequest" else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)

    if not job.service_items.exists():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Add at least one service before invoicing."}, status=400)
        messages.error(request, "Add at least one service to the job before invoicing.")
        return redirect("job_detail", job_id=job_id)

    invoice = create_draft_invoice_for_job(job)
    if invoice is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "ok", "message": "Covered by prepaid agreement — no invoice needed."})
        messages.success(request, "All services covered by a prepaid agreement — no invoice created.")
        return redirect("job_detail", job_id=job_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "invoice_id": invoice.id})
    messages.success(
        request,
        f"Draft invoice #{invoice.id} created from this job. Review and send from Billing.",
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

    d = job.scheduled_date or _business_today(request.user.business if hasattr(request.user, 'business') else None)
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
        Job.objects.prefetch_related(
            "issues__photos",
            "completion_photos",
            "issues__reported_by",
            "work_visits__service_item__service",
        ),
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
    description = (form.cleaned_data.get("description") or "").strip()
    detail_description = (form.cleaned_data.get("detail_description") or "").strip()
    quantity = form.cleaned_data["quantity"]
    unit_price = form.cleaned_data.get("unit_price")
    item_start = form.cleaned_data.get("scheduled_date")
    item_end = form.cleaned_data.get("scheduled_end_date")
    if item_start and item_end and item_end < item_start:
        messages.error(request, "Line item end date cannot be before the start date.")
        return redirect("job_detail", job_id=job.id)

    unit, rate = get_effective_rate(job.property, service)
    rate = unit_price if unit_price is not None else rate

    item = None
    if description:
        item = JobServiceItem.objects.filter(job=job, service=service, description=description).first()
    elif not detail_description and unit_price is None and not item_start and not item_end:
        item = JobServiceItem.objects.filter(job=job, service=service, description="").first()

    if item:
        item.description = description
        item.detail_description = detail_description
        item.quantity = quantity
        item.unit = unit
        item.unit_price = rate
        item.scheduled_date = item_start
        item.scheduled_end_date = item_end if item_start and item_end and item_end > item_start else None
        item.save()
    else:
        item = JobServiceItem.objects.create(
            job=job,
            service=service,
            description=description,
            detail_description=detail_description,
            quantity=quantity,
            unit=unit,
            unit_price=rate,
            scheduled_date=item_start,
            scheduled_end_date=item_end if item_start and item_end and item_end > item_start else None,
        )
    _expand_job_range_for_item(job, item.scheduled_date, item.scheduled_end_date)

    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner", "manager")
def update_job_service_item(request, job_id, item_id):
    """Update an existing service item's qty, price, or description."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403)
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    item = get_object_or_404(JobServiceItem, id=item_id, job=job)
    data = json.loads(request.body) if request.body else {}
    from decimal import Decimal
    if "quantity" in data:
        try:
            item.quantity = Decimal(str(data["quantity"])) if data["quantity"] else Decimal("1")
            if item.quantity <= 0:
                item.quantity = Decimal("1")
        except (ValueError, TypeError):
            pass
    if "unit_price" in data:
        try:
            item.unit_price = Decimal(str(data["unit_price"])) if data["unit_price"] else Decimal("0")
        except (ValueError, TypeError):
            pass
    if "description" in data:
        item.description = (data["description"] or "")[:255]
    if "detail_description" in data:
        item.detail_description = (data["detail_description"] or "")[:1000]
    if "unit" in data:
        item.unit = (data["unit"] or "ea")[:50]
    if "scheduled_date" in data or "scheduled_end_date" in data:
        try:
            item_start = _parse_iso_date(data.get("scheduled_date"))
            item_end = _parse_iso_date(data.get("scheduled_end_date"))
        except ValueError:
            return JsonResponse({"error": "Invalid line item date."}, status=400)
        if item_start and item_end and item_end < item_start:
            return JsonResponse({"error": "Line item end date cannot be before the start date."}, status=400)
        item.scheduled_date = item_start
        item.scheduled_end_date = item_end if item_start and item_end and item_end > item_start else None
    item.save()
    _expand_job_range_for_item(job, item.scheduled_date, item.scheduled_end_date)
    return JsonResponse({
        "ok": True,
        "line_total": str(item.line_total()),
        "description": item.description or "",
        "detail_description": item.detail_description or "",
        "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else "",
        "scheduled_end_date": item.scheduled_end_date.isoformat() if item.scheduled_end_date else "",
    })


@require_POST
@role_required("owner", "manager")
def add_job_work_visit(request, job_id):
    """Add a non-consecutive return visit to the same job or line item."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403) if _wants_json(request) else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    data = _request_data(request)
    service_item_id = (data.get("service_item") or "").strip()
    service_item = None
    if service_item_id:
        service_item = JobServiceItem.objects.filter(id=service_item_id, job=job).first()
        if service_item is None:
            if _wants_json(request):
                return JsonResponse({"error": "Choose a valid line item for this return visit."}, status=400)
            messages.error(request, "Choose a valid line item for this return visit.")
            return redirect("job_detail", job_id=job.id)
    try:
        visit_start = _parse_iso_date(data.get("scheduled_date"))
        visit_end = _parse_iso_date(data.get("scheduled_end_date"))
    except ValueError:
        if _wants_json(request):
            return JsonResponse({"error": "Choose valid return visit dates."}, status=400)
        messages.error(request, "Choose valid return visit dates.")
        return redirect("job_detail", job_id=job.id)
    if not visit_start:
        if _wants_json(request):
            return JsonResponse({"error": "Choose a return visit date."}, status=400)
        messages.error(request, "Choose a return visit date.")
        return redirect("job_detail", job_id=job.id)
    if visit_start and visit_end and visit_end < visit_start:
        if _wants_json(request):
            return JsonResponse({"error": "Return visit end date cannot be before the start date."}, status=400)
        messages.error(request, "Return visit end date cannot be before the start date.")
        return redirect("job_detail", job_id=job.id)
    visit = JobWorkVisit.objects.create(
        job=job,
        service_item=service_item,
        scheduled_date=visit_start,
        scheduled_end_date=visit_end if visit_end and visit_end > visit_start else None,
        notes=(data.get("notes") or "").strip(),
    )
    if _wants_json(request):
        return JsonResponse({"status": "ok", "visit": _serialize_job_work_visit(visit)})
    messages.success(request, "Return visit added to this job.")
    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner", "manager")
def update_job_work_visit(request, job_id, visit_id):
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    visit = get_object_or_404(JobWorkVisit.objects.select_related("service_item__service"), id=visit_id, job=job)
    data = _request_data(request)
    try:
        visit_start = _parse_iso_date(data.get("scheduled_date"))
        visit_end = _parse_iso_date(data.get("scheduled_end_date"))
    except ValueError:
        return JsonResponse({"error": "Choose valid return visit dates."}, status=400)
    if not visit_start:
        return JsonResponse({"error": "Choose a return visit date."}, status=400)
    if visit_start and visit_end and visit_end < visit_start:
        return JsonResponse({"error": "Return visit end date cannot be before the start date."}, status=400)
    visit.scheduled_date = visit_start
    visit.scheduled_end_date = visit_end if visit_end and visit_end > visit_start else None
    if "notes" in data:
        visit.notes = (data.get("notes") or "").strip()
    if "service_item" in data:
        service_item_id = (data.get("service_item") or "").strip()
        if service_item_id:
            service_item = JobServiceItem.objects.filter(id=service_item_id, job=job).first()
            if service_item is None:
                return JsonResponse({"error": "Choose a valid line item for this return visit."}, status=400)
            visit.service_item = service_item
        else:
            visit.service_item = None
    visit.save()
    return JsonResponse({"status": "ok", "visit": _serialize_job_work_visit(visit)})


@require_POST
@role_required("owner", "manager")
def remove_job_work_visit(request, job_id, visit_id):
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403) if _wants_json(request) else redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)
    JobWorkVisit.objects.filter(id=visit_id, job=job).delete()
    if _wants_json(request):
        return JsonResponse({"status": "ok", "visit_id": visit_id})
    messages.success(request, "Return visit removed.")
    return redirect("job_detail", job_id=job.id)


@require_POST
@role_required("owner", "manager")
def edit_job(request, job_id):
    """Update job details: date, time, crew, notes, status."""
    business = get_business(request)
    if not business:
        return redirect("/")
    job = get_object_or_404(Job, id=job_id, property__customer__business=business)

    scheduled_date = request.POST.get("scheduled_date", "").strip()
    scheduled_end_date_str = request.POST.get("scheduled_end_date", "").strip()
    scheduled_time = request.POST.get("scheduled_time", "").strip()
    crew_id = request.POST.get("assigned_crew", "").strip()
    employee_id = request.POST.get("assigned_to", "").strip()
    notes = request.POST.get("notes")
    status = request.POST.get("status", "").strip()

    if scheduled_date:
        try:
            job.scheduled_date = date.fromisoformat(scheduled_date)
        except (ValueError, TypeError):
            pass
    # Wave 6: accept optional end-date to make a job span multiple days without
    # recreating it. Empty string clears the end date (single-day job).
    if "scheduled_end_date" in request.POST:
        if scheduled_end_date_str:
            try:
                parsed_end = date.fromisoformat(scheduled_end_date_str)
                # Only set if strictly after the start date; same day = single-day (clear it).
                if job.scheduled_date and parsed_end > job.scheduled_date:
                    job.scheduled_end_date = parsed_end
                else:
                    job.scheduled_end_date = None
            except (ValueError, TypeError):
                pass
        else:
            # Empty string means user cleared the field → single-day job.
            job.scheduled_end_date = None
    if scheduled_time:
        try:
            from datetime import time as dt_time
            parts = scheduled_time.split(":")
            job.scheduled_time = dt_time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, TypeError, IndexError):
            pass
    elif scheduled_time == "":
        job.scheduled_time = None

    primary_crew_changed = False
    new_primary_crew = None
    if crew_id:
        new_primary_crew = Crew.objects.filter(id=crew_id, business=business).first()
        if new_primary_crew and new_primary_crew.id != job.assigned_crew_id:
            primary_crew_changed = True
        job.assigned_crew = new_primary_crew
        job.assigned_to = None
    elif crew_id == "":
        job.assigned_crew = None
    if employee_id:
        from accounts.models import User
        job.assigned_to = User.objects.filter(id=employee_id, business=business).first()
        job.assigned_crew = None
    if notes is not None:
        job.notes = notes[:2000]
    if status and status in ("scheduled", "skipped", "cancelled"):
        job.status = status

    job.save()
    # Wave 3: keep crews M2M invariant — primary crew is always in the list.
    # If user changed primary via this form, add the new primary. We do NOT
    # remove the old primary or any other crews — that's what the create-job
    # form's "Additional crews" field is for.
    if primary_crew_changed and new_primary_crew:
        job.crews.add(new_primary_crew)
    messages.success(request, "Job updated.")
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
                    if d < _business_today(business):
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


# ═══════════════════════════════════════════════
# Mowing Management
# ═══════════════════════════════════════════════

@role_required("owner", "manager")
def mowing_hub(request):
    """Mowing management page: see all mowing clients, frequencies, upcoming jobs, send bulk messages."""
    business = get_business(request)
    if not business:
        return redirect("/")

    today = _business_today(business)
    # Week starts on Sunday (isoweekday: Sun=7, so offset = weekday+1 mod 7)
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)  # Sunday
    week_end = week_start + timedelta(days=6)  # Saturday

    # Find mowing-related services — broad match for lookups (catches "Mowing", "Field Mowing", etc.)
    from pricing.models import ServiceTemplate
    mowing_services = ServiceTemplate.objects.filter(
        business=business, active=True, name__icontains="mow"
    )
    mowing_svc_ids = set(mowing_services.values_list("id", flat=True))

    # Get all active recurring jobs that include a mowing service
    recurring_jobs = RecurringJob.objects.filter(
        property__customer__business=business,
        active=True,
    ).select_related("property__customer", "assigned_crew", "assigned_to")

    mowing_recurrences = []
    for rj in recurring_jobs:
        # Check if service_snapshot contains a mowing service
        is_mowing = False
        for svc_snap in (rj.service_snapshot or []):
            sid = svc_snap.get("service_id")
            if sid and int(sid) in mowing_svc_ids:
                is_mowing = True
                break
        if not is_mowing:
            # Fallback: check notes for "mow"
            if "mow" in (rj.notes or "").lower():
                is_mowing = True
        if is_mowing:
            mowing_recurrences.append(rj)

    # Gather entries per property (not per customer) so multi-property clients show separate rows
    customer_map = {}  # key = recurring_job_id -> {customer, properties, frequency, crew, recurring_id}
    for rj in mowing_recurrences:
        cust = rj.property.customer
        key = rj.id  # Key by RecurringJob so each property is a separate entry
        # Find the specific mowing service ID from this RecurringJob's snapshot
        rj_mow_svc_id = None
        for snap in (rj.service_snapshot or []):
            sid = snap.get("service_id")
            if sid and int(sid) in mowing_svc_ids:
                rj_mow_svc_id = int(sid)
                break
        customer_map[key] = {
            "customer": cust,
            "properties": [rj.property],
            "frequency": rj.get_frequency_display(),
            "frequency_key": rj.frequency,
            "crew": rj.assigned_crew.name if rj.assigned_crew else (rj.assigned_to.get_full_name() if rj.assigned_to else "Unassigned"),
            "recurring_id": rj.id,
            "recurring_job": rj,
            "property_address": rj.property.address,
            "mow_svc_id": rj_mow_svc_id,
        }

    # Also find customers with mowing jobs this week (even without recurring setup)
    # Match broadly: mowing service items OR "[Mowing]" in notes
    this_week_jobs = Job.objects.filter(
        property__customer__business=business,
        scheduled_date__gte=week_start,
        scheduled_date__lte=week_end,
    ).filter(
        Q(service_items__service__in=mowing_services) |
        Q(notes__icontains="[Mowing]")
    ).select_related("property__customer", "assigned_crew", "assigned_to").distinct()

    # Build week schedule keyed by property_id (not customer_id)
    week_schedule = {}
    # Also build customer-level schedule for fallback
    week_schedule_by_customer = {}
    for job in this_week_jobs:
        pid = job.property_id
        cid = job.property.customer_id
        if pid not in week_schedule:
            week_schedule[pid] = []
        week_schedule[pid].append(job)
        if cid not in week_schedule_by_customer:
            week_schedule_by_customer[cid] = []
        week_schedule_by_customer[cid].append(job)

    # Also add one-off mowing clients from this week who aren't in recurring
    # Check if any property from this week's jobs is NOT already in customer_map
    existing_prop_ids = set()
    for key, data in customer_map.items():
        for prop in data["properties"]:
            existing_prop_ids.add(prop.id)
    for pid, jobs in week_schedule.items():
        if pid not in existing_prop_ids:
            cust = jobs[0].property.customer
            customer_map[f"oneoff_{pid}"] = {
                "customer": cust,
                "properties": [jobs[0].property],
                "property_address": jobs[0].property.address,
                "frequency": "One-time",
                "frequency_key": "one_time",
                "crew": (jobs[0].assigned_crew.name if jobs[0].assigned_crew
                         else (jobs[0].assigned_to.get_full_name() if jobs[0].assigned_to else "Unassigned")),
                "recurring_id": None,
            }

    # Build sorted client list
    clients = []
    freq_order = {"weekly": 0, "10day": 1, "biweekly": 2, "monthly": 3, "custom": 4, "one_time": 5}
    # Calculate avg duration per property (for all properties in customer_map)
    from django.db.models import Avg, F, ExpressionWrapper, DurationField
    all_prop_ids = set()
    for data in customer_map.values():
        for p in data["properties"]:
            all_prop_ids.add(p.id)

    prop_avg_durations = {}
    if all_prop_ids:
        avgs = Job.objects.filter(
            property_id__in=all_prop_ids,
            status="completed",
            started_at__isnull=False,
            completed_at__isnull=False,
        ).values('property_id').annotate(
            avg_dur=Avg(ExpressionWrapper(F('completed_at') - F('started_at'), output_field=DurationField()))
        )
        for row in avgs:
            dur = row['avg_dur']
            if dur:
                prop_avg_durations[row['property_id']] = int(dur.total_seconds() / 60)

    # Query mowing job history for the current year per property (for progress tracker)
    # Match broadly: mowing service items OR "[Mowing]" in notes (same as how jobs are created)
    from decimal import Decimal
    year_start_date = today.replace(month=1, day=1)
    mow_jobs_this_year = Job.objects.filter(
        property_id__in=all_prop_ids,
        scheduled_date__gte=year_start_date,
    ).filter(
        Q(service_items__service__in=mowing_services) |
        Q(notes__icontains="[Mowing]")
    ).select_related("property").prefetch_related("service_items").order_by("scheduled_date").distinct()

    # Deduplicate — the Q with OR + JOIN can produce duplicate job rows
    seen_job_ids = set()
    prop_mow_history = {}
    prop_earned_revenue = {}  # per-property earned revenue (completed mowing jobs)
    for job in mow_jobs_this_year:
        if job.id in seen_job_ids:
            continue
        seen_job_ids.add(job.id)
        pid = job.property_id
        if pid not in prop_mow_history:
            prop_mow_history[pid] = []
        # Sum mowing service item revenue for this job
        job_rev = sum(
            (si.quantity or 1) * (si.unit_price or 0)
            for si in job.service_items.all()
            if si.service_id in mowing_svc_ids
        )
        prop_mow_history[pid].append({
            "status": job.status,
            "date": job.scheduled_date,
            "revenue": job_rev,
        })
        if job.status == "completed":
            prop_earned_revenue[pid] = prop_earned_revenue.get(pid, Decimal("0")) + job_rev

    for key, data in customer_map.items():
        # Get this week's jobs by property ID only — no customer-level fallback
        # (fallback would mix jobs from different properties for the same client)
        prop_ids = [p.id for p in data["properties"]]
        this_week = []
        for pid in prop_ids:
            this_week.extend(week_schedule.get(pid, []))
        data["this_week_jobs"] = this_week
        data["next_job_date"] = this_week[0].scheduled_date if this_week else None
        data["has_email"] = bool(data["customer"].email)
        data["has_phone"] = bool(data["customer"].phone)
        # Average duration from all property history
        prop_ids = [p.id for p in data["properties"]]
        mins_list = [prop_avg_durations[pid] for pid in prop_ids if pid in prop_avg_durations]
        if mins_list:
            avg_mins = sum(mins_list) // len(mins_list)
            data["avg_duration"] = f"{avg_mins}m" if avg_mins < 60 else f"{avg_mins // 60}h {avg_mins % 60}m"
            data["avg_duration_mins"] = avg_mins
        else:
            data["avg_duration"] = None
            data["avg_duration_mins"] = 0
        # Mowing progress for the year (per-property)
        prop_id = prop_ids[0] if prop_ids else None
        history = prop_mow_history.get(prop_id, []) if prop_id else []
        data["mow_completed"] = sum(1 for h in history if h["status"] == "completed")
        data["mow_scheduled"] = sum(1 for h in history if h["status"] == "scheduled")
        data["mow_skipped"] = sum(1 for h in history if h["status"] == "skipped")
        data["mow_total"] = len(history)
        data["mow_history"] = history
        data["earned_revenue"] = prop_earned_revenue.get(prop_id, Decimal("0")) if prop_id else Decimal("0")
        # Per-cut pricing: use the specific mowing service from this RecurringJob's snapshot
        # Priority: PropertyServiceRate override → RecurringJob snapshot price → service default
        from pricing.utils import get_effective_rate
        from decimal import Decimal as _Dec
        data["per_cut_rate"] = None
        prop_obj = data["properties"][0] if data["properties"] else None
        rj_obj = data.get("recurring_job")
        # Resolve the specific mowing service for this property
        mow_svc = None
        if data.get("mow_svc_id"):
            mow_svc = mowing_services.filter(id=data["mow_svc_id"]).first()
        if not mow_svc:
            mow_svc = mowing_services.first()
        if prop_obj and mow_svc:
            _unit, _rate = get_effective_rate(prop_obj, mow_svc)
            if _rate > 0:
                data["per_cut_rate"] = _rate
            else:
                # Fallback: check RecurringJob snapshot for saved price
                if rj_obj and rj_obj.service_snapshot:
                    for snap in rj_obj.service_snapshot:
                        sp = snap.get("unit_price")
                        if sp and _Dec(str(sp)) > 0:
                            data["per_cut_rate"] = _Dec(str(sp))
                            break

        # Missed client detection: no job this week + last mow was too long ago
        data["is_missed"] = False
        if not data["this_week_jobs"] and data["frequency_key"] in ("weekly", "biweekly"):
            completed_dates = [h["date"] for h in history if h["status"] == "completed"]
            if completed_dates:
                last_mow = max(completed_dates)
                days_since = (today - last_mow).days
                threshold = 10 if data["frequency_key"] == "weekly" else 21
                if days_since > threshold:
                    data["is_missed"] = True
                    data["days_since_last_mow"] = days_since
            elif history:
                # Has been scheduled before but never completed
                data["is_missed"] = True
                data["days_since_last_mow"] = None
        clients.append(data)
    clients.sort(key=lambda c: (freq_order.get(c["frequency_key"], 9), c["customer"].name))
    missed_count = sum(1 for c in clients if c.get("is_missed"))

    # Stats
    from decimal import Decimal
    weekly_count = sum(1 for c in clients if c["frequency_key"] == "weekly")
    biweekly_count = sum(1 for c in clients if c["frequency_key"] == "biweekly")
    tenday_count = sum(1 for c in clients if c["frequency_key"] == "10day")
    scheduled_this_week = sum(1 for c in clients if c["this_week_jobs"])
    total_est_minutes = sum(c.get("avg_duration_mins", 0) for c in clients if c["this_week_jobs"])
    est_day_display = f"{total_est_minutes // 60}h {total_est_minutes % 60}m" if total_est_minutes else "—"

    # Revenue projections
    freq_cuts_per_week = {"weekly": Decimal("1"), "10day": Decimal("0.7"), "biweekly": Decimal("0.5"), "monthly": Decimal("0.23")}
    weekly_revenue = Decimal("0")
    for c in clients:
        rate = c.get("per_cut_rate") or Decimal("0")
        freq = c.get("frequency_key", "weekly")
        weekly_revenue += rate * freq_cuts_per_week.get(freq, Decimal("0.5"))
    monthly_revenue = (weekly_revenue * Decimal("4.33")).quantize(Decimal("0.01"))
    season_revenue = (weekly_revenue * Decimal("30")).quantize(Decimal("0.01"))
    weekly_revenue = weekly_revenue.quantize(Decimal("0.01"))

    # Actual mowing revenue earned this year
    year_start = date(today.year, 1, 1)
    actual_mowing_revenue = Decimal("0")
    todays_mowing_revenue = Decimal("0")
    if mowing_services.exists():
        actual_mowing_revenue = JobServiceItem.objects.filter(
            service__in=mowing_services,
            job__property__customer__business=business,
            job__status="completed",
            job__scheduled_date__gte=year_start,
        ).aggregate(total=Sum(F("quantity") * F("unit_price")))["total"] or Decimal("0")
        # Today's projected mowing revenue (all mowing jobs scheduled today)
        todays_mowing_revenue = JobServiceItem.objects.filter(
            service__in=mowing_services,
            job__property__customer__business=business,
            job__scheduled_date=today,
        ).aggregate(total=Sum(F("quantity") * F("unit_price")))["total"] or Decimal("0")

    # Customers + crews for "Add Mowing Client" modal
    from customers.models import Customer
    all_customers = Customer.objects.filter(business=business).prefetch_related('properties').order_by('name')
    customers_json = json.dumps([
        {"id": c.id, "name": c.name, "properties": [{"id": p.id, "address": p.address} for p in c.properties.all()]}
        for c in all_customers
    ])
    crews = Crew.objects.filter(business=business).order_by("name")

    can_see_pricing = request.user.role in ("owner", "manager")

    return render(request, "jobs/mowing_hub.html", {
        "clients": clients,
        "total_count": len(clients),
        "weekly_count": weekly_count,
        "biweekly_count": biweekly_count,
        "tenday_count": tenday_count,
        "scheduled_this_week": scheduled_this_week,
        "missed_count": missed_count,
        "est_day_display": est_day_display,
        "week_start": week_start,
        "week_end": week_end,
        "today": today,
        "customers_json": customers_json,
        "crews": crews,
        "can_see_pricing": can_see_pricing,
        "weekly_revenue": weekly_revenue,
        "monthly_revenue": monthly_revenue,
        "season_revenue": season_revenue,
        "actual_mowing_revenue": actual_mowing_revenue,
        "todays_mowing_revenue": todays_mowing_revenue,
    })


@require_POST
@role_required("owner", "manager")
def mowing_bulk_message(request):
    """Send a bulk email to selected mowing clients (e.g., rain delay notice)."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "Forbidden"}, status=403)

    from businesses.email_sender import send_business_email, is_email_configured
    if not is_email_configured(business):
        return JsonResponse({"error": "Email not configured. Connect Gmail in Settings."}, status=400)

    data = json.loads(request.body)
    customer_ids = data.get("customer_ids", [])
    subject = (data.get("subject") or "").strip()
    message_body = (data.get("message") or "").strip()

    if not customer_ids or not message_body:
        return JsonResponse({"error": "Select clients and enter a message."}, status=400)

    from customers.models import Customer, ClientMessage

    customers = Customer.objects.filter(id__in=customer_ids, business=business)
    sent = 0
    failed = 0
    for cust in customers:
        if not cust.email:
            failed += 1
            continue
        ok, _detail = send_business_email(
            business=business,
            to=cust.email,
            subject=subject or f"Update from {business.name}",
            body_text=message_body.replace("{{customer_name}}", cust.name).replace("{{business_name}}", business.name),
            reply_to=[business.contact_email] if business.contact_email else None,
        )
        if ok:
            ClientMessage.objects.create(
                customer=cust,
                channel="email",
                direction=ClientMessage.DIRECTION_SENT,
                subject=subject or f"Update from {business.name}",
                body=message_body.replace("{{customer_name}}", cust.name),
                to_address=cust.email,
                created_by=request.user,
            )
            sent += 1
        else:
            failed += 1

    return JsonResponse({"sent": sent, "failed": failed})


@require_POST
@role_required("owner", "manager")
def add_mowing_client(request):
    """Create a recurring mowing job for a customer/property."""
    business = get_business(request)
    if not business:
        messages.error(request, "Forbidden")
        return redirect("mowing_hub")

    from pricing.models import ServiceTemplate
    from customers.models import Customer
    from pricing.utils import get_effective_rate

    customer_id = request.POST.get("customer_id")
    property_id = request.POST.get("property_id")
    frequency = request.POST.get("frequency", "weekly")
    crew_id = request.POST.get("crew_id")
    price_per_cut = request.POST.get("price_per_cut", "").strip()

    if not customer_id or not property_id:
        messages.error(request, "Customer and property are required.")
        return redirect("mowing_hub")

    customer = get_object_or_404(Customer, id=customer_id, business=business)
    prop = get_object_or_404(Property, id=property_id, customer=customer)

    # Find or auto-create mowing service (exact "Mowing" preferred)
    mowing_svc = _get_mowing_service(business)
    if not mowing_svc:
        mowing_svc = ServiceTemplate.objects.create(
            business=business,
            name="Mowing",
            default_unit="visit",
            default_rate=0,
            pricing_method="flat",
            active=True,
        )
        messages.info(request, "A 'Mowing' service was created. Set your pricing in Service Pricing.")

    # Save per-client price override if provided
    from pricing.models import PropertyServiceRate
    if price_per_cut:
        try:
            from decimal import Decimal
            rate_val = Decimal(price_per_cut)
            PropertyServiceRate.objects.update_or_create(
                property=prop,
                service=mowing_svc,
                defaults={"override_rate": rate_val},
            )
        except (ValueError, TypeError):
            pass

    unit, rate = get_effective_rate(prop, mowing_svc)
    service_snapshot = [{"service_id": mowing_svc.id, "quantity": "1", "unit": unit, "unit_price": str(rate)}]

    crew = Crew.objects.filter(id=crew_id, business=business).first() if crew_id else None

    RecurringJob.objects.create(
        property=prop,
        frequency=frequency,
        start_date=_business_today(business),
        active=True,
        assigned_crew=crew,
        service_snapshot=service_snapshot,
    )
    price_msg = f" at ${price_per_cut}/cut" if price_per_cut else ""
    messages.success(request, f"Added {customer.name} as a {dict(RecurringJob.FREQUENCY_CHOICES).get(frequency, frequency)} mowing client{price_msg}.")
    return redirect("mowing_hub")


@require_POST
@role_required("owner", "manager")
def mowing_fix_prices(request):
    """One-click fix: update all $0 mowing JobServiceItems with the correct price from PropertyServiceRate or RecurringJob snapshot."""
    business = get_business(request)
    if not business:
        return redirect("mowing_hub")

    from decimal import Decimal
    from pricing.models import ServiceTemplate
    from pricing.utils import get_effective_rate

    mowing_svcs = ServiceTemplate.objects.filter(business=business, active=True, name__icontains="mow")
    mowing_svc_ids = set(mowing_svcs.values_list("id", flat=True))
    if not mowing_svc_ids:
        messages.warning(request, "No mowing service found.")
        return redirect("mowing_hub")

    # Find all $0 or NULL mowing JobServiceItems for this business
    zero_items = JobServiceItem.objects.filter(
        service_id__in=mowing_svc_ids,
        job__property__customer__business=business,
        job__status__in=["scheduled", "en_route"],
    ).filter(
        Q(unit_price=Decimal("0")) | Q(unit_price__isnull=True)
    ).select_related("job__property", "service")

    fixed = 0
    for item in zero_items:
        try:
            prop = item.job.property
            svc = item.service
            new_price = None

            # 1. PropertyServiceRate
            _unit, _rate = get_effective_rate(prop, svc)
            if _rate > 0:
                new_price = _rate

            # 2. RecurringJob snapshot
            if not new_price:
                rj = RecurringJob.objects.filter(property=prop, active=True).first()
                if rj and rj.service_snapshot:
                    for snap in rj.service_snapshot:
                        sp = snap.get("unit_price")
                        if sp and Decimal(str(sp)) > 0:
                            new_price = Decimal(str(sp))
                            break
            if new_price:
                item.unit_price = new_price
                item.save(update_fields=["unit_price"])
                fixed += 1
        except Exception:
            continue

    if fixed:
        messages.success(request, f"Fixed prices on {fixed} scheduled mowing jobs.")
    else:
        messages.info(request, "No $0 mowing jobs found to fix. Set prices on the mowing hub first, then click Fix Prices.")
    return redirect("mowing_hub")


@require_POST
@role_required("owner", "manager")
def mowing_update_price(request):
    """Update the per-cut price for a mowing client (inline edit from mowing hub)."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    property_id = data.get("property_id")
    price = data.get("price", "").strip() if data.get("price") else ""

    if not property_id:
        return JsonResponse({"error": "Missing property_id"}, status=400)

    prop = get_object_or_404(Property, id=property_id, customer__business=business)

    from pricing.models import ServiceTemplate, PropertyServiceRate
    mowing_svc = _get_mowing_service(business)
    if not mowing_svc:
        return JsonResponse({"error": "No mowing service found"}, status=404)

    if price:
        from decimal import Decimal
        try:
            rate_val = Decimal(price)
            PropertyServiceRate.objects.update_or_create(
                property=prop, service=mowing_svc,
                defaults={"override_rate": rate_val},
            )
            # Also update RecurringJob service_snapshot so price persists even if PropertyServiceRate is lost
            for rj in RecurringJob.objects.filter(property=prop, active=True):
                if rj.service_snapshot:
                    updated = False
                    for snap in rj.service_snapshot:
                        if str(snap.get("service_id")) == str(mowing_svc.id):
                            snap["unit_price"] = str(rate_val)
                            updated = True
                    if updated:
                        rj.save(update_fields=["service_snapshot"])
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid price"}, status=400)
    else:
        PropertyServiceRate.objects.filter(property=prop, service=mowing_svc).delete()

    return JsonResponse({"ok": True})


@require_POST
@role_required("owner", "manager")
def mowing_update_crew(request):
    """Update crew assignment for a recurring mowing client."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    recurring_id = data.get("recurring_id")
    crew_id = data.get("crew_id", "")

    if not recurring_id:
        return JsonResponse({"error": "Missing recurring_id"}, status=400)

    rj = get_object_or_404(RecurringJob, id=recurring_id, property__customer__business=business)

    if crew_id:
        crew = Crew.objects.filter(id=crew_id, business=business).first()
        rj.assigned_crew = crew
    else:
        rj.assigned_crew = None
    rj.save(update_fields=["assigned_crew"])
    return JsonResponse({"ok": True})


@require_POST
@role_required("owner", "manager")
def mowing_remove_client(request):
    """Remove a client from the mowing hub by deactivating their recurring job. Client stays in CRM."""
    business = get_business(request)
    if not business:
        return redirect("mowing_hub")
    recurring_id = request.POST.get("recurring_id")
    if not recurring_id:
        messages.error(request, "Missing client ID.")
        return redirect("mowing_hub")
    rj = get_object_or_404(RecurringJob, id=recurring_id, property__customer__business=business)
    customer_name = rj.property.customer.name
    prop = rj.property

    # Deactivate recurring job
    rj.active = False
    rj.save(update_fields=["active"])

    # Delete all future scheduled jobs for this property (keep completed/skipped)
    today = _business_today(business)
    future_scheduled = Job.objects.filter(
        property_id=prop.id,
        scheduled_date__gte=today,
        status="scheduled",
    )
    del_count = future_scheduled.count()
    if del_count:
        sched_ids = list(future_scheduled.values_list("id", flat=True))
        JobServiceItem.objects.filter(job_id__in=sched_ids).delete()
        Job.objects.filter(id__in=sched_ids).delete()

    del_msg = f" Removed {del_count} scheduled job{'s' if del_count != 1 else ''} from the calendar." if del_count else ""
    messages.success(request, f"Removed {customer_name} from mowing. Client remains in your CRM.{del_msg}")
    return redirect("mowing_hub")


@require_POST
@role_required("owner", "manager")
def mowing_update_frequency(request):
    """Update frequency for a recurring mowing client and reschedule future jobs."""
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    recurring_id = data.get("recurring_id")
    new_frequency = data.get("frequency", "").strip()

    if not recurring_id or new_frequency not in ("weekly", "10day", "biweekly", "monthly"):
        return JsonResponse({"error": "Invalid parameters"}, status=400)

    rj = get_object_or_404(RecurringJob, id=recurring_id, property__customer__business=business)
    old_frequency = rj.frequency
    rj.frequency = new_frequency
    rj.save(update_fields=["frequency"])

    # If frequency actually changed, reschedule future jobs
    deleted = 0
    created = 0
    if old_frequency != new_frequency:
        from decimal import Decimal
        from pricing.models import ServiceTemplate
        from pricing.utils import get_effective_rate

        today = _business_today(business)
        prop = rj.property

        # Find the primary mowing service (for creating new jobs)
        mowing_svc = _get_mowing_service(business)

        # Find future unstarted mowing jobs BEFORE deleting — capture the date window
        # Match by recurring_job OR by property + mowing service (for legacy jobs without recurring_job link)
        mowing_svc_ids = set(ServiceTemplate.objects.filter(
            business=business, active=True, name__icontains="mow"
        ).values_list("id", flat=True))
        future_jobs = Job.objects.filter(
            property=prop,
            scheduled_date__gt=today,
            status__in=["scheduled"],
        ).filter(
            Q(recurring_job=rj) | Q(service_items__service_id__in=mowing_svc_ids)
        ).distinct().order_by('scheduled_date')

        # Capture the original start and end dates from the existing schedule
        first_future = future_jobs.first()
        last_future = future_jobs.last()
        season_start = first_future.scheduled_date if first_future else (today + timedelta(days=1))
        season_end = last_future.scheduled_date if last_future else date(today.year, 10, 31)
        if season_end < today:
            season_end = date(today.year + 1, 10, 31)

        # Now delete them
        deleted = future_jobs.count()
        JobServiceItem.objects.filter(job__in=future_jobs).delete()
        future_jobs.delete()

        interval = {"weekly": 7, "10day": 10, "biweekly": 14, "monthly": 30}.get(new_frequency, 7)

        # Get price
        job_unit = "visit"
        job_rate = Decimal("0")
        if mowing_svc:
            job_unit, job_rate = get_effective_rate(prop, mowing_svc)
            if job_rate == 0 and rj.service_snapshot:
                for snap in rj.service_snapshot:
                    sp = snap.get("unit_price")
                    if sp and Decimal(str(sp)) > 0:
                        job_rate = Decimal(str(sp))
                        job_unit = snap.get("unit", "visit")
                        break

        # Anchor new cadence from the last completed service, even if that
        # service happened before the current future schedule window.
        last_completed_date = (
            Job.objects.filter(
                property=prop,
                scheduled_date__lte=today,
                status="completed",
            )
            .filter(Q(recurring_job=rj) | Q(service_items__service_id__in=mowing_svc_ids))
            .order_by("-scheduled_date")
            .values_list("scheduled_date", flat=True)
            .first()
        )

        # Find completed/in_progress/skipped mowing jobs in the future season
        # window so we schedule around preserved jobs, not on top of them.
        existing_done_dates = set()
        done_dates = list(
            Job.objects.filter(
                property=prop,
                scheduled_date__gte=season_start,
                scheduled_date__lte=season_end,
                status__in=["completed", "in_progress", "skipped"],
            )
            .filter(Q(recurring_job=rj) | Q(service_items__service_id__in=mowing_svc_ids))
            .values_list("scheduled_date", flat=True)
            .distinct()
        )
        existing_done_dates = set(done_dates)

        # Start scheduling from last completed service + interval. If that date
        # is no longer in the future, keep advancing by the new cadence.
        if last_completed_date:
            next_start = last_completed_date + timedelta(days=interval)
            while next_start <= today:
                next_start += timedelta(days=interval)
        else:
            next_start = season_start

        # Re-generate jobs with new frequency, flowing from last completed job
        current_date = next_start
        while current_date <= season_end:
            if current_date in existing_done_dates:
                current_date += timedelta(days=interval)
                continue
            job = Job.objects.create(
                property=prop,
                scheduled_date=current_date,
                status="scheduled",
                notes=f"[Mowing] {prop.customer.name}",
                assigned_crew=rj.assigned_crew,
                assigned_to=rj.assigned_to,
                recurring_job=rj,
            )
            if mowing_svc:
                JobServiceItem.objects.create(
                    job=job,
                    service=mowing_svc,
                    description="Mowing",
                    quantity=1,
                    unit=job_unit,
                    unit_price=job_rate,
                )
            created += 1
            current_date += timedelta(days=interval)

    return JsonResponse({
        "ok": True,
        "deleted": deleted,
        "created": created,
        "message": f"Changed to {new_frequency}. Removed {deleted} old jobs, created {created} new ones." if deleted or created else "",
    })


@require_POST
@role_required("owner", "manager")
def mowing_bulk_schedule(request):
    """Batch-create mowing jobs — once or for the entire season based on frequency."""
    business = get_business(request)
    if not business:
        return redirect("/")

    from decimal import Decimal
    from pricing.models import ServiceTemplate
    from pricing.utils import get_effective_rate

    property_ids = request.POST.getlist("property_ids")
    schedule_date_str = request.POST.get("schedule_date", "")
    schedule_mode = request.POST.get("schedule_mode", "once")
    season_end_str = request.POST.get("season_end", "")

    import logging as _log
    _log.getLogger(__name__).warning(
        "MOWING BULK SCHEDULE REQUEST: property_ids=%s, mode=%s, date=%s, end=%s",
        property_ids, schedule_mode, schedule_date_str, season_end_str,
    )

    if not property_ids or not schedule_date_str:
        messages.error(request, "Select clients and pick a start date.")
        return redirect("mowing_hub")

    try:
        schedule_date = date.fromisoformat(schedule_date_str)
    except (ValueError, TypeError):
        messages.error(request, "Invalid date.")
        return redirect("mowing_hub")

    # Season end date
    season_end = None
    if schedule_mode == "season" and season_end_str:
        try:
            season_end = date.fromisoformat(season_end_str)
        except (ValueError, TypeError):
            pass
    if schedule_mode == "season" and not season_end:
        # Default: end of October
        season_end = date(schedule_date.year, 10, 31)

    # Use primary "Mowing" service for creating new jobs
    mowing_svc = _get_mowing_service(business)
    # Broad match for finding existing jobs (catches "Mowing", "Field Mowing", etc.)
    all_mowing_svc_ids = _get_mowing_service_ids(business)

    properties = Property.objects.filter(
        id__in=property_ids, customer__business=business
    ).select_related("customer")

    # Get frequency per property from their mowing RecurringJob

    prop_frequencies = {}
    prop_crews = {}
    for rj in RecurringJob.objects.filter(property_id__in=property_ids, active=True).select_related('assigned_crew', 'assigned_to'):
        is_mowing = False
        if rj.service_snapshot:
            for snap in rj.service_snapshot:
                sid = snap.get("service_id")
                if sid and int(sid) in all_mowing_svc_ids:
                    is_mowing = True
                    break
        if not is_mowing and not rj.service_snapshot:
            is_mowing = True  # Legacy: no snapshot, assume mowing
        if is_mowing:
            prop_frequencies[rj.property_id] = rj.frequency
            prop_crews[rj.property_id] = rj

    import logging
    logger = logging.getLogger(__name__)

    created = 0
    deleted = 0
    for prop in properties:
        freq = prop_frequencies.get(prop.id)
        rj = prop_crews.get(prop.id)
        if not freq:
            # No mowing RecurringJob found — check if there's ANY RecurringJob for this property
            any_rj = RecurringJob.objects.filter(property_id=prop.id, active=True).first()
            if any_rj:
                freq = any_rj.frequency
                rj = any_rj
                logger.warning(
                    "MOWING SCHEDULE: prop_id=%s fell through mowing filter, using RecurringJob %s freq=%s",
                    prop.id, any_rj.id, any_rj.frequency,
                )
            else:
                freq = "weekly"
                logger.warning(
                    "MOWING SCHEDULE: prop_id=%s has NO RecurringJob at all, defaulting to weekly",
                    prop.id,
                )
        logger.warning(
            "MOWING SCHEDULE: prop_id=%s (%s) → freq=%s, interval=%d days",
            prop.id, prop.address, freq,
            {"weekly": 7, "10day": 10, "biweekly": 14, "monthly": 30}.get(freq, 7),
        )

        # Get price: prefer PropertyServiceRate override, then RecurringJob snapshot, then service default
        job_unit = "visit"
        job_rate = Decimal("0")
        if mowing_svc:
            job_unit, job_rate = get_effective_rate(prop, mowing_svc)
            # If rate is 0, check RecurringJob service_snapshot for a saved price
            if job_rate == 0 and rj and rj.service_snapshot:
                for snap in rj.service_snapshot:
                    snap_price = snap.get("unit_price")
                    if snap_price and Decimal(str(snap_price)) > 0:
                        job_rate = Decimal(str(snap_price))
                        job_unit = snap.get("unit", "visit")
                        break

        if schedule_mode == "season":
            # Generate recurring dates from start to season end
            interval = {"weekly": 7, "10day": 10, "biweekly": 14, "monthly": 30}.get(freq, 7)

            # Step 1: Delete ALL "scheduled" jobs for this property through the season.
            # Includes jobs BEFORE the start date (stale scheduled jobs that should
            # have been completed but weren't — e.g. jobs 1-4 when job 5 is completed).
            year_begin = date(schedule_date.year, 1, 1)
            all_scheduled = Job.objects.filter(
                property_id=prop.id,
                scheduled_date__gte=year_begin,
                scheduled_date__lte=season_end,
                status="scheduled",
            )
            sched_count = all_scheduled.count()
            logger.warning(
                "MOWING BULK SCHEDULE: prop_id=%s, prop=%s, delete_range=%s to %s, "
                "found %d scheduled jobs to delete, freq=%s, interval=%d",
                prop.id, prop.address, year_begin, season_end, sched_count, freq, interval
            )
            if sched_count > 0:
                deleted += sched_count
                sched_ids = list(all_scheduled.values_list("id", flat=True))
                JobServiceItem.objects.filter(job_id__in=sched_ids).delete()
                del_count, _ = Job.objects.filter(id__in=sched_ids).delete()
                logger.warning("MOWING BULK SCHEDULE: actually deleted %d jobs", del_count)

            # Step 2: Find ALL completed/in_progress/skipped jobs this year so we don't
            # create new jobs on those dates, and pick up scheduling after the last one.
            done_dates = list(
                Job.objects.filter(
                    property_id=prop.id,
                    scheduled_date__gte=year_begin,
                    scheduled_date__lte=season_end,
                    status__in=["completed", "in_progress", "skipped"],
                ).values_list("scheduled_date", flat=True)
            )
            existing_done_dates = set(done_dates)
            last_done_date = max(done_dates) if done_dates else None

            # Step 3: Determine where to start scheduling new jobs
            # If there are completed jobs, start the next job one interval after
            # the LAST completed job. This keeps the schedule flowing from actual work done.
            if last_done_date and last_done_date >= schedule_date:
                next_start = last_done_date + timedelta(days=interval)
            else:
                next_start = schedule_date

            # Step 4: Generate new scheduled jobs from next_start to season_end
            current_date = next_start
            while current_date <= season_end:
                # Double-check: skip if a completed/skipped job already exists on this date
                if current_date in existing_done_dates:
                    current_date += timedelta(days=interval)
                    continue
                # Wave 6: link back to the RecurringJob so calendar_job_reschedule
                # can shift RecurringJob.start_date when user selects "apply to all future".
                # rj may be None for legacy flows — the FK is nullable.
                job = Job.objects.create(
                    property=prop,
                    scheduled_date=current_date,
                    status="scheduled",
                    notes=f"[Mowing] {prop.customer.name}",
                    assigned_crew=rj.assigned_crew if rj else None,
                    assigned_to=rj.assigned_to if rj else None,
                    recurring_job=rj,
                )
                if mowing_svc:
                    JobServiceItem.objects.create(
                        job=job,
                        service=mowing_svc,
                        description="Mowing",
                        quantity=1,
                        unit=job_unit,
                        unit_price=job_rate,
                    )
                created += 1
                current_date += timedelta(days=interval)
        else:
            # Single job
            # Wave 6: link to RecurringJob (same rationale as the season branch above).
            job = Job.objects.create(
                property=prop,
                scheduled_date=schedule_date,
                status="scheduled",
                notes=f"[Mowing] {prop.customer.name}",
                assigned_crew=rj.assigned_crew if rj else None,
                assigned_to=rj.assigned_to if rj else None,
                recurring_job=rj,
            )
            if mowing_svc:
                JobServiceItem.objects.create(
                    job=job,
                    service=mowing_svc,
                    description=clean_service_label(service=mowing_svc),
                    quantity=1,
                    unit=job_unit,
                    unit_price=job_rate,
                )
            created += 1

    if schedule_mode == "season":
        del_msg = f" Deleted {deleted} old scheduled jobs first." if deleted else " No old jobs found to delete."
        messages.success(request, f"Scheduled {created} new mowing jobs through {season_end.strftime('%b %d')}.{del_msg}")
    else:
        messages.success(request, f"Scheduled {created} mowing job{'' if created == 1 else 's'} for {schedule_date.strftime('%b %d')}.")
    return redirect("mowing_hub")

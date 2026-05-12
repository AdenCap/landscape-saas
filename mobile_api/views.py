import json
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Case, Count, DecimalField, F, IntegerField, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from billing.models import Estimate, EstimateImage, EstimateLineItem, Invoice, InvoiceLineItem
from billing.services import invoice_card_payment_default
from billing.views import _approve_and_deliver_invoice, _log_invoice_audit, _sync_invoice_payment_from_line_items
from customers.models import Customer, Property
from financials.models import Receipt
from jobs.models import Crew, Job, JobCompletionPhoto, JobIssue, JobNote, JobPhoto, JobServiceItem, PropertyNote
from pricing.models import ServiceTemplate
from accounts.models import EmployeePayment, User
from service_agreements.models import AgreementVisit, ServiceAgreement
from time_tracking.models import EmployeeSchedule, TimeEntry, TimeEntryLocationPing, TimeOffRequest

from . import auth as mobile_auth
from .auth import issue_access_token, session_from_refresh_token, session_from_request, user_by_email, user_by_identifier
from .models import MobileDeviceSession

UNASSIGNED_CALENDAR_COLOR = "#94a3b8"
STATUS_CALENDAR_COLORS = {
    "scheduled": "#3b82f6",
    "in_progress": "#f59e0b",
    "completed": "#22c55e",
    "skipped": "#6b7280",
    "cancelled": "#6b7280",
}


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return request.POST


def _scalar(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _user_payload(user):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "role": user.role,
        "business_id": user.business_id,
    }


def _business_payload(business):
    return {
        "id": business.id,
        "name": business.name,
        "timezone": getattr(business, "timezone", "America/New_York"),
        "client_card_payments_enabled": bool(getattr(business, "client_card_payments_enabled", False)),
        "default_invoice_card_payments_enabled": bool(getattr(business, "default_invoice_card_payments_enabled", True)),
        "client_saved_cards_enabled": bool(getattr(business, "client_saved_cards_enabled", False)),
    }


def _parse_date(value):
    value = _scalar(value)
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_decimal(value):
    value = _scalar(value)
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_bool(value, default=False):
    value = _scalar(value)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _uploaded_image_or_error(request):
    image = request.FILES.get("photo") or request.FILES.get("image") or request.FILES.get("file")
    if not image:
        return None, JsonResponse({"error": "Photo is required."}, status=400)

    allowed_image_types = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    if image.content_type not in allowed_image_types:
        return None, JsonResponse({"error": "Invalid file type."}, status=400)
    if image.size > 10 * 1024 * 1024:
        return None, JsonResponse({"error": "Photo must be 10 MB or smaller."}, status=400)
    return image, None


def _parse_time_value(value):
    if value in (None, ""):
        return None
    try:
        hour, minute = str(value).split(":")[:2]
        return timezone.datetime(2000, 1, 1, int(hour), int(minute)).time()
    except (TypeError, ValueError):
        return "invalid"


def _time_entry_payload(entry):
    if not entry:
        return None
    return {
        "id": entry.id,
        "clock_in": entry.clock_in.isoformat(),
        "clock_out": entry.clock_out.isoformat() if entry.clock_out else None,
        "duration_minutes": entry.duration_minutes,
        "status": entry.status,
        "clock_in_latitude": str(entry.clock_in_latitude) if entry.clock_in_latitude is not None else None,
        "clock_in_longitude": str(entry.clock_in_longitude) if entry.clock_in_longitude is not None else None,
        "clock_out_latitude": str(entry.clock_out_latitude) if entry.clock_out_latitude is not None else None,
        "clock_out_longitude": str(entry.clock_out_longitude) if entry.clock_out_longitude is not None else None,
    }


def _active_time_entry(user):
    return TimeEntry.objects.filter(user=user, clock_out__isnull=True).order_by("-clock_in").first()


def _time_clock_payload(user):
    active_entry = _active_time_entry(user)
    current_timezone = timezone.get_current_timezone()
    today = timezone.localdate()
    day_start = timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.min.time()),
        current_timezone,
    )
    day_end = timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.max.time()),
        current_timezone,
    )
    today_filter = Q(clock_in__lte=day_end) & (Q(clock_out__isnull=True) | Q(clock_out__gte=day_start))
    if active_entry:
        today_filter |= Q(id=active_entry.id)
    today_entries = TimeEntry.objects.filter(user=user).filter(today_filter).order_by("clock_in")
    now = timezone.now()
    today_minutes = 0
    for entry in today_entries:
        if entry.clock_out:
            today_minutes += entry.duration_minutes or 0
        else:
            today_minutes += max(int((now - entry.clock_in).total_seconds() / 60), 0)
    return {
        "is_clocked_in": active_entry is not None,
        "active_entry": _time_entry_payload(active_entry),
        "today_minutes": today_minutes,
        "today_display": f"{today_minutes // 60}h {today_minutes % 60}m",
        "server_time": now.isoformat(),
    }


def _location_ping_payload(ping):
    return {
        "id": ping.id,
        "latitude": str(ping.latitude),
        "longitude": str(ping.longitude),
        "accuracy_meters": str(ping.accuracy_meters) if ping.accuracy_meters is not None else None,
        "recorded_at": ping.recorded_at.isoformat(),
    }


def health(request):
    return JsonResponse({
        "ok": True,
        "service": "fieldlgx-mobile-api",
        "version": 1,
    })


@csrf_exempt
@require_POST
def login(request):
    data = _json_body(request)
    identifier = (data.get("email") or data.get("username") or "").strip()
    password = data.get("password") or ""
    user = user_by_identifier(identifier)
    if not user or not user.check_password(password) or not user.business_id:
        return JsonResponse({"error": "Invalid email or password."}, status=400)
    session, refresh_token = MobileDeviceSession.issue(
        user=user,
        device_name=data.get("device_name") or "",
        platform=data.get("platform") or "ios",
    )
    return JsonResponse({
        "access_token": issue_access_token(session),
        "refresh_token": refresh_token,
        "user": _user_payload(user),
    })


@csrf_exempt
@require_POST
def refresh(request):
    data = _json_body(request)
    session = session_from_refresh_token(data.get("refresh_token"))
    if not session:
        return JsonResponse({"error": "Invalid refresh token."}, status=401)
    return JsonResponse({
        "access_token": issue_access_token(session),
        "user": _user_payload(session.user),
    })


@csrf_exempt
@require_POST
def logout(request):
    data = _json_body(request)
    session = session_from_refresh_token(data.get("refresh_token"))
    if session:
        session.revoke()
    return JsonResponse({"ok": True})


def _login_existing_social_user(request, verifier):
    data = _json_body(request)
    identity_token = data.get("identity_token") or ""
    try:
        verified = verifier(identity_token)
    except Exception:
        return JsonResponse({"error": "Could not verify identity token."}, status=400)
    user = user_by_email(verified.get("email"))
    if not user or not user.business_id:
        return JsonResponse({"error": "No FIELDLGX account is linked to this email."}, status=404)
    session, refresh_token = MobileDeviceSession.issue(
        user=user,
        device_name=data.get("device_name") or "",
        platform="ios",
    )
    return JsonResponse({
        "access_token": issue_access_token(session),
        "refresh_token": refresh_token,
        "user": _user_payload(user),
    })


@csrf_exempt
@require_POST
def apple_login(request):
    return _login_existing_social_user(request, mobile_auth.verify_apple_identity_token)


@csrf_exempt
@require_POST
def google_login(request):
    return _login_existing_social_user(request, mobile_auth.verify_google_identity_token)


def bootstrap(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    modules = ["dashboard", "jobs", "calendar", "clients", "billing", "time", "sync"]
    if session.user.role in {"owner", "manager"}:
        modules.extend(["employees", "financials", "settings", "fertilization", "agreements"])
    return JsonResponse({
        "user": _user_payload(session.user),
        "business": _business_payload(session.business),
        "modules": modules,
        "sync": {
            "cursor": None,
            "server_time": session.last_seen_at.isoformat(),
        },
    })


def command(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Command is only available to owners and managers."}, status=403)

    target_date = _parse_date(request.GET.get("date"))
    if not target_date:
        return JsonResponse({"error": "Invalid date."}, status=400)

    business = session.business
    business_jobs = Job.objects.filter(property__customer__business=business)
    today_jobs = business_jobs.filter(
        Q(scheduled_date=target_date) |
        Q(scheduled_date__lte=target_date, scheduled_end_date__gte=target_date)
    ).exclude(status__in=["skipped"])
    todays_jobs_qs = business_jobs.filter(scheduled_date=target_date)
    open_jobs = today_jobs.exclude(status__in=["completed", "skipped"])
    active_routes = todays_jobs_qs.filter(assigned_crew__isnull=False).values("assigned_crew_id").distinct().count()
    unassigned_jobs = todays_jobs_qs.filter(
        status="scheduled",
        assigned_to__isnull=True,
        assigned_crew__isnull=True,
    )
    needs_scheduled = business_jobs.filter(
        scheduled_date__isnull=True,
        status__in=["scheduled", "in_progress"],
    )
    ready_to_bill_qs = business_jobs.filter(
        status="completed",
        service_items__billed_invoice__isnull=True,
    ).distinct()
    ready_to_bill_total = (
        JobServiceItem.objects.filter(
            job__property__customer__business=business,
            job__status="completed",
            billed_invoice__isnull=True,
        ).aggregate(
            total=Coalesce(
                Sum(F("quantity") * F("unit_price")),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    )
    scheduled_value = (
        JobServiceItem.objects.filter(
            job__property__customer__business=business,
            job__scheduled_date=target_date,
        ).aggregate(
            total=Coalesce(
                Sum(F("quantity") * F("unit_price")),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    )
    invoices = Invoice.objects.filter(business=business)
    outstanding_total = invoices.filter(status__in=["sent", "draft"]).aggregate(
        total=Sum("total"),
    )["total"] or Decimal("0")
    open_estimates = Estimate.objects.filter(business=business, status__in=["draft", "sent"]).count()

    attention = []
    if needs_scheduled.exists():
        attention.append({
            "kind": "schedule",
            "title": "Needs scheduled",
            "detail": f"{needs_scheduled.count()} job{'s' if needs_scheduled.count() != 1 else ''} waiting for a date.",
            "count": needs_scheduled.count(),
        })
    if unassigned_jobs.exists():
        attention.append({
            "kind": "crew",
            "title": "Needs crew",
            "detail": f"{unassigned_jobs.count()} job{'s' if unassigned_jobs.count() != 1 else ''} not assigned.",
            "count": unassigned_jobs.count(),
        })
    if ready_to_bill_qs.exists():
        attention.append({
            "kind": "billing",
            "title": "Ready to bill",
            "detail": f"{ready_to_bill_qs.count()} completed visit{'s' if ready_to_bill_qs.count() != 1 else ''} ready for invoice review.",
            "count": ready_to_bill_qs.count(),
        })
    if not attention:
        attention.append({
            "kind": "stable",
            "title": "Day looks stable",
            "detail": "No urgent scheduling, crew, or billing issues.",
            "count": 0,
        })

    next_jobs = list(open_jobs.select_related(
        "property",
        "property__customer",
        "assigned_to",
        "assigned_crew",
    ).prefetch_related("service_items__service").annotate(
        site_photo_count=Count("site_photos"),
    ).order_by("route_order", "scheduled_time", "id")[:5])

    return JsonResponse({
        "date": target_date.isoformat(),
        "summary": {
            "today_jobs": today_jobs.count(),
            "active_routes": active_routes,
            "unassigned_jobs": unassigned_jobs.count(),
            "needs_scheduled": needs_scheduled.count(),
            "ready_to_bill": ready_to_bill_qs.count(),
            "ready_to_bill_total": f"{ready_to_bill_total:.2f}",
            "scheduled_value": f"{scheduled_value:.2f}",
            "outstanding_total": f"{outstanding_total:.2f}",
            "open_estimates": open_estimates,
            "customers": Customer.objects.filter(business=business).count(),
        },
        "attention": attention[:4],
        "next_jobs": [_job_payload(job, target_date) for job in next_jobs],
        "server_time": timezone.now().isoformat(),
    })


def _service_filter_payload(business):
    filters = [{"key": "all", "label": "All"}]
    for service in ServiceTemplate.objects.filter(business=business).order_by("name"):
        filters.append({
            "key": service.name.lower().replace(" ", "-"),
            "label": service.name,
        })
    defaults = [
        ("mowing", "Mowing"),
        ("fertilization", "Fertilization"),
        ("landscaping", "Landscaping"),
        ("other", "Other"),
    ]
    existing = {item["key"] for item in filters}
    for key, label in defaults:
        if key not in existing:
            filters.append({"key": key, "label": label})
    return filters


def _apply_service_filter(jobs, service_key):
    service_key = (service_key or "all").strip().lower()
    if service_key in {"", "all"}:
        return jobs
    label = service_key.replace("-", " ")
    return jobs.filter(
        Q(service_items__service__name__iexact=label) |
        Q(service_items__description__iexact=label)
    ).distinct()


def work(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Work is only available to owners and managers."}, status=403)

    target_date = _parse_date(request.GET.get("date"))
    if not target_date:
        return JsonResponse({"error": "Invalid date."}, status=400)

    base_jobs = _job_queryset_for_mobile(session)
    base_jobs = _apply_service_filter(base_jobs, request.GET.get("service"))
    upcoming_end = target_date + timedelta(days=14)
    recent_start = target_date - timedelta(days=7)

    upcoming = base_jobs.filter(
        scheduled_date__gte=target_date,
        scheduled_date__lte=upcoming_end,
        status__in=["scheduled", "in_progress"],
    ).order_by("scheduled_date", "scheduled_time", "route_order", "id")
    needs_scheduled = base_jobs.filter(
        scheduled_date__isnull=True,
        status__in=["scheduled", "in_progress"],
    ).order_by("schedule_by_date", "id")
    finished = base_jobs.filter(
        status="completed",
    ).filter(
        Q(scheduled_date__gte=recent_start) | Q(completed_at__date__gte=recent_start)
    ).order_by("-completed_at", "-scheduled_date", "id")
    needs_billing = finished.filter(
        invoice__isnull=True,
        invoices__isnull=True,
    ).distinct()

    return JsonResponse({
        "date": target_date.isoformat(),
        "summary": {
            "upcoming": upcoming.count(),
            "needs_scheduled": needs_scheduled.count(),
            "finished": finished.count(),
            "needs_billing": needs_billing.count(),
        },
        "service_filters": _service_filter_payload(session.business),
        "sections": {
            "upcoming": [_job_payload(job, job.scheduled_date or target_date) for job in upcoming[:20]],
            "needs_scheduled": [_job_payload(job, target_date) for job in needs_scheduled[:20]],
            "finished": [_job_payload(job, job.scheduled_date or target_date) for job in finished[:20]],
            "needs_billing": [_job_payload(job, job.scheduled_date or target_date) for job in needs_billing[:20]],
        },
        "server_time": timezone.now().isoformat(),
    })


def _property_payload(property_obj):
    return {
        "id": property_obj.id,
        "address": property_obj.address,
        "latitude": str(property_obj.latitude) if property_obj.latitude is not None else None,
        "longitude": str(property_obj.longitude) if property_obj.longitude is not None else None,
        "notes": property_obj.notes,
        "gate_code": property_obj.gate_code,
        "has_dog": property_obj.has_dog,
        "yard_sqft": property_obj.yard_sqft,
    }


def _client_payload(customer, include_notes=True):
    properties = list(customer.properties.all())
    primary_property = properties[0] if properties else None
    job_count = Job.objects.filter(property__customer=customer).count()
    invoice_count = Invoice.objects.filter(customer=customer).count()
    estimate_count = Estimate.objects.filter(customer=customer).count()
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "primary_address": primary_property.address if primary_property else customer.full_address,
        "mailing_address": customer.full_address,
        "notes": customer.notes if include_notes else "",
        "billing": {
            "invoice_frequency": customer.invoice_frequency,
            "monthly_invoice_send_day": customer.monthly_invoice_send_day,
            "invoice_due_days": customer.invoice_due_days,
            "has_card_on_file": bool(customer.stripe_customer_id and customer.stripe_payment_method_id) or bool(customer.card_last4),
            "card_last4": customer.card_last4,
            "card_brand": customer.card_brand,
            "auto_charge": customer.auto_charge,
            "auto_charge_completed_jobs": customer.auto_charge_completed_jobs,
            "auto_charge_monthly_invoices": customer.auto_charge_monthly_invoices,
        },
        "stats": {
            "jobs": job_count,
            "invoices": invoice_count,
            "estimates": estimate_count,
        },
        "properties": [_property_payload(prop) for prop in properties],
        "updated_at": customer.updated_at.isoformat(),
    }


def _client_or_response(request, client_id):
    session = session_from_request(request)
    if not session:
        return None, None, JsonResponse({"error": "Authentication required."}, status=401)
    try:
        customer = Customer.objects.prefetch_related("properties").get(id=client_id, business=session.business)
    except Customer.DoesNotExist:
        return None, session, JsonResponse({"error": "Client not found."}, status=404)
    return customer, session, None


def _create_client_from_payload(data, business):
    name = (data.get("name") or "").strip()
    if not name:
        return None, JsonResponse({"error": "Client name is required."}, status=400)
    customer = Customer.objects.create(
        business=business,
        name=name,
        email=(data.get("email") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        notes=(data.get("notes") or "").strip(),
    )
    address = (data.get("address") or "").strip()
    if address:
        Property.objects.create(customer=customer, address=address)
    return Customer.objects.prefetch_related("properties").get(id=customer.id), None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def clients(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Clients are only available to owners and managers."}, status=403)

    if request.method == "POST":
        data = _json_body(request)
        customer, error = _create_client_from_payload(data, session.business)
        if error:
            return error
        return JsonResponse({"client": _client_payload(customer)}, status=201)

    query = (request.GET.get("q") or "").strip()
    customers = Customer.objects.filter(business=session.business).prefetch_related("properties").order_by("name")
    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(properties__address__icontains=query)
        ).distinct()
    customer_list = list(customers[:50])
    return JsonResponse({
        "summary": {
            "total": Customer.objects.filter(business=session.business).count(),
            "shown": len(customer_list),
        },
        "clients": [_client_payload(customer, include_notes=False) for customer in customer_list],
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def client_detail(request, client_id):
    customer, session, error = _client_or_response(request, client_id)
    if error:
        return error
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Clients are only available to owners and managers."}, status=403)

    if request.method == "PATCH":
        data = _json_body(request)
        update_fields = []
        for field in ("name", "email", "phone", "notes", "invoice_frequency"):
            if field in data:
                setattr(customer, field, (data.get(field) or "").strip())
                update_fields.append(field)
        if update_fields:
            customer.save(update_fields=update_fields + ["updated_at"])
            customer = Customer.objects.prefetch_related("properties").get(id=customer.id)

    return JsonResponse({
        "client": _client_payload(customer),
        "server_time": timezone.now().isoformat(),
    })


def _calendar_range(target_date, view):
    if view == "week":
        start = target_date - timedelta(days=target_date.weekday())
        return start, start + timedelta(days=6)
    if view == "month":
        return target_date.replace(day=1), target_date.replace(day=monthrange(target_date.year, target_date.month)[1])
    return target_date, target_date


def calendar(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Calendar is only available to owners and managers."}, status=403)

    target_date = _parse_date(request.GET.get("date"))
    if not target_date:
        return JsonResponse({"error": "Invalid date."}, status=400)
    view = (request.GET.get("view") or "week").strip().lower()
    if view not in {"day", "week", "month"}:
        view = "week"
    start, end = _calendar_range(target_date, view)

    jobs = _job_queryset_for_mobile(session).filter(
        Q(scheduled_date__gte=start, scheduled_date__lte=end) |
        Q(scheduled_date__lte=end, scheduled_end_date__gte=start)
    ).exclude(status="skipped").order_by("scheduled_date", "scheduled_time", "route_order", "id")
    job_list = list(jobs[:200])
    return JsonResponse({
        "view": view,
        "date": target_date.isoformat(),
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "summary": {
            "total": len(job_list),
            "unassigned": sum(1 for job in job_list if not job.assigned_to_id and not job.assigned_crew_id),
            "completed": sum(1 for job in job_list if job.status == "completed"),
        },
        "jobs": [_job_payload(job, job.scheduled_date or start) for job in job_list],
        "server_time": timezone.now().isoformat(),
    })


def _apply_job_write_fields(job, data, business):
    update_fields = []
    if "scheduled_date" in data:
        value = data.get("scheduled_date")
        parsed = _parse_date(value) if value else None
        if value and not parsed:
            return JsonResponse({"error": "Invalid scheduled date."}, status=400)
        job.scheduled_date = parsed
        update_fields.append("scheduled_date")
    if "scheduled_end_date" in data:
        value = data.get("scheduled_end_date")
        parsed = _parse_date(value) if value else None
        if value and not parsed:
            return JsonResponse({"error": "Invalid scheduled end date."}, status=400)
        job.scheduled_end_date = parsed
        update_fields.append("scheduled_end_date")
    if "scheduled_time" in data:
        parsed = _parse_time_value(data.get("scheduled_time"))
        if parsed == "invalid":
            return JsonResponse({"error": "Invalid scheduled time."}, status=400)
        job.scheduled_time = parsed
        update_fields.append("scheduled_time")
    if "scheduled_end_time" in data:
        parsed = _parse_time_value(data.get("scheduled_end_time"))
        if parsed == "invalid":
            return JsonResponse({"error": "Invalid scheduled end time."}, status=400)
        job.scheduled_end_time = parsed
        update_fields.append("scheduled_end_time")
    if "notes" in data:
        job.notes = (data.get("notes") or "").strip()
        update_fields.append("notes")
    if "status" in data:
        status = (data.get("status") or "").strip()
        if status not in {choice[0] for choice in Job.STATUS_CHOICES}:
            return JsonResponse({"error": "Invalid job status."}, status=400)
        job.status = status
        update_fields.append("status")
    if "color" in data:
        color = (data.get("color") or "").strip()
        if color and (len(color) != 7 or not color.startswith("#")):
            return JsonResponse({"error": "Invalid job color."}, status=400)
        job.color = color
        update_fields.append("color")
    if "assigned_crew_id" in data:
        crew_id = data.get("assigned_crew_id")
        if crew_id in (None, ""):
            job.assigned_crew = None
        else:
            try:
                job.assigned_crew = Crew.objects.get(id=crew_id, business=business)
            except (Crew.DoesNotExist, ValueError, TypeError):
                return JsonResponse({"error": "Crew not found."}, status=404)
        update_fields.append("assigned_crew")
    if update_fields:
        job.save(update_fields=update_fields)
    return None


def _replace_job_service_items(job, items, business):
    if items is None:
        return None
    if not isinstance(items, list):
        return JsonResponse({"error": "Service items must be a list."}, status=400)
    job.service_items.all().delete()
    for item in items:
        try:
            service = ServiceTemplate.objects.get(id=item.get("service_id"), business=business)
        except (ServiceTemplate.DoesNotExist, ValueError, TypeError, AttributeError):
            return JsonResponse({"error": "Service not found."}, status=404)
        quantity = _parse_decimal(item.get("quantity")) or Decimal("1.00")
        unit_price = _parse_decimal(item.get("unit_price"))
        if unit_price is None:
            unit_price = service.default_rate
        JobServiceItem.objects.create(
            job=job,
            service=service,
            description=(item.get("description") or "").strip(),
            detail_description=(item.get("detail_description") or "").strip(),
            quantity=quantity,
            unit=(item.get("unit") or service.default_unit or "visit").strip(),
            unit_price=unit_price,
        )
    return None


def job_options(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Job options are only available to owners and managers."}, status=403)

    properties = Property.objects.filter(customer__business=session.business).select_related("customer").order_by("customer__name", "address")[:200]
    services = ServiceTemplate.objects.filter(business=session.business, active=True).order_by("name")
    crews = Crew.objects.filter(business=session.business).order_by("name")
    return JsonResponse({
        "properties": [
            {
                "id": prop.id,
                "customer_id": prop.customer_id,
                "customer_name": prop.customer.name,
                "address": prop.address,
            }
            for prop in properties
        ],
        "services": [
            {
                "id": service.id,
                "name": service.name,
                "unit": service.default_unit,
                "unit_price": f"{service.default_rate:.2f}",
            }
            for service in services
        ],
        "crews": [
            {
                "id": crew.id,
                "name": crew.name,
            }
            for crew in crews
        ],
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_POST
def jobs(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Jobs can only be created by owners and managers."}, status=403)

    data = _json_body(request)
    try:
        property_obj = Property.objects.get(id=data.get("property_id"), customer__business=session.business)
    except (Property.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"error": "Property not found."}, status=404)

    job = Job.objects.create(property=property_obj, status="scheduled")
    error = _apply_job_write_fields(job, data, session.business)
    if error:
        job.delete()
        return error
    error = _replace_job_service_items(job, data.get("service_items"), session.business)
    if error:
        job.delete()
        return error

    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse({
        "job": _job_payload(job, job.scheduled_date or date.today()),
        "server_time": timezone.now().isoformat(),
    }, status=201)


def _invoice_payload(invoice):
    return {
        "id": invoice.id,
        "number": f"#{invoice.id}",
        "customer": {
            "id": invoice.customer_id,
            "name": invoice.customer.name,
        },
        "status": invoice.status,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "total": f"{invoice.total:.2f}",
        "enable_card_payment": invoice.enable_card_payment,
        "is_monthly": bool(invoice.job_id is None and invoice.period_start),
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
    }


def _monthly_invoice_send_on(invoice):
    send_day = (
        getattr(invoice.customer, "monthly_invoice_send_day", None)
        or getattr(invoice.business, "default_monthly_invoice_send_day", None)
    )
    if invoice.status != "draft" or not invoice.period_start or not send_day:
        return None
    day = min(send_day, 28)
    try:
        return date(invoice.period_start.year, invoice.period_start.month, day)
    except (TypeError, ValueError):
        return None


def _monthly_invoice_payload(invoice):
    payload = _invoice_payload(invoice)
    send_on = _monthly_invoice_send_on(invoice)
    payload["send_on"] = send_on.isoformat() if send_on else None
    return payload


def _estimate_payload(estimate):
    total = estimate.accepted_total if estimate.accepted_total is not None else estimate.total()
    return {
        "id": estimate.id,
        "title": estimate.title,
        "customer": {
            "id": estimate.customer_id,
            "name": estimate.customer.name,
        },
        "status": estimate.status,
        "valid_until": estimate.valid_until.isoformat() if estimate.valid_until else None,
        "total": f"{total:.2f}",
        "deposit_required": estimate.deposit_required,
        "photo_count": estimate.images.count() if hasattr(estimate, "images") else 0,
    }


def _receipt_payload(receipt):
    return {
        "id": receipt.id,
        "vendor": receipt.vendor,
        "description": receipt.description,
        "category": receipt.category,
        "amount": f"{(receipt.amount or Decimal('0')):.2f}",
        "receipt_date": receipt.receipt_date.isoformat(),
        "job_id": receipt.job_id,
        "file_url": receipt.file.url if receipt.file else "",
        "created_at": receipt.created_at.isoformat(),
    }


def _invoice_line_item_payload(item):
    return {
        "id": item.id,
        "description": item.description,
        "detail_description": item.detail_description,
        "quantity": str(item.quantity),
        "unit": "",
        "unit_price": f"{item.unit_price:.2f}",
        "line_total": f"{item.line_total:.2f}",
        "is_paid": item.is_paid,
        "is_optional": False,
        "is_discount": item.is_discount,
    }


def _estimate_line_item_payload(item):
    return {
        "id": item.id,
        "description": item.description,
        "detail_description": item.detail_description,
        "quantity": str(item.quantity),
        "unit": item.unit,
        "unit_price": f"{item.unit_price:.2f}",
        "line_total": f"{item.line_total:.2f}",
        "is_paid": False,
        "is_optional": item.is_addon,
        "is_discount": False,
    }


def _money_customer_or_error(session, customer_id):
    try:
        return Customer.objects.get(id=customer_id, business=session.business), None
    except (Customer.DoesNotExist, ValueError, TypeError):
        return None, JsonResponse({"error": "Customer not found."}, status=404)


def _create_invoice_line_items(invoice, items):
    if not isinstance(items, list) or not items:
        return JsonResponse({"error": "At least one line item is required."}, status=400)
    for item in items:
        description = (item.get("description") or "").strip()
        if not description:
            return JsonResponse({"error": "Line item description is required."}, status=400)
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=description,
            detail_description=(item.get("detail_description") or "").strip(),
            quantity=int(_parse_decimal(item.get("quantity")) or Decimal("1")),
            unit_price=_parse_decimal(item.get("unit_price")) or Decimal("0"),
            material_cost=_parse_decimal(item.get("material_cost")) or Decimal("0"),
            labor_cost=_parse_decimal(item.get("labor_cost")) or Decimal("0"),
        )
    invoice.refresh_from_db()
    return None


def _create_estimate_line_items(estimate, items):
    if not isinstance(items, list) or not items:
        return JsonResponse({"error": "At least one line item is required."}, status=400)
    for index, item in enumerate(items):
        description = (item.get("description") or "").strip()
        if not description:
            return JsonResponse({"error": "Line item description is required."}, status=400)
        EstimateLineItem.objects.create(
            estimate=estimate,
            description=description,
            detail_description=(item.get("detail_description") or "").strip(),
            quantity=_parse_decimal(item.get("quantity")) or Decimal("1"),
            unit=(item.get("unit") or "ea").strip(),
            unit_price=_parse_decimal(item.get("unit_price")) or Decimal("0"),
            material_cost=_parse_decimal(item.get("material_cost")) or Decimal("0"),
            labor_cost=_parse_decimal(item.get("labor_cost")) or Decimal("0"),
            is_addon=bool(item.get("is_optional")),
            order=index,
        )
    return None


def money(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Money is only available to owners and managers."}, status=403)

    today = timezone.localdate()
    invoices = Invoice.objects.filter(business=session.business).select_related("customer")
    estimates = Estimate.objects.filter(business=session.business).select_related("customer")
    building_invoice_q = Q(status="draft", job__isnull=True, period_start__isnull=False)
    attention_invoices = invoices.exclude(building_invoice_q)
    building_invoices = invoices.filter(building_invoice_q)
    outstanding = attention_invoices.filter(status__in=["sent", "draft"]).aggregate(total=Sum("total"))["total"] or Decimal("0")
    overdue = invoices.filter(status="sent", due_date__lt=today).aggregate(total=Sum("total"))["total"] or Decimal("0")
    paid_month = invoices.filter(status="paid", paid_at__date__year=today.year, paid_at__date__month=today.month).aggregate(total=Sum("total"))["total"] or Decimal("0")
    building_total = building_invoices.aggregate(total=Sum("total"))["total"] or Decimal("0")

    return JsonResponse({
        "summary": {
            "outstanding": f"{outstanding:.2f}",
            "overdue": f"{overdue:.2f}",
            "drafts": attention_invoices.filter(status="draft").count(),
            "paid_month": f"{paid_month:.2f}",
            "open_estimates": estimates.filter(status__in=["draft", "sent"]).count(),
            "building_invoices": building_invoices.count(),
            "building_total": f"{building_total:.2f}",
        },
        "invoices": [_invoice_payload(invoice) for invoice in attention_invoices.order_by("-issue_date", "-id")[:30]],
        "estimates": [_estimate_payload(estimate) for estimate in estimates.order_by("-updated_at", "-id")[:30]],
        "server_time": timezone.now().isoformat(),
    })


def financials(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Financials are only available to owners and managers."}, status=403)

    today = timezone.localdate()
    month_start = today.replace(day=1)
    month_end = today.replace(day=monthrange(today.year, today.month)[1])
    invoices = Invoice.objects.filter(business=session.business).select_related("customer")
    receipts = Receipt.objects.filter(business=session.business)
    payments = EmployeePayment.objects.filter(business=session.business)
    month_revenue = invoices.filter(status="paid", paid_at__date__gte=month_start, paid_at__date__lte=month_end).aggregate(total=Sum("total"))["total"] or Decimal("0")
    open_invoice_total = invoices.filter(status__in=["draft", "sent"]).aggregate(total=Sum("total"))["total"] or Decimal("0")
    expense_total = receipts.filter(receipt_date__gte=month_start, receipt_date__lte=month_end).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    payroll_total = payments.filter(paid_date__gte=month_start, paid_date__lte=month_end).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    recent_receipts = receipts.select_related("job").order_by("-receipt_date", "-created_at")[:12]
    return JsonResponse({
        "summary": {
            "month_revenue": f"{month_revenue:.2f}",
            "open_invoice_total": f"{open_invoice_total:.2f}",
            "expense_total": f"{expense_total:.2f}",
            "payroll_total": f"{payroll_total:.2f}",
            "net_month": f"{(month_revenue - expense_total - payroll_total):.2f}",
        },
        "receipts": [_receipt_payload(receipt) for receipt in recent_receipts],
        "server_time": timezone.now().isoformat(),
    })


def team(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Team is only available to owners and managers."}, status=403)

    today = timezone.localdate()
    current_timezone = timezone.get_current_timezone()
    day_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()), current_timezone)
    day_end = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()), current_timezone)
    employees = User.objects.filter(business=session.business).order_by("first_name", "last_name", "username")
    today_entries = TimeEntry.objects.filter(
        user__business=session.business,
        clock_in__lte=day_end,
    ).filter(Q(clock_out__isnull=True) | Q(clock_out__gte=day_start)).select_related("user").order_by("-clock_in")
    active_entries = TimeEntry.objects.filter(
        user__business=session.business,
        clock_out__isnull=True,
    ).select_related("user").order_by("-clock_in")
    pending_time = TimeEntry.objects.filter(user__business=session.business, status="pending_approval").count()
    pending_time_off = TimeOffRequest.objects.filter(business=session.business, status="pending").count()
    schedules = EmployeeSchedule.objects.filter(user__business=session.business).select_related("user").order_by("user__first_name", "day_of_week")
    schedule_map = {}
    for slot in schedules:
        schedule_map.setdefault(slot.user_id, []).append({
            "day": slot.get_day_of_week_display(),
            "start": slot.start_time.strftime("%H:%M") if slot.start_time else "",
            "end": slot.end_time.strftime("%H:%M") if slot.end_time else "",
        })

    return JsonResponse({
        "summary": {
            "employees": employees.count(),
            "clocked_in": active_entries.count(),
            "pending_time": pending_time,
            "pending_time_off": pending_time_off,
        },
        "employees": [
            {
                "id": employee.id,
                "name": employee.get_full_name() or employee.username,
                "email": employee.email,
                "phone": employee.phone,
                "role": employee.role,
                "hourly_rate": f"{employee.hourly_rate:.2f}" if employee.hourly_rate is not None else "",
                "color": employee.color,
                "is_active": employee.is_active,
                "is_clocked_in": any(entry.user_id == employee.id for entry in active_entries),
                "schedule": schedule_map.get(employee.id, []),
            }
            for employee in employees
        ],
        "today_entries": [
            {
                **_time_entry_payload(entry),
                "employee": entry.user.get_full_name() or entry.user.username,
            }
            for entry in today_entries[:20]
        ],
        "server_time": timezone.now().isoformat(),
    })


def agreements(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Agreements are only available to owners and managers."}, status=403)

    agreements_qs = ServiceAgreement.objects.filter(business=session.business).select_related("customer").prefetch_related("line_items")
    visits = AgreementVisit.objects.filter(agreement__business=session.business)
    return JsonResponse({
        "summary": {
            "active": agreements_qs.filter(status="active").count(),
            "draft": agreements_qs.filter(status="draft").count(),
            "expired": agreements_qs.filter(status="expired").count(),
            "scheduled_visits": visits.filter(status="scheduled").count(),
        },
        "agreements": [
            {
                "id": agreement.id,
                "name": agreement.name,
                "customer": {"id": agreement.customer_id, "name": agreement.customer.name},
                "status": agreement.status,
                "agreement_type": agreement.get_agreement_type_display(),
                "billing_frequency": agreement.get_billing_frequency_display(),
                "start_date": agreement.start_date.isoformat() if agreement.start_date else None,
                "end_date": agreement.end_date.isoformat() if agreement.end_date else None,
                "price": f"{agreement.price:.2f}",
                "visits_included": agreement.visits_included,
                "visits_used": agreement.visits_used,
                "visits_remaining": agreement.visits_remaining,
                "auto_renew": agreement.auto_renew,
                "prepaid": agreement.prepaid,
                "line_items": [
                    {
                        "id": item.id,
                        "service_name": item.service_name,
                        "description": item.description,
                        "frequency": item.get_frequency_display(),
                        "quantity": str(item.quantity),
                        "unit": item.unit,
                        "unit_price": f"{item.unit_price:.2f}",
                        "line_total": f"{item.line_total:.2f}",
                        "progress": item.progress_display,
                    }
                    for item in agreement.line_items.all()
                ],
            }
            for agreement in agreements_qs.order_by("-start_date", "-id")[:50]
        ],
        "server_time": timezone.now().isoformat(),
    })


def settings(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Settings are only available to owners and managers."}, status=403)

    business = session.business
    return JsonResponse({
        "business": _business_payload(business),
        "contact": {
            "from_email": business.from_email,
            "contact_email": business.contact_email,
            "contact_phone": business.contact_phone,
            "website_url": business.website_url,
            "shop_address": business.shop_address,
            "logo_url": business.logo.url if business.logo else "",
        },
        "billing": {
            "default_invoice_automation_mode": business.default_invoice_automation_mode,
            "auto_invoice_send_behavior": business.auto_invoice_send_behavior,
            "default_monthly_invoice_send_day": business.default_monthly_invoice_send_day,
            "default_invoice_due_days": business.default_invoice_due_days,
            "default_estimate_valid_days": business.default_estimate_valid_days,
            "client_card_payments_enabled": business.client_card_payments_enabled,
            "default_invoice_card_payments_enabled": business.default_invoice_card_payments_enabled,
            "client_saved_cards_enabled": business.client_saved_cards_enabled,
            "stripe_connected": business.can_accept_stripe_payments(),
        },
        "notifications": {
            "job_scheduled": business.notify_job_scheduled,
            "crew_en_route": business.notify_crew_en_route,
            "job_completed": business.notify_job_completed,
            "completion_photos": business.notify_include_completion_photos,
            "invoice_reminders": business.invoice_reminder_enabled,
            "estimate_follow_up_days": business.estimate_follow_up_days,
            "google_review_requests": business.google_review_requests_enabled,
        },
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def monthly_invoices(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Monthly invoices are only available to owners and managers."}, status=403)

    monthly = Invoice.objects.filter(
        business=session.business,
        job__isnull=True,
        period_start__isnull=False,
    ).select_related("business", "customer").prefetch_related("line_items")

    year_param = (request.GET.get("year") or "").strip()
    data = _json_body(request) if request.method == "POST" else {}
    if request.method == "POST" and not year_param:
        year_param = str(data.get("year") or "").strip()
    year_int = int(year_param) if year_param.isdigit() else None
    if year_int:
        monthly = monthly.filter(period_start__year=year_int)

    if request.method == "POST":
        action = (data.get("action") or "").strip()
        if action not in {"send_selected", "send_all_ready"}:
            return JsonResponse({"error": "Unsupported monthly invoice action."}, status=400)
        if action == "send_all_ready":
            send_qs = monthly.filter(status="draft")
        else:
            invoice_ids = [pk for pk in data.get("invoice_ids", []) if str(pk).isdigit()]
            send_qs = monthly.filter(id__in=invoice_ids, status="draft")
        invoices_to_send = list(send_qs.order_by("period_start", "id"))
        if not invoices_to_send:
            return JsonResponse({"error": "No draft monthly invoices selected."}, status=400)

        sent_count = emailed_count = charged_count = failed_email_count = 0
        request.user = session.user
        for invoice in invoices_to_send:
            result = _approve_and_deliver_invoice(invoice, request=request, user=session.user, source="native_monthly_batch")
            if not result.get("sent"):
                continue
            sent_count += 1
            if result.get("email") == "sent":
                emailed_count += 1
            elif result.get("email") == "failed":
                failed_email_count += 1
            if result.get("charged"):
                charged_count += 1
        monthly = Invoice.objects.filter(
            business=session.business,
            job__isnull=True,
            period_start__isnull=False,
        ).select_related("business", "customer").prefetch_related("line_items")
        if year_int:
            monthly = monthly.filter(period_start__year=year_int)
        response = _monthly_invoice_queue_response(monthly)
        response["result"] = {
            "sent": sent_count,
            "emailed": emailed_count,
            "charged": charged_count,
            "email_failed": failed_email_count,
            "message": f"Sent {sent_count} monthly invoice{'' if sent_count == 1 else 's'}.",
        }
        return JsonResponse(response)

    return JsonResponse(_monthly_invoice_queue_response(monthly))


def _monthly_invoice_queue_response(monthly):
    monthly_for_stats = list(monthly.order_by("-period_start", "-id")[:100])
    draft_invoices = [invoice for invoice in monthly_for_stats if invoice.status == "draft"]
    sent_invoices = [invoice for invoice in monthly_for_stats if invoice.status == "sent"]
    paid_invoices = [invoice for invoice in monthly_for_stats if invoice.status == "paid"]
    return {
        "summary": {
            "draft_count": len(draft_invoices),
            "sent_count": len(sent_invoices),
            "paid_count": len(paid_invoices),
            "draft_total": f"{sum((invoice.total for invoice in draft_invoices), Decimal('0')):.2f}",
            "sent_total": f"{sum((invoice.total for invoice in sent_invoices), Decimal('0')):.2f}",
            "paid_total": f"{sum((invoice.total for invoice in paid_invoices), Decimal('0')):.2f}",
        },
        "invoices": [_monthly_invoice_payload(invoice) for invoice in monthly_for_stats],
        "server_time": timezone.now().isoformat(),
    }


@csrf_exempt
@require_http_methods(["POST"])
def invoices(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Invoices are only available to owners and managers."}, status=403)

    data = _json_body(request)
    customer, error = _money_customer_or_error(session, data.get("customer_id"))
    if error:
        return error
    invoice = Invoice.objects.create(
        business=session.business,
        customer=customer,
        status="draft",
        due_date=_parse_date(data.get("due_date")),
        enable_card_payment=_parse_bool(
            data.get("enable_card_payment"),
            default=invoice_card_payment_default(session.business),
        ),
    )
    error = _create_invoice_line_items(invoice, data.get("line_items"))
    if error:
        invoice.delete()
        return error
    invoice = Invoice.objects.select_related("customer").prefetch_related("line_items").get(id=invoice.id)
    return JsonResponse({
        "invoice": _invoice_payload(invoice),
        "summary": {
            "subtotal": f"{invoice.subtotal:.2f}",
            "tax": f"{invoice.tax:.2f}",
            "total": f"{invoice.total:.2f}",
            "paid_items": 0,
            "line_items": invoice.line_items.count(),
        },
        "line_items": [_invoice_line_item_payload(item) for item in invoice.line_items.all()],
        "server_time": timezone.now().isoformat(),
    }, status=201)


@require_http_methods(["GET"])
def invoice_detail(request, invoice_id):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Invoices are only available to owners and managers."}, status=403)

    try:
        invoice = Invoice.objects.select_related("customer").prefetch_related("line_items").get(
            id=invoice_id,
            business=session.business,
        )
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "Invoice not found."}, status=404)

    return JsonResponse({
        "invoice": _invoice_payload(invoice),
        "summary": {
            "subtotal": f"{invoice.subtotal:.2f}",
            "tax": f"{invoice.tax:.2f}",
            "total": f"{invoice.total:.2f}",
            "paid_items": invoice.line_items.filter(is_paid=True).count(),
            "line_items": invoice.line_items.count(),
        },
        "line_items": [_invoice_line_item_payload(item) for item in invoice.line_items.all()],
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def invoice_action(request, invoice_id):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Invoices are only available to owners and managers."}, status=403)
    try:
        invoice = Invoice.objects.select_related("customer", "business").prefetch_related("line_items").get(
            id=invoice_id,
            business=session.business,
        )
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "Invoice not found."}, status=404)

    action = (_json_body(request).get("action") or "").strip()
    if action == "send":
        request.user = session.user
        result = _approve_and_deliver_invoice(invoice, request=request, user=session.user, source="native_ios")
        invoice = Invoice.objects.select_related("customer").prefetch_related("line_items").get(id=invoice.id)
        return JsonResponse({
            "result": result,
            "invoice": _invoice_payload(invoice),
            "server_time": timezone.now().isoformat(),
        })
    if action == "reminder":
        if invoice.status != "sent":
            return JsonResponse({"error": "Reminders can only be sent for outstanding invoices."}, status=400)
        invoice.last_reminder_at = timezone.now()
        invoice.save(update_fields=["last_reminder_at"])
        return JsonResponse({
            "result": {
                "sent": False,
                "email": "queued_for_office",
                "message": "Reminder noted. Use web email settings to send configured reminder templates.",
            },
            "invoice": _invoice_payload(invoice),
            "server_time": timezone.now().isoformat(),
        })
    return JsonResponse({"error": "Unsupported invoice action."}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def invoice_line_item_action(request, invoice_id, item_id):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Invoices are only available to owners and managers."}, status=403)
    try:
        invoice = Invoice.objects.select_related("customer", "business").prefetch_related("line_items").get(
            id=invoice_id,
            business=session.business,
        )
        line_item = invoice.line_items.get(id=item_id)
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "Invoice not found."}, status=404)
    except InvoiceLineItem.DoesNotExist:
        return JsonResponse({"error": "Line item not found."}, status=404)

    data = _json_body(request)
    action = (data.get("action") or "paid").strip()
    request.user = session.user
    if action == "unpaid":
        line_item.is_paid = False
        line_item.paid_at = None
        line_item.paid_by = None
        line_item.payment_method = ""
        line_item.save(update_fields=["is_paid", "paid_at", "paid_by", "payment_method"])
        paid = False
    elif action == "paid":
        line_item.is_paid = True
        line_item.paid_at = timezone.now()
        line_item.paid_by = session.user
        line_item.payment_method = (data.get("payment_method") or "").strip()
        line_item.save(update_fields=["is_paid", "paid_at", "paid_by", "payment_method"])
        paid = True
    else:
        return JsonResponse({"error": "Unsupported line item action."}, status=400)

    _log_invoice_audit(
        invoice,
        "line_items_edited",
        request=request,
        details={"line_item_id": line_item.id, "line_item": line_item.description, "paid": paid},
    )
    invoice = Invoice.objects.prefetch_related("line_items").get(id=invoice.id)
    _sync_invoice_payment_from_line_items(invoice, request=request)
    invoice = Invoice.objects.select_related("customer").prefetch_related("line_items").get(id=invoice.id)
    return JsonResponse({
        "invoice": _invoice_payload(invoice),
        "summary": {
            "subtotal": f"{invoice.subtotal:.2f}",
            "tax": f"{invoice.tax:.2f}",
            "total": f"{invoice.total:.2f}",
            "paid_items": invoice.line_items.filter(is_paid=True).count(),
            "line_items": invoice.line_items.count(),
        },
        "line_items": [_invoice_line_item_payload(item) for item in invoice.line_items.all()],
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def estimates(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Estimates are only available to owners and managers."}, status=403)

    data = _json_body(request)
    customer, error = _money_customer_or_error(session, data.get("customer_id"))
    if error:
        return error
    property_obj = None
    if data.get("property_id"):
        try:
            property_obj = Property.objects.get(id=data.get("property_id"), customer__business=session.business)
        except (Property.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"error": "Property not found."}, status=404)

    estimate = Estimate.objects.create(
        business=session.business,
        customer=customer,
        property=property_obj,
        title=(data.get("title") or "FIELDLGX Service Estimate").strip(),
        notes=(data.get("notes") or "").strip(),
        valid_until=_parse_date(data.get("valid_until")),
        deposit_required=bool(data.get("deposit_required", False)),
        deposit_type=(data.get("deposit_type") or "fixed").strip() if data.get("deposit_required") else "fixed",
        deposit_amount=_parse_decimal(data.get("deposit_amount")),
    )
    error = _create_estimate_line_items(estimate, data.get("line_items"))
    if error:
        estimate.delete()
        return error
    estimate = Estimate.objects.select_related("customer", "property").prefetch_related("line_items").get(id=estimate.id)
    return JsonResponse({
        "estimate": _estimate_payload(estimate),
        "summary": {
            "base_total": f"{estimate.base_total():.2f}",
            "addons_total": f"{estimate.addons_total():.2f}",
            "total": f"{estimate.total():.2f}",
            "line_items": estimate.line_items.count(),
        },
        "deposit": {
            "required": estimate.deposit_required,
            "type": estimate.deposit_type,
            "amount": f"{(estimate.deposit_amount or Decimal('0')):.2f}",
            "amount_due": f"{estimate.deposit_dollar_amount():.2f}",
            "paid": estimate.deposit_paid,
        },
        "line_items": [_estimate_line_item_payload(item) for item in estimate.line_items.all()],
        "server_time": timezone.now().isoformat(),
    }, status=201)


@require_http_methods(["GET"])
def estimate_detail(request, estimate_id):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Estimates are only available to owners and managers."}, status=403)

    try:
        estimate = Estimate.objects.select_related("customer", "property").prefetch_related("line_items").get(
            id=estimate_id,
            business=session.business,
        )
    except Estimate.DoesNotExist:
        return JsonResponse({"error": "Estimate not found."}, status=404)

    deposit_due = estimate.deposit_dollar_amount()
    return JsonResponse({
        "estimate": _estimate_payload(estimate),
        "summary": {
            "base_total": f"{estimate.base_total():.2f}",
            "addons_total": f"{estimate.addons_total():.2f}",
            "total": f"{estimate.total():.2f}",
            "line_items": estimate.line_items.count(),
        },
        "deposit": {
            "required": estimate.deposit_required,
            "type": estimate.deposit_type,
            "amount": f"{(estimate.deposit_amount or Decimal('0')):.2f}",
            "amount_due": f"{deposit_due:.2f}",
            "paid": estimate.deposit_paid,
        },
        "line_items": [_estimate_line_item_payload(item) for item in estimate.line_items.all()],
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def estimate_action(request, estimate_id):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Estimates are only available to owners and managers."}, status=403)
    try:
        estimate = Estimate.objects.select_related("customer").get(id=estimate_id, business=session.business)
    except Estimate.DoesNotExist:
        return JsonResponse({"error": "Estimate not found."}, status=404)

    action = (_json_body(request).get("action") or "").strip()
    if action == "mark_sent":
        estimate.status = "sent"
        estimate.sent_at = timezone.now()
        estimate.save(update_fields=["status", "sent_at"])
    elif action == "followup":
        if estimate.status == "accepted":
            return JsonResponse({"error": "Accepted estimates do not need follow-up."}, status=400)
        estimate.last_follow_up_at = timezone.now()
        estimate.save(update_fields=["last_follow_up_at"])
    else:
        return JsonResponse({"error": "Unsupported estimate action."}, status=400)
    return JsonResponse({
        "estimate": _estimate_payload(estimate),
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_POST
def estimate_photos(request, estimate_id):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if session.user.role not in {"owner", "manager"}:
        return JsonResponse({"error": "Estimate photos are only available to owners and managers."}, status=403)
    try:
        estimate = Estimate.objects.get(id=estimate_id, business=session.business)
    except Estimate.DoesNotExist:
        return JsonResponse({"error": "Estimate not found."}, status=404)

    image, error = _uploaded_image_or_error(request)
    if error:
        return error

    caption = (request.POST.get("caption") or "").strip()[:255]
    next_order = estimate.images.count()
    EstimateImage.objects.create(
        estimate=estimate,
        image=image,
        caption=caption,
        order=next_order,
    )
    estimate = Estimate.objects.select_related("customer", "property").prefetch_related("line_items", "images").get(id=estimate.id)
    return JsonResponse({
        "estimate": _estimate_payload(estimate),
        "photo_count": estimate.images.count(),
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_POST
def receipts(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)

    image, error = _uploaded_image_or_error(request)
    if error:
        return error

    job = None
    job_id = request.POST.get("job_id")
    if job_id:
        try:
            job = Job.objects.get(id=job_id, property__customer__business=session.business)
        except (Job.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"error": "Job not found."}, status=404)

    receipt_date = _parse_date(request.POST.get("receipt_date"))
    if not receipt_date:
        return JsonResponse({"error": "Invalid receipt date."}, status=400)
    amount = _parse_decimal(request.POST.get("amount"))
    category = (request.POST.get("category") or "other").strip().lower()
    allowed_categories = {choice[0] for choice in Receipt.CATEGORY_CHOICES}
    if category not in allowed_categories:
        category = "other"

    receipt = Receipt.objects.create(
        business=session.business,
        file=image,
        receipt_date=receipt_date,
        amount=amount,
        vendor=(request.POST.get("vendor") or "").strip()[:255],
        description=(request.POST.get("description") or "").strip()[:500],
        category=category,
        job=job,
        uploaded_by=session.user,
    )
    return JsonResponse({
        "receipt": _receipt_payload(receipt),
        "server_time": timezone.now().isoformat(),
    }, status=201)


def time_clock_status(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    return JsonResponse(_time_clock_payload(session.user))


@csrf_exempt
@require_POST
def time_clock_in(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    active_entry = _active_time_entry(session.user)
    if not active_entry:
        data = _json_body(request)
        entry_data = {
            "user": session.user,
            "clock_in": timezone.now(),
        }
        latitude = _parse_decimal(data.get("latitude"))
        longitude = _parse_decimal(data.get("longitude"))
        if latitude is not None and longitude is not None:
            entry_data["clock_in_latitude"] = latitude
            entry_data["clock_in_longitude"] = longitude
        TimeEntry.objects.create(**entry_data)
    return JsonResponse(_time_clock_payload(session.user))


@csrf_exempt
@require_POST
def time_clock_out(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    entry = _active_time_entry(session.user)
    if not entry:
        return JsonResponse({"error": "No active clock-in found."}, status=400)

    data = _json_body(request)
    entry.clock_out = timezone.now()
    update_fields = ["clock_out"]
    latitude = _parse_decimal(data.get("latitude"))
    longitude = _parse_decimal(data.get("longitude"))
    if latitude is not None and longitude is not None:
        entry.clock_out_latitude = latitude
        entry.clock_out_longitude = longitude
        update_fields.extend(["clock_out_latitude", "clock_out_longitude"])
    entry.save(update_fields=update_fields)
    return JsonResponse(_time_clock_payload(session.user))


@csrf_exempt
@require_POST
def time_clock_location(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    entry = _active_time_entry(session.user)
    if not entry:
        return JsonResponse({"error": "Clock in before sharing location."}, status=400)

    data = _json_body(request)
    latitude = _parse_decimal(data.get("latitude"))
    longitude = _parse_decimal(data.get("longitude"))
    if latitude is None or longitude is None:
        return JsonResponse({"error": "Latitude and longitude are required."}, status=400)

    ping_data = {
        "time_entry": entry,
        "user": session.user,
        "latitude": latitude,
        "longitude": longitude,
    }
    accuracy = _parse_decimal(data.get("accuracy"))
    if accuracy is not None:
        ping_data["accuracy_meters"] = accuracy
    ping = TimeEntryLocationPing.objects.create(**ping_data)
    return JsonResponse({
        "ok": True,
        "location": _location_ping_payload(ping),
        "time_clock": _time_clock_payload(session.user),
    })


SUPPORTED_SYNC_ENTITIES = {
    "client",
    "property",
    "job",
    "job_note",
    "property_note",
    "job_service_item",
    "estimate",
    "invoice",
    "time_entry",
    "location_event",
}


def sync_pull(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    now = timezone.now()
    clients = Customer.objects.filter(business=session.business).prefetch_related("properties").order_by("-updated_at", "id")[:100]
    jobs = _job_queryset_for_mobile(session).order_by("-created_at", "id")[:100]
    invoices = Invoice.objects.filter(business=session.business).select_related("customer").order_by("-issue_date", "-id")[:100]
    estimates = Estimate.objects.filter(business=session.business).select_related("customer").order_by("-updated_at", "-id")[:100]
    return JsonResponse({
        "cursor": now.isoformat(),
        "server_time": now.isoformat(),
        "changes": {
            "clients": [_client_payload(customer) for customer in clients],
            "jobs": [_job_payload(job, job.scheduled_date or date.today()) for job in jobs],
            "invoices": [_invoice_payload(invoice) for invoice in invoices],
            "estimates": [_estimate_payload(estimate) for estimate in estimates],
        },
        "conflicts": [],
    })


@csrf_exempt
@require_POST
def sync_push(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    data = _json_body(request)
    accepted = []
    rejected = []
    for index, mutation in enumerate(data.get("mutations") or []):
        entity_type = mutation.get("entity_type")
        if entity_type not in SUPPORTED_SYNC_ENTITIES:
            rejected.append({
                "index": index,
                "local_id": mutation.get("local_id") or "",
                "entity_type": entity_type or "",
                "reason": "Unsupported entity type.",
            })
            continue
        operation = mutation.get("operation")
        payload = mutation.get("payload") or {}
        local_id = mutation.get("local_id") or ""
        if entity_type == "client" and operation == "create":
            if session.user.role not in {"owner", "manager"}:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": "Clients are only available to owners and managers.",
                })
                continue
            customer, error = _create_client_from_payload(payload, session.business)
            if error:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Client sync failed."),
                })
                continue
            accepted.append({
                "index": index,
                "local_id": local_id,
                "entity_type": entity_type,
                "operation": operation,
                "server_id": customer.id,
                "payload": _client_payload(customer),
            })
            continue
        if entity_type == "job" and operation == "create":
            if session.user.role not in {"owner", "manager"}:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": "Jobs can only be created by owners and managers.",
                })
                continue
            try:
                property_obj = Property.objects.get(id=payload.get("property_id"), customer__business=session.business)
            except (Property.DoesNotExist, ValueError, TypeError):
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": "Property not found.",
                })
                continue
            job = Job.objects.create(property=property_obj, status="scheduled")
            error = _apply_job_write_fields(job, payload, session.business)
            if error:
                job.delete()
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Job sync failed."),
                })
                continue
            error = _replace_job_service_items(job, payload.get("service_items"), session.business)
            if error:
                job.delete()
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Job sync failed."),
                })
                continue
            job = _job_queryset_for_mobile(session).get(id=job.id)
            accepted.append({
                "index": index,
                "local_id": local_id,
                "entity_type": entity_type,
                "operation": operation,
                "server_id": job.id,
                "payload": _job_payload(job, job.scheduled_date or date.today()),
            })
            continue
        if entity_type == "invoice" and operation == "create":
            if session.user.role not in {"owner", "manager"}:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": "Invoices can only be created by owners and managers.",
                })
                continue
            customer, error = _money_customer_or_error(session, payload.get("customer_id"))
            if error:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Invoice sync failed."),
                })
                continue
            invoice = Invoice.objects.create(
                business=session.business,
                customer=customer,
                status="draft",
                due_date=_parse_date(payload.get("due_date")),
                enable_card_payment=_parse_bool(
                    payload.get("enable_card_payment"),
                    default=invoice_card_payment_default(session.business),
                ),
            )
            error = _create_invoice_line_items(invoice, payload.get("line_items"))
            if error:
                invoice.delete()
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Invoice sync failed."),
                })
                continue
            invoice = Invoice.objects.select_related("customer").prefetch_related("line_items").get(id=invoice.id)
            accepted.append({
                "index": index,
                "local_id": local_id,
                "entity_type": entity_type,
                "operation": operation,
                "server_id": invoice.id,
                "payload": _invoice_payload(invoice),
            })
            continue
        if entity_type == "estimate" and operation == "create":
            if session.user.role not in {"owner", "manager"}:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": "Estimates can only be created by owners and managers.",
                })
                continue
            customer, error = _money_customer_or_error(session, payload.get("customer_id"))
            if error:
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Estimate sync failed."),
                })
                continue
            property_obj = None
            if payload.get("property_id"):
                try:
                    property_obj = Property.objects.get(id=payload.get("property_id"), customer__business=session.business)
                except (Property.DoesNotExist, ValueError, TypeError):
                    rejected.append({
                        "index": index,
                        "local_id": local_id,
                        "entity_type": entity_type,
                        "reason": "Property not found.",
                    })
                    continue
            estimate = Estimate.objects.create(
                business=session.business,
                customer=customer,
                property=property_obj,
                title=(payload.get("title") or "FIELDLGX Service Estimate").strip(),
                notes=(payload.get("notes") or "").strip(),
                valid_until=_parse_date(payload.get("valid_until")),
                deposit_required=bool(payload.get("deposit_required", False)),
                deposit_type=(payload.get("deposit_type") or "fixed").strip() if payload.get("deposit_required") else "fixed",
                deposit_amount=_parse_decimal(payload.get("deposit_amount")),
            )
            error = _create_estimate_line_items(estimate, payload.get("line_items"))
            if error:
                estimate.delete()
                rejected.append({
                    "index": index,
                    "local_id": local_id,
                    "entity_type": entity_type,
                    "reason": json.loads(error.content.decode("utf-8")).get("error", "Estimate sync failed."),
                })
                continue
            estimate = Estimate.objects.select_related("customer", "property").prefetch_related("line_items").get(id=estimate.id)
            accepted.append({
                "index": index,
                "local_id": local_id,
                "entity_type": entity_type,
                "operation": operation,
                "server_id": estimate.id,
                "payload": _estimate_payload(estimate),
            })
            continue
        rejected.append({
            "index": index,
            "local_id": local_id,
            "entity_type": entity_type,
            "reason": "Entity sync handler is not implemented yet.",
        })
    return JsonResponse({
        "accepted": accepted,
        "rejected": rejected,
        "conflicts": [],
        "cursor": timezone.now().isoformat(),
    })


def _job_alerts(job):
    alerts = []
    prop = job.property
    if prop.gate_code:
        alerts.append({"label": "Gate code", "text": prop.gate_code})
    if prop.has_dog:
        alerts.append({"label": "Dog on site", "text": "Check before entering the yard."})
    if (prop.notes or "").strip():
        alerts.append({"label": "Property note", "text": prop.notes.strip()})
    for note in getattr(prop, "crew_visible_notes", [])[:3]:
        alerts.append({"label": "Permanent note", "text": note.text})
    return alerts


def _service_item_payload(item):
    return {
        "id": item.id,
        "name": item.description or item.service.name,
        "detail_description": item.detail_description,
        "quantity": str(item.quantity),
        "unit": item.unit,
        "unit_price": str(item.unit_price),
        "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
    }


def _job_payload(job, target_date):
    items = list(job.service_items.all())
    if job.scheduled_end_date and job.scheduled_date and job.scheduled_end_date > job.scheduled_date:
        items = [item for item in items if item.scheduled_date is None or item.scheduled_date == target_date]
    customer = job.property.customer
    crew_color = (
        job.assigned_crew.color
        if getattr(job, "assigned_crew", None) and getattr(job.assigned_crew, "color", None)
        else UNASSIGNED_CALENDAR_COLOR
    )
    status_color = STATUS_CALENDAR_COLORS.get(job.status, STATUS_CALENDAR_COLORS["scheduled"])
    job_color_override = (job.color or "").strip() or None
    return {
        "id": job.id,
        "status": job.status,
        "color": job_color_override or status_color,
        "status_color": status_color,
        "assignee_color": crew_color,
        "crew_color": crew_color,
        "job_color_override": job_color_override,
        "scheduled_date": job.scheduled_date.isoformat() if job.scheduled_date else None,
        "scheduled_end_date": job.scheduled_end_date.isoformat() if job.scheduled_end_date else None,
        "scheduled_time": job.scheduled_time.strftime("%H:%M") if job.scheduled_time else None,
        "scheduled_end_time": job.scheduled_end_time.strftime("%H:%M") if job.scheduled_end_time else None,
        "route_order": job.route_order,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
        },
        "property": {
            "id": job.property.id,
            "address": job.property.address,
            "latitude": str(job.property.latitude) if job.property.latitude is not None else None,
            "longitude": str(job.property.longitude) if job.property.longitude is not None else None,
        },
        "assigned": {
            "crew": job.assigned_crew.name if job.assigned_crew else None,
            "employee": job.assigned_to.get_full_name() or job.assigned_to.username if job.assigned_to else None,
        },
        "notes": job.notes,
        "alerts": _job_alerts(job),
        "service_items": [_service_item_payload(item) for item in items],
        "photo_count": job.site_photo_count,
    }


def _job_note_payload(note):
    author = note.author
    return {
        "id": note.id,
        "text": note.text,
        "visibility": note.visibility,
        "author": author.get_full_name() or author.username if author else "",
        "created_at": note.created_at.isoformat(),
    }


def _job_issue_payload(issue):
    reporter = issue.reported_by
    return {
        "id": issue.id,
        "issue_type": issue.issue_type,
        "issue_type_display": issue.get_issue_type_display(),
        "description": issue.description,
        "status": issue.status,
        "reported_by": reporter.get_full_name() or reporter.username if reporter else "",
        "created_at": issue.created_at.isoformat(),
    }


def _job_actions_payload(job, business):
    requires_photo = bool(getattr(business, "require_completion_photo", False))
    has_completion_photo = job.completion_photos.exists()
    return {
        "can_start": job.status == "scheduled",
        "can_complete": job.status == "in_progress" and (not requires_photo or has_completion_photo),
        "can_skip": job.status in {"scheduled", "in_progress"},
        "requires_completion_photo": requires_photo,
        "has_completion_photo": has_completion_photo,
    }


def _job_detail_payload(job, session):
    target_date = job.scheduled_date or date.today()
    notes = list(job.job_notes.all())
    if session.user.role == "crew":
        notes = [note for note in notes if note.visibility == JobNote.VISIBILITY_CREW]
    return {
        "job": _job_payload(job, target_date),
        "actions": _job_actions_payload(job, session.business),
        "job_notes": [_job_note_payload(note) for note in notes],
        "job_issues": [_job_issue_payload(issue) for issue in job.issues.all()],
        "server_time": timezone.now().isoformat(),
    }


def _job_queryset_for_mobile(session):
    jobs = Job.objects.filter(
        property__customer__business=session.business,
    ).select_related(
        "property",
        "property__customer",
        "assigned_to",
        "assigned_crew",
    ).prefetch_related(
        "assigned_employees",
        "service_items__service",
        "completion_photos",
        "job_notes__author",
        "issues__reported_by",
        Prefetch(
            "property__property_notes",
            queryset=PropertyNote.objects.filter(visibility=PropertyNote.VISIBILITY_CREW).select_related("author"),
            to_attr="crew_visible_notes",
        ),
    ).annotate(
        site_photo_count=Count("site_photos"),
    ).distinct()

    if session.user.role == "crew":
        jobs = jobs.filter(
            Q(assigned_to=session.user) |
            Q(assigned_employees=session.user) |
            Q(assigned_crew__members=session.user) |
            Q(assigned_crew__crew_leader=session.user)
        ).distinct()
    return jobs


def _mobile_job_or_response(request, job_id):
    session = session_from_request(request)
    if not session:
        return None, None, JsonResponse({"error": "Authentication required."}, status=401)

    business_job_exists = Job.objects.filter(
        id=job_id,
        property__customer__business=session.business,
    ).exists()
    if not business_job_exists:
        return None, session, JsonResponse({"error": "Job not found."}, status=404)

    try:
        job = _job_queryset_for_mobile(session).get(id=job_id)
    except Job.DoesNotExist:
        return None, session, JsonResponse({"error": "You do not have access to this job."}, status=403)
    return job, session, None


def _update_job_location(job, data):
    update_fields = []
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    if latitude not in (None, "") and longitude not in (None, ""):
        job.technician_latitude = latitude
        job.technician_longitude = longitude
        job.technician_location_updated_at = timezone.now()
        update_fields.extend([
            "technician_latitude",
            "technician_longitude",
            "technician_location_updated_at",
        ])
    return update_fields


def today(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    target_date = _parse_date(request.GET.get("date"))
    if not target_date:
        return JsonResponse({"error": "Invalid date."}, status=400)

    jobs = Job.objects.filter(
        Q(scheduled_date=target_date) |
        Q(scheduled_date__lte=target_date, scheduled_end_date__gte=target_date),
        property__customer__business=session.business,
    ).select_related(
        "property",
        "property__customer",
        "assigned_to",
        "assigned_crew",
    ).prefetch_related(
        "service_items__service",
        "assigned_employees",
        Prefetch(
            "property__property_notes",
            queryset=PropertyNote.objects.filter(visibility=PropertyNote.VISIBILITY_CREW).select_related("author"),
            to_attr="crew_visible_notes",
        ),
    ).annotate(
        site_photo_count=Count("site_photos"),
        is_done=Case(
            When(status__in=["completed", "skipped", "cancelled"], then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).distinct()

    if session.user.role == "crew":
        jobs = jobs.filter(
            Q(assigned_to=session.user) |
            Q(assigned_employees=session.user) |
            Q(assigned_crew__members=session.user) |
            Q(assigned_crew__crew_leader=session.user)
        ).distinct()

    jobs = list(jobs.order_by("is_done", "route_order", "scheduled_time", "id"))
    completed = sum(1 for job in jobs if job.status in {"completed", "skipped"})
    return JsonResponse({
        "date": target_date.isoformat(),
        "summary": {
            "total": len(jobs),
            "completed": completed,
            "remaining": max(len(jobs) - completed, 0),
        },
        "jobs": [_job_payload(job, target_date) for job in jobs],
    })


@csrf_exempt
def job_detail(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error
    if request.method == "PATCH":
        if session.user.role not in {"owner", "manager"}:
            return JsonResponse({"error": "Jobs can only be edited by owners and managers."}, status=403)
        data = _json_body(request)
        error = _apply_job_write_fields(job, data, session.business)
        if error:
            return error
        error = _replace_job_service_items(job, data.get("service_items"), session.business)
        if error:
            return error
        job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_start(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error
    if job.status not in {"scheduled", "in_progress"}:
        return JsonResponse({"error": "This job cannot be started."}, status=400)

    data = _json_body(request)
    update_fields = _update_job_location(job, data)
    if job.status != "in_progress":
        job.status = "in_progress"
        update_fields.append("status")
    if not job.started_at:
        job.started_at = timezone.now()
        update_fields.append("started_at")
    if update_fields:
        job.save(update_fields=update_fields)
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_complete(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error
    if job.status != "in_progress":
        return JsonResponse({"error": "This job cannot be completed."}, status=400)
    if getattr(session.business, "require_completion_photo", False) and not job.completion_photos.exists():
        return JsonResponse({"error": "Completion photo required."}, status=400)

    data = _json_body(request)
    update_fields = _update_job_location(job, data)
    now = timezone.now()
    if not job.started_at:
        job.started_at = now
        update_fields.append("started_at")
    job.status = "completed"
    job.completed_at = now
    job.completed_by = session.user
    update_fields.extend(["status", "completed_at", "completed_by"])
    job.save(update_fields=update_fields)
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_skip(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error
    if job.status not in {"scheduled", "in_progress"}:
        return JsonResponse({"error": "This job cannot be skipped."}, status=400)

    data = _json_body(request)
    reason = (data.get("reason") or "").strip()
    if not reason:
        return JsonResponse({"error": "Skip reason is required."}, status=400)

    update_fields = _update_job_location(job, data)
    job.status = "skipped"
    job.skip_reason = reason
    job.skipped_at = timezone.now()
    update_fields.extend(["status", "skip_reason", "skipped_at"])
    job.save(update_fields=update_fields)
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_completion_photo(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error

    image = request.FILES.get("photo") or request.FILES.get("image")
    if not image:
        return JsonResponse({"error": "Photo is required."}, status=400)

    allowed_image_types = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    if image.content_type not in allowed_image_types:
        return JsonResponse({"error": "Invalid file type."}, status=400)
    if image.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "Photo must be 10 MB or smaller."}, status=400)

    JobCompletionPhoto.objects.create(job=job, image=image, uploaded_by=session.user)
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_photos(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error

    image = request.FILES.get("photo") or request.FILES.get("image")
    if not image:
        return JsonResponse({"error": "Photo is required."}, status=400)

    allowed_image_types = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    if image.content_type not in allowed_image_types:
        return JsonResponse({"error": "Invalid file type."}, status=400)
    if image.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "Photo must be 10 MB or smaller."}, status=400)

    category = (request.POST.get("category") or "general").strip().lower()
    allowed_categories = {choice[0] for choice in JobPhoto.CATEGORY_CHOICES}
    if category not in allowed_categories:
        category = "general"
    caption = (request.POST.get("caption") or "").strip()[:255]

    JobPhoto.objects.create(
        job=job,
        image=image,
        category=category,
        caption=caption,
        uploaded_by=session.user,
    )
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_notes(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error

    data = _json_body(request)
    text = (data.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "Note text is required."}, status=400)

    visibility = (data.get("visibility") or JobNote.VISIBILITY_CREW).strip().lower()
    if visibility not in {JobNote.VISIBILITY_CREW, JobNote.VISIBILITY_INTERNAL}:
        visibility = JobNote.VISIBILITY_CREW
    if session.user.role == "crew":
        visibility = JobNote.VISIBILITY_CREW

    JobNote.objects.create(
        job=job,
        author=session.user,
        text=text,
        visibility=visibility,
    )
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))


@csrf_exempt
@require_POST
def job_issues(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error

    data = _json_body(request)
    description = (data.get("description") or "").strip()
    if not description:
        return JsonResponse({"error": "Issue description is required."}, status=400)

    issue_type = (data.get("issue_type") or "other").strip().lower()
    allowed_types = {choice[0] for choice in JobIssue.TYPE_CHOICES}
    if issue_type not in allowed_types:
        issue_type = "other"

    JobIssue.objects.create(
        job=job,
        reported_by=session.user,
        issue_type=issue_type,
        description=description,
    )
    job = _job_queryset_for_mobile(session).get(id=job.id)
    return JsonResponse(_job_detail_payload(job, session))

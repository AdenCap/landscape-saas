import json
from datetime import date

from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from jobs.models import Job, JobCompletionPhoto, JobIssue, JobNote, JobPhoto, PropertyNote

from . import auth as mobile_auth
from .auth import issue_access_token, session_from_refresh_token, session_from_request, user_by_email
from .models import MobileDeviceSession


def _json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


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
        "client_saved_cards_enabled": bool(getattr(business, "client_saved_cards_enabled", False)),
    }


def _parse_date(value):
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


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
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    user = user_by_email(email)
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
    return JsonResponse({
        "cursor": now.isoformat(),
        "server_time": now.isoformat(),
        "changes": {},
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
        rejected.append({
            "index": index,
            "local_id": mutation.get("local_id") or "",
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
    return {
        "id": job.id,
        "status": job.status,
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


def job_detail(request, job_id):
    job, session, error = _mobile_job_or_response(request, job_id)
    if error:
        return error
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

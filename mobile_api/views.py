import json
from datetime import date

from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from jobs.models import Job, PropertyNote

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

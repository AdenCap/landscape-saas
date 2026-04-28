import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import auth as mobile_auth
from .auth import issue_access_token, session_from_refresh_token, user_by_email
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

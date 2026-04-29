import base64
import json
import secrets
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import MobileDeviceSession, hash_token

ACCESS_TOKEN_TTL_SECONDS = 15 * 60


def _signing_key():
    return settings.SECRET_KEY


def issue_access_token(session):
    import hashlib
    import hmac

    payload = {
        "sid": session.id,
        "uid": session.user_id,
        "bid": session.business_id,
        "exp": int(time.time()) + ACCESS_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(8),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_signing_key().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def authenticate_access_token(token):
    import hashlib
    import hmac

    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_signing_key().encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    padded = body + ("=" * (-len(body) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, TypeError):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    session = MobileDeviceSession.objects.select_related("user", "business").filter(
        id=payload.get("sid"),
        user_id=payload.get("uid"),
        business_id=payload.get("bid"),
        revoked_at__isnull=True,
    ).first()
    if not session:
        return None
    session.last_seen_at = timezone.now()
    session.save(update_fields=["last_seen_at"])
    return session


def session_from_refresh_token(refresh_token):
    if not refresh_token:
        return None
    return MobileDeviceSession.objects.select_related("user", "business").filter(
        refresh_token_hash=hash_token(refresh_token),
        revoked_at__isnull=True,
    ).first()


def session_from_request(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return None
    return authenticate_access_token(header.removeprefix("Bearer ").strip())


def user_by_email(email):
    User = get_user_model()
    return User.objects.filter(email__iexact=(email or "").strip(), is_active=True).first()


def user_by_identifier(identifier):
    User = get_user_model()
    value = (identifier or "").strip()
    if not value:
        return None
    return User.objects.filter(email__iexact=value, is_active=True).first() or User.objects.filter(
        username__iexact=value,
        is_active=True,
    ).first()


def verify_apple_identity_token(identity_token):
    """
    Verify an Apple identity token and return {"email": str, "sub": str}.
    The full JWKS validation belongs in the production social-auth pass.
    """
    raise NotImplementedError("Apple identity token verification is not configured yet.")


def verify_google_identity_token(identity_token):
    """
    Verify a Google identity token and return {"email": str, "sub": str}.
    The full Google token validation belongs in the production social-auth pass.
    """
    raise NotImplementedError("Google identity token verification is not configured yet.")

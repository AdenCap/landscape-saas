import base64
import json
import secrets
import time
import urllib.request

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

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
    """
    apple_client_id = _apple_client_id()
    if not apple_client_id:
        raise ValueError("Apple client ID is not configured.")
    header, payload, signing_input, signature = _decode_jwt(identity_token)
    if payload.get("iss") != "https://appleid.apple.com":
        raise ValueError("Invalid Apple token issuer.")
    if payload.get("aud") != apple_client_id:
        raise ValueError("Invalid Apple token audience.")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Apple token expired.")
    _verify_jwks_signature(
        jwks_url="https://appleid.apple.com/auth/keys",
        key_id=header.get("kid"),
        algorithm=header.get("alg"),
        signing_input=signing_input,
        signature=signature,
    )
    email = (payload.get("email") or "").strip()
    if not email:
        raise ValueError("Apple token did not include an email address.")
    return {"email": email, "sub": payload.get("sub") or ""}


def verify_google_identity_token(identity_token):
    """
    Verify a Google identity token and return {"email": str, "sub": str}.
    """
    audience_values = _google_client_ids()
    if not audience_values:
        raise ValueError("Google client ID is not configured.")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise ValueError("google-auth is not installed.") from exc

    last_error = None
    for audience in audience_values:
        try:
            payload = id_token.verify_oauth2_token(identity_token, google_requests.Request(), audience)
            if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise ValueError("Invalid Google token issuer.")
            if payload.get("email_verified") is False:
                raise ValueError("Google email is not verified.")
            email = (payload.get("email") or "").strip()
            if not email:
                raise ValueError("Google token did not include an email address.")
            return {"email": email, "sub": payload.get("sub") or ""}
        except Exception as exc:
            last_error = exc
    raise ValueError("Could not verify Google identity token.") from last_error


def _apple_client_id():
    provider = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("apple", {})
    return (
        getattr(settings, "APPLE_IOS_CLIENT_ID", "")
        or provider.get("APP", {}).get("client_id", "")
        or getattr(settings, "APPLE_CLIENT_ID", "")
    )


def _google_client_ids():
    provider = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("google", {})
    values = [
        getattr(settings, "GOOGLE_IOS_CLIENT_ID", ""),
        provider.get("APP", {}).get("client_id", ""),
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""),
    ]
    return [value for value in dict.fromkeys(v.strip() for v in values if v and v.strip())]


def _decode_jwt(identity_token):
    parts = (identity_token or "").split(".")
    if len(parts) != 3:
        raise ValueError("Malformed identity token.")
    header = json.loads(_urlsafe_b64decode(parts[0]))
    payload = json.loads(_urlsafe_b64decode(parts[1]))
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    signature = _urlsafe_b64decode(parts[2])
    return header, payload, signing_input, signature


def _urlsafe_b64decode(value):
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode())


def _verify_jwks_signature(jwks_url, key_id, algorithm, signing_input, signature):
    if algorithm != "RS256" or not key_id:
        raise ValueError("Unsupported identity token signature.")
    with urllib.request.urlopen(jwks_url, timeout=5) as response:
        jwks = json.loads(response.read().decode("utf-8"))
    key = next((candidate for candidate in jwks.get("keys", []) if candidate.get("kid") == key_id), None)
    if not key:
        raise ValueError("Identity token signing key not found.")
    public_numbers = RSAPublicNumbers(
        e=int.from_bytes(_urlsafe_b64decode(key["e"]), "big"),
        n=int.from_bytes(_urlsafe_b64decode(key["n"]), "big"),
    )
    public_key = public_numbers.public_key()
    try:
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise ValueError("Invalid identity token signature.") from exc

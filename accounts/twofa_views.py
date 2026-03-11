"""
Optional two-factor authentication (2FA) via TOTP.
2FA is required only on new devices: after verifying once, we mark the device as trusted
and skip 2FA on future logins from that device.
"""
import secrets
from io import BytesIO
import base64

from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required

from accounts.decorators import role_required
from accounts.models import TrustedDevice

# Cookie name and max age for "trusted device" (2FA only on new devices)
TRUSTED_DEVICE_COOKIE = "fieldops_trusted"
TRUSTED_DEVICE_MAX_AGE = 90 * 24 * 60 * 60  # 90 days


def _get_otp_device_model():
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice
        return TOTPDevice
    except ImportError:
        return None


def _otp_login(request, device):
    try:
        from django_otp import login as otp_login
        otp_login(request, device)
    except ImportError:
        pass


def _user_has_2fa(user):
    TOTPDevice = _get_otp_device_model()
    if TOTPDevice is None:
        return False
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def post_login_check(request):
    """
    Run after every password login (LOGIN_REDIRECT_URL points here).
    If user has 2FA and this is a new device, send them to verify; otherwise go to dashboard.
    """
    from django.utils.http import url_has_allowed_host_and_scheme
    # Default redirect: owners go to dashboard, crew to their jobs, others to dashboard
    default_redirect = "/dashboard/"
    if request.user.is_authenticated:
        role = getattr(request.user, "role", None)
        if role == "crew":
            default_redirect = "/jobs/crew/"
    next_url = request.GET.get("next") or default_redirect
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = default_redirect
    if not request.user.is_authenticated:
        return redirect("/accounts/login/")
    if not _user_has_2fa(request.user):
        return redirect(next_url)
    cookie_token = request.COOKIES.get(TRUSTED_DEVICE_COOKIE)
    if cookie_token and TrustedDevice.objects.filter(user=request.user, token=cookie_token).exists():
        return redirect(next_url)
    # New device: require 2FA
    return redirect(f"/accounts/verify/?next={next_url}")


@login_required
@role_required("owner")
@require_http_methods(["GET", "POST"])
def twofa_setup(request):
    """Create a TOTP device and show QR code for authenticator app."""
    TOTPDevice = _get_otp_device_model()
    if TOTPDevice is None:
        messages.warning(request, "2FA is not installed. Run: pip install django-otp qrcode, then add the apps and run migrate.")
        return redirect("business_settings")
    import qrcode
    import qrcode.image.svg
    import urllib.parse

    user = request.user
    device = TOTPDevice.objects.filter(user=user).first()

    if request.method == "POST":
        if device:
            device.delete()
            device = None
        if not device:
            device = TOTPDevice.objects.create(user=user, name="default", confirmed=False)
            device.save()
        token = request.POST.get("token", "").strip().replace(" ", "")
        if token and device.verify_token(token):
            device.confirmed = True
            device.save()
            _otp_login(request, device)
            # Mark this device as trusted so we don't ask for 2FA on next login here
            device_token = secrets.token_urlsafe(32)
            TrustedDevice.objects.create(user=user, token=device_token)
            response = redirect("business_settings")
            response.set_cookie(
                TRUSTED_DEVICE_COOKIE,
                device_token,
                max_age=TRUSTED_DEVICE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
            messages.success(request, "Two-factor authentication is now enabled.")
            return response
        elif token:
            messages.error(request, "Invalid code. Try again.")
        device = TOTPDevice.objects.filter(user=user).first()

    if not device:
        device = TOTPDevice.objects.create(user=user, name="default", confirmed=False)
        device.save()

    issuer = "FieldLgx"
    label = f"{issuer}:{user.username}"
    uri = f"otpauth://totp/{urllib.parse.quote(label)}?secret={device.key}&issuer={urllib.parse.quote(issuer)}"
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buf = BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, "accounts/twofa_setup.html", {
        "device": device,
        "qr_b64": qr_b64,
        "secret": device.key,
    })


@login_required
@require_http_methods(["GET", "POST"])
def twofa_verify(request):
    """Verify OTP token (only when logging in from a new device)."""
    TOTPDevice = _get_otp_device_model()
    if TOTPDevice is None:
        return redirect("/")
    user = request.user
    device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
    if not device:
        return redirect("/")

    if request.method == "POST":
        token = request.POST.get("token", "").strip().replace(" ", "")
        if token and device.verify_token(token):
            _otp_login(request, device)
            # Default redirect: owners go to dashboard, crew to their jobs
            default_redirect = "/dashboard/"
            if user.is_authenticated:
                role = getattr(user, "role", None)
                if role == "crew":
                    default_redirect = "/jobs/crew/"
            next_url = request.GET.get("next") or request.session.get("next_after_verify") or default_redirect
            request.session.pop("next_after_verify", None)
            # Mark this device as trusted so we don't ask for 2FA again on this device
            device_token = secrets.token_urlsafe(32)
            TrustedDevice.objects.create(user=user, token=device_token)
            response = redirect(next_url)
            response.set_cookie(
                TRUSTED_DEVICE_COOKIE,
                device_token,
                max_age=TRUSTED_DEVICE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
            return response
        messages.error(request, "Invalid code. Try again.")

    return render(request, "accounts/twofa_verify.html", {})


@login_required
@role_required("owner")
@require_POST
def twofa_revoke_device(request):
    """Revoke one trusted device; next login from that device will require 2FA."""
    device_id = request.POST.get("device_id")
    if device_id:
        TrustedDevice.objects.filter(user=request.user, pk=device_id).delete()
        messages.success(request, "Device removed. Next sign-in from that device will require your 2FA code.")
    return redirect("business_settings")


@login_required
@role_required("owner")
@require_POST
def twofa_disable(request):
    """Remove 2FA for the current user."""
    TOTPDevice = _get_otp_device_model()
    if TOTPDevice:
        TOTPDevice.objects.filter(user=request.user).delete()
    TrustedDevice.objects.filter(user=request.user).delete()
    messages.success(request, "Two-factor authentication has been disabled.")
    return redirect("business_settings")
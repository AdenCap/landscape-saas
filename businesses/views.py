from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from accounts.models import TrustedDevice
from .models import Business
from .forms import BusinessSettingsForm


@role_required("owner")
@require_http_methods(["GET", "POST"])
def business_settings(request):
    """Owner can configure email/phone used for client communication."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    if request.method == "POST":
        old_business_type = business.business_type
        form = BusinessSettingsForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            obj = form.save(commit=False)
            # Re-sync enabled_modules when business type changes
            if obj.business_type != old_business_type:
                obj.enabled_modules = list(
                    Business.MODULE_DEFAULTS.get(obj.business_type, [])
                )
            obj.save()
            messages.success(request, "Business settings updated.")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect("business_settings")
    else:
        form = BusinessSettingsForm(instance=business)

    has_2fa = False
    trusted_devices = []
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice
        has_2fa = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
        if has_2fa:
            trusted_devices = list(TrustedDevice.objects.filter(user=request.user))
    except Exception:
        pass
    # Effective platform fee % on card payments (per-business or global default)
    fee_percent = getattr(business, "stripe_connect_application_fee_percent", None)
    if fee_percent is None:
        from django.conf import settings
        fee_percent = getattr(settings, "STRIPE_CONNECT_APPLICATION_FEE_PERCENT", 0) or 0
    else:
        fee_percent = float(fee_percent)
    # Check if Stripe Connect is enabled at platform level
    from django.conf import settings
    stripe_connect_enabled = bool(getattr(settings, "STRIPE_SECRET_KEY", None))
    # Gmail OAuth status
    gmail_oauth_connected = business.gmail_oauth_available
    gmail_oauth_email = None
    if gmail_oauth_connected:
        try:
            from allauth.socialaccount.models import SocialAccount
            sa = SocialAccount.objects.filter(user=request.user, provider="google").first()
            if sa and sa.extra_data:
                gmail_oauth_email = sa.extra_data.get("email", "")
        except Exception:
            pass

    return render(request, "businesses/business_settings.html", {
        "form": form,
        "business": business,
        "next_value": request.GET.get("next", ""),
        "has_2fa": has_2fa,
        "trusted_devices": trusted_devices,
        "stripe_connect_fee_percent": fee_percent,
        "stripe_connect_enabled": stripe_connect_enabled,
        "gmail_oauth_connected": gmail_oauth_connected,
        "gmail_oauth_email": gmail_oauth_email,
    })


@require_POST
@role_required("owner")
def disconnect_gmail(request):
    """Remove the stored Gmail OAuth token so the owner can reconnect with a different account."""
    try:
        from allauth.socialaccount.models import SocialAccount, SocialToken
        sa = SocialAccount.objects.filter(user=request.user, provider="google").first()
        if sa:
            SocialToken.objects.filter(account=sa).delete()
            sa.delete()
            messages.success(request, "Gmail disconnected. You can now connect a different Gmail account.")
        else:
            messages.info(request, "No Gmail account was connected.")
    except Exception as exc:
        messages.error(request, f"Could not disconnect Gmail: {exc}")
    return redirect("business_settings")


@require_POST
@role_required("owner")
def test_gmail_connection(request):
    """Send a test email to verify Gmail (Settings) is configured correctly."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    from .email_sender import send_business_email, is_email_configured
    if not is_email_configured(business):
        messages.error(
            request,
            "Gmail is not connected. Sign in with Google or enter your Gmail App Password above, then try again.",
        )
        return redirect("business_settings")

    to_email = business.get_from_email() or business.email_smtp_user
    if not to_email:
        messages.error(request, "Set a From address or Gmail address first.")
        return redirect("business_settings")
    # Extract address if it's "Name <email>"
    if isinstance(to_email, str) and "<" in to_email and ">" in to_email:
        to_email = to_email.split("<")[1].split(">")[0].strip()

    ok, detail = send_business_email(
        business=business,
        to=to_email,
        subject="FieldLgx \u2013 Gmail test",
        body_text="This is a test email from FieldLgx. Your Gmail connection is working.",
    )
    if ok:
        method = "OAuth" if detail == "sent_oauth" else "SMTP"
        messages.success(request, f"Test email sent to {to_email} via {method}. Check your inbox.")
    else:
        from .email_sender import format_send_error
        messages.error(request, format_send_error(detail))
    return redirect("business_settings")


def serve_logo(request, business_id):
    """Public endpoint to serve the business logo as PNG. Used in emails where
    direct Supabase URLs may be blocked or return WebP (unsupported by Gmail)."""
    from django.http import HttpResponse
    business = get_object_or_404(Business, id=business_id)
    if not business.logo:
        return HttpResponse(status=404)
    try:
        import requests as _requests
        from PIL import Image as PILImage
        import io

        url = business.logo.url
        if url and url.startswith("http"):
            resp = _requests.get(url, timeout=10)
            resp.raise_for_status()
            img_data = io.BytesIO(resp.content)
        else:
            img_data = business.logo.open("rb")

        pil_img = PILImage.open(img_data)
        pil_img = pil_img.convert("RGBA") if pil_img.mode in ("RGBA", "LA", "P") else pil_img.convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        return HttpResponse(buf.read(), content_type="image/png")
    except Exception:
        return HttpResponse(status=404)

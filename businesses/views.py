from django.conf import settings
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
        else:
            # Show which fields have errors so user knows what to fix
            error_fields = ", ".join(form.errors.keys())
            messages.error(request, f"Could not save — please fix errors in: {error_fields}")
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

    payment_method_count = sum(
        1
        for value in [
            business.venmo_username,
            business.zelle_email_or_phone,
            business.cashapp_cashtag,
            business.paypal_link,
        ]
        if (value or "").strip()
    )
    logo_ready = bool(business.logo)
    contact_ready = bool((business.contact_email or "").strip() and (business.contact_phone or "").strip())
    email_ready = bool(gmail_oauth_connected or business.email_smtp_user and business.email_smtp_password)
    stripe_ready = bool(business.stripe_connect_account_id and business.stripe_connect_charges_enabled)
    try:
        from billing.models import DocumentTemplate
        estimate_template = DocumentTemplate.get_default_for_business(business, "estimate")
        invoice_template = DocumentTemplate.get_default_for_business(business, "invoice")
    except Exception:
        estimate_template = None
        invoice_template = None
    document_ready = bool(
        logo_ready
        and contact_ready
        and estimate_template
        and invoice_template
        and (estimate_template.terms_and_conditions or invoice_template.terms_and_conditions)
    )

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
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "payment_method_count": payment_method_count,
        "logo_ready": logo_ready,
        "contact_ready": contact_ready,
        "email_ready": email_ready,
        "stripe_ready": stripe_ready,
        "estimate_template": estimate_template,
        "invoice_template": invoice_template,
        "document_ready": document_ready,
    })


@role_required("owner")
def storage_diagnostic(request):
    """Diagnostic page to check if file storage (Supabase) is configured correctly."""
    from django.http import JsonResponse
    import os
    from django.core.files.storage import default_storage

    business = _get_business(request)
    result = {
        "storage_backend": default_storage.__class__.__name__,
        "SUPABASE_PROJECT_URL": bool(os.environ.get("SUPABASE_PROJECT_URL", "").strip()),
        "SUPABASE_SERVICE_KEY": bool(os.environ.get("SUPABASE_SERVICE_KEY", "").strip()),
        "SUPABASE_STORAGE_BUCKET": os.environ.get("SUPABASE_STORAGE_BUCKET", "uploads"),
        "BLOB_READ_WRITE_TOKEN": bool(os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()),
        "logo_field": str(business.logo) if business and business.logo else "Not set",
        "logo_url": None,
    }
    if business and business.logo:
        try:
            result["logo_url"] = business.logo.url
        except Exception as e:
            result["logo_url"] = f"Error: {e}"

    # Test write if Supabase is configured
    if result["SUPABASE_PROJECT_URL"] and result["SUPABASE_SERVICE_KEY"]:
        try:
            from django.core.files.base import ContentFile
            test_name = default_storage.save("_diagnostic_test.txt", ContentFile(b"test"))
            result["write_test"] = f"OK — saved as {test_name}"
            default_storage.delete(test_name)
        except Exception as e:
            result["write_test"] = f"FAILED: {e}"
    else:
        result["write_test"] = "Skipped — Supabase not configured"

    return JsonResponse(result, json_dumps_params={"indent": 2})


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
    """Public endpoint to serve the business logo. Tries PNG conversion via PIL,
    falls back to serving the original file directly if PIL fails."""
    from django.http import HttpResponse
    import logging
    logger = logging.getLogger(__name__)

    business = get_object_or_404(Business, id=business_id)
    if not business.logo:
        logger.warning("serve_logo: business %s has no logo", business_id)
        return HttpResponse(status=404)

    import io
    url = None
    raw_bytes = None

    # Step 1: Get the raw image bytes
    try:
        url = business.logo.url
        logger.info("serve_logo: business %s logo url = %s", business_id, url[:100] if url else "None")
    except Exception as e:
        logger.error("serve_logo: error getting url: %s", e)

    if url and url.startswith("http"):
        try:
            import requests as _requests
            resp = _requests.get(url, timeout=15)
            resp.raise_for_status()
            raw_bytes = resp.content
            content_type = resp.headers.get("content-type", "image/png")
            logger.info("serve_logo: downloaded %d bytes, content-type=%s", len(raw_bytes), content_type)
        except Exception as e:
            logger.error("serve_logo: download failed: %s", e)
    else:
        try:
            f = business.logo.open("rb")
            raw_bytes = f.read()
            f.close()
            content_type = "image/png"
            logger.info("serve_logo: read %d bytes from local file", len(raw_bytes))
        except Exception as e:
            logger.error("serve_logo: local file read failed: %s", e)

    if not raw_bytes:
        return HttpResponse(status=404)

    # Step 2: Try to convert to PNG via PIL (handles webp, heic, etc.)
    try:
        from PIL import Image as PILImage
        img_data = io.BytesIO(raw_bytes)
        pil_img = PILImage.open(img_data)
        if pil_img.mode in ("RGBA", "LA", "P"):
            pil_img = pil_img.convert("RGBA")
        else:
            pil_img = pil_img.convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        return HttpResponse(buf.read(), content_type="image/png")
    except Exception as e:
        logger.warning("serve_logo: PIL conversion failed (%s), serving raw", e)

    # Step 3: Fallback — serve the original bytes as-is
    return HttpResponse(raw_bytes, content_type=content_type if content_type else "image/png")

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
    return render(request, "businesses/business_settings.html", {
        "form": form,
        "business": business,
        "next_value": request.GET.get("next", ""),
        "has_2fa": has_2fa,
        "trusted_devices": trusted_devices,
        "stripe_connect_fee_percent": fee_percent,
        "stripe_connect_enabled": stripe_connect_enabled,
    })


@require_POST
@role_required("owner")
def test_gmail_connection(request):
    """Send a test email to verify Gmail (Settings) is configured correctly."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    connection = business.get_smtp_connection()
    if not connection:
        messages.error(
            request,
            "Gmail is not connected. Enter your Gmail address and App Password above and save, then try again.",
        )
        return redirect("business_settings")

    to_email = business.get_from_email() or business.email_smtp_user
    if not to_email:
        messages.error(request, "Set a From address or Gmail address first.")
        return redirect("business_settings")
    # Extract address if it's "Name <email>"
    if isinstance(to_email, str) and "<" in to_email and ">" in to_email:
        to_email = to_email.split("<")[1].split(">")[0].strip()

    try:
        msg = EmailMessage(
            subject="FieldLgx – Gmail test",
            body="This is a test email from FieldLgx. Your Gmail connection is working.",
            from_email=business.get_from_email() or business.email_smtp_user,
            to=[to_email],
            connection=connection,
        )
        msg.send()
        messages.success(request, f"Test email sent to {to_email}. Check your inbox.")
    except Exception as e:
        messages.error(request, f"Could not send test email: {str(e)}. Check your Gmail and App Password.")
    return redirect("business_settings")

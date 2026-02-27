"""
Platform subscription: businesses pay the platform (you) for software access.
Uses Stripe Checkout for subscription and Customer Portal for managing the subscription.
"""
import stripe
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.utils import get_business


def _stripe_enabled():
    return bool(getattr(settings, "STRIPE_SECRET_KEY", None))


def _get_price_id():
    return getattr(settings, "STRIPE_SUBSCRIPTION_PRICE_ID", None) or ""


@role_required("owner")
@require_http_methods(["GET"])
def subscription_status(request):
    """Show current subscription and link to subscribe or manage."""
    business = get_business(request)
    if not business:
        messages.error(request, "No business associated with your account.")
        return redirect("/")
    return render(
        request,
        "subscription/status.html",
        {
            "business": business,
            "stripe_enabled": _stripe_enabled(),
            "has_active_subscription": business.has_active_subscription(),
        },
    )


@role_required("owner")
@require_POST
def create_checkout_session(request):
    """Create Stripe Checkout Session for subscription; redirect to Stripe."""
    if not _stripe_enabled():
        messages.info(request, "Subscription setup is in progress. Please contact support to activate your account.")
        return redirect("subscription:status")
    price_id = _get_price_id()
    if not price_id:
        messages.info(request, "Subscription setup is in progress. Please contact support to activate your account.")
        return redirect("subscription:status")
    business = get_business(request)
    if not business:
        messages.error(request, "No business associated with your account.")
        return redirect("/")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    success_url = request.build_absolute_uri(reverse("subscription:success") + "?session_id={CHECKOUT_SESSION_ID}")
    cancel_url = request.build_absolute_uri(reverse("subscription:status"))
    customer_email = None
    if request.user.email:
        customer_email = request.user.email
    try:
        if business.stripe_customer_id:
            session = stripe.checkout.Session.create(
                customer=business.stripe_customer_id,
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"business_id": str(business.id)},
                subscription_data={"metadata": {"business_id": str(business.id)}},
            )
        else:
            session = stripe.checkout.Session.create(
                customer_email=customer_email or "",
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"business_id": str(business.id)},
                subscription_data={"metadata": {"business_id": str(business.id)}},
            )
        return redirect(session.url)
    except stripe.StripeError as e:
        messages.warning(request, f"Unable to start checkout at this time. Please try again or contact support if the issue persists.")
        return redirect("subscription:status")
    except Exception as e:
        messages.warning(request, "An error occurred while setting up checkout. Please contact support.")
        return redirect("subscription:status")


@role_required("owner")
@require_http_methods(["GET"])
def checkout_success(request):
    """After successful Checkout; session_id is in query. Webhook will set subscription on Business."""
    session_id = request.GET.get("session_id")
    if not session_id:
        return redirect("subscription:status")
    messages.success(request, "Subscription started. You now have full access to Field Ops.")
    return redirect("/")


@role_required("owner")
@require_POST
def create_portal_session(request):
    """Create Stripe Customer Portal session so the owner can manage subscription (cancel, update payment)."""
    if not _stripe_enabled():
        messages.info(request, "Subscription management is not available at this time.")
        return redirect("subscription:status")
    business = get_business(request)
    if not business or not business.stripe_customer_id:
        messages.info(request, "No active subscription found to manage.")
        return redirect("subscription:status")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return_url = request.build_absolute_uri(reverse("subscription:status"))
    try:
        session = stripe.billing_portal.Session.create(
            customer=business.stripe_customer_id,
            return_url=return_url,
        )
        return redirect(session.url)
    except stripe.StripeError as e:
        messages.warning(request, "Unable to open billing portal at this time. Please try again later.")
        return redirect("subscription:status")
    except Exception as e:
        messages.warning(request, "An error occurred. Please contact support if the issue persists.")
        return redirect("subscription:status")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks: subscription and invoice events for platform; account.updated for Connect."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not webhook_secret:
        return HttpResponse("Webhook secret not set", status=500)
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponse("Invalid payload", status=400)
    except stripe.SignatureVerificationError:
        return HttpResponse("Invalid signature", status=400)
    from .handlers import handle_stripe_webhook
    handle_stripe_webhook(event)
    return HttpResponse(status=200)

"""
Platform subscription: businesses pay the platform (you) for software access.
Uses Stripe Checkout for subscription and Customer Portal for managing the subscription.
"""
import hashlib
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
from accounts.models import User


def _stripe_enabled():
    return bool(getattr(settings, "STRIPE_SECRET_KEY", None))


def _get_price_id(plan_tier="core"):
    if plan_tier == "solo":
        return getattr(settings, "STRIPE_SUBSCRIPTION_PRICE_ID_SOLO", None) or ""
    return getattr(settings, "STRIPE_SUBSCRIPTION_PRICE_ID", None) or ""


@role_required("owner")
@require_http_methods(["GET"])
def subscription_status(request):
    """Show current subscription and link to subscribe or manage."""
    business = get_business(request)
    if not business:
        messages.error(request, "No business associated with your account.")
        return redirect("/")
    pricing = {
        "solo_price": getattr(settings, "PLATFORM_SOLO_PRICE", "29.99"),
        "pro_price": getattr(settings, "PLATFORM_PRO_PRICE", "99.99"),
        "crew_soft_cap": getattr(settings, "PLATFORM_CREW_SOFT_CAP", 12),
    }
    crew_user_count = User.objects.filter(business=business, role="crew", is_active=True).count()
    effective_soft_cap = business.crew_soft_cap(pricing["crew_soft_cap"])
    pricing_signal = {
        "crew_user_count": crew_user_count,
        "effective_soft_cap": effective_soft_cap,
        "solo_fit": crew_user_count <= 1,
        "recommend_pro": business.subscription_plan_tier == "solo" and crew_user_count > 1,
    }
    return render(
        request,
        "subscription/status.html",
        {
            "business": business,
            "stripe_enabled": _stripe_enabled(),
            "has_active_subscription": business.has_active_subscription(),
            "pricing": pricing,
            "pricing_signal": pricing_signal,
        },
    )


@role_required("owner")
@require_POST
def create_checkout_session(request):
    """Create Stripe Checkout Session for subscription; redirect to Stripe."""
    if not _stripe_enabled():
        messages.info(request, "Subscription setup is in progress. Please contact support to activate your account.")
        return redirect("subscription:status")
    plan_tier = (request.POST.get("plan_tier") or "core").strip().lower()
    if plan_tier not in {"solo", "core"}:
        plan_tier = "core"
    price_id = _get_price_id(plan_tier)
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
    # Generate idempotency key to prevent duplicate sessions
    idempotency_key = f"subscription:{business.id}:{plan_tier}:{hashlib.md5(f'{business.id}:{price_id}'.encode()).hexdigest()[:16]}"
    
    try:
        # Ensure we have a Stripe customer ID
        if not business.stripe_customer_id:
            # Create Stripe customer if we don't have one
            customer = stripe.Customer.create(
                email=customer_email or "",
                metadata={"business_id": str(business.id)},
            )
            business.stripe_customer_id = customer.id
            business.save(update_fields=["stripe_customer_id"])
        
        # Create checkout session with existing customer
        session = stripe.checkout.Session.create(
            customer=business.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"business_id": str(business.id), "plan_tier": plan_tier},
            subscription_data={"metadata": {"business_id": str(business.id), "plan_tier": plan_tier}},
            idempotency_key=idempotency_key,
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
    """
    Handle Stripe webhooks: subscription and invoice events for platform; account.updated for Connect.
    Implements idempotency by tracking processed events.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    
    # Check for Connect-specific webhook secret, otherwise use platform secret
    # If STRIPE_CONNECT_WEBHOOK_SECRET is set, we can distinguish Connect events
    # For now, we use a single endpoint with platform secret
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not webhook_secret:
        return HttpResponse("Webhook secret not set", status=500)
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponse("Invalid payload", status=400)
    except stripe.SignatureVerificationError:
        return HttpResponse("Invalid signature", status=400)
    
    # Check for idempotency: have we processed this event before?
    from .models import StripeWebhookEvent
    from django.utils import timezone
    
    event_id = event.get("id")
    event_type = event.get("type")
    
    if event_id:
        # Check if we've already processed this event
        webhook_event, created = StripeWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "raw_data": event,
            }
        )
        
        if not created and webhook_event.processed:
            # Already processed, return success
            return HttpResponse(status=200)
        
        # Mark as processing
        webhook_event.event_type = event_type
        webhook_event.raw_data = event
        webhook_event.save()
    
    # Process the event
    try:
        from .handlers import handle_stripe_webhook
        handle_stripe_webhook(event)
        
        # Mark as successfully processed
        if event_id:
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.error_message = ""
            webhook_event.save()
        
        return HttpResponse(status=200)
    except Exception as e:
        # Return non-2xx so Stripe retries transient processing failures.
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing webhook {event_id}: {str(e)}", exc_info=True)

        if event_id:
            webhook_event.processed = False
            webhook_event.error_message = str(e)[:1000]  # Truncate long errors
            webhook_event.save()

        # 500 triggers Stripe retry with exponential backoff.
        return HttpResponse("Webhook processing failed", status=500)

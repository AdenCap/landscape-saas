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


def _stripe_enabled():
    return bool(getattr(settings, "STRIPE_SECRET_KEY", None))


def _get_price_id(tier=None):
    """Get Stripe price ID for the specified tier. Falls back to legacy setting if tier not specified."""
    if tier == "solo":
        return getattr(settings, "STRIPE_SOLO_PRICE_ID", None) or ""
    elif tier == "pro":
        return getattr(settings, "STRIPE_PRO_PRICE_ID", None) or ""
    # Fallback to legacy setting
    return getattr(settings, "STRIPE_SUBSCRIPTION_PRICE_ID", None) or ""


def _get_trial_days(tier):
    """Get trial period in days for the specified tier."""
    if tier == "solo":
        return 7
    elif tier == "pro":
        return 14
    return 0


@role_required("owner")
@require_http_methods(["GET"])
def subscription_status(request):
    """Show current subscription and link to subscribe or manage."""
    business = get_business(request)
    if not business:
        messages.error(request, "No business associated with your account.")
        return redirect("/")
    
    # Get available tiers
    solo_price_id = _get_price_id("solo")
    pro_price_id = _get_price_id("pro")
    
    return render(
        request,
        "subscription/status.html",
        {
            "business": business,
            "stripe_enabled": _stripe_enabled(),
            "has_active_subscription": business.has_active_subscription(),
            "solo_price_id": solo_price_id,
            "pro_price_id": pro_price_id,
            "solo_available": bool(solo_price_id),
            "pro_available": bool(pro_price_id),
        },
    )


@role_required("owner")
@require_POST
def create_checkout_session(request):
    """Create Stripe Checkout Session for subscription; redirect to Stripe."""
    if not _stripe_enabled():
        messages.info(request, "Subscription setup is in progress. Please contact support to activate your account.")
        return redirect("subscription:status")
    
    # Get tier from POST data (solo or pro)
    tier = request.POST.get("tier", "").lower()
    if tier not in ["solo", "pro"]:
        messages.error(request, "Please select a subscription tier.")
        return redirect("subscription:status")
    
    price_id = _get_price_id(tier)
    if not price_id:
        messages.info(request, f"Subscription setup is in progress for the {tier} tier. Please contact support to activate your account.")
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
    
    # Get trial days for this tier
    trial_days = _get_trial_days(tier)
    
    # Generate idempotency key to prevent duplicate sessions
    idempotency_key = f"subscription:{business.id}:{tier}:{hashlib.md5(f'{business.id}:{price_id}:{tier}'.encode()).hexdigest()[:16]}"
    
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
        
        # Build subscription data with trial period if applicable
        subscription_data = {
            "metadata": {
                "business_id": str(business.id),
                "tier": tier,
            }
        }
        if trial_days > 0:
            subscription_data["trial_period_days"] = trial_days
        
        # Create checkout session with existing customer
        session = stripe.checkout.Session.create(
            customer=business.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"business_id": str(business.id), "tier": tier},
            subscription_data=subscription_data,
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
        # Log error but return 200 to Stripe (we don't want retries for bad data)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing webhook {event_id}: {str(e)}", exc_info=True)
        
        if event_id:
            webhook_event.processed = False
            webhook_event.error_message = str(e)[:1000]  # Truncate long errors
            webhook_event.save()
        
        # Return 200 to prevent Stripe from retrying (idempotency handled)
        return HttpResponse(status=200)

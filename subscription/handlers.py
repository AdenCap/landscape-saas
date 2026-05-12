"""Stripe webhook event handlers: subscription (platform), Connect account.updated, invoice payment."""
from django.utils import timezone

from businesses.models import Business


def handle_stripe_webhook(event):
    """Dispatch to the right handler by event type."""
    handlers = {
        "customer.subscription.created": _subscription_updated,
        "customer.subscription.updated": _subscription_updated,
        "customer.subscription.deleted": _subscription_deleted,
        "invoice.paid": _invoice_paid,
        "account.updated": _account_updated,
        "checkout.session.completed": _checkout_session_completed,
    }
    handler = handlers.get(event["type"])
    if handler:
        handler(event)


def _subscription_updated(event):
    """Sync subscription status and period end to Business."""
    sub = event["data"]["object"]
    business_id = (sub.get("metadata") or {}).get("business_id")
    if not business_id:
        return
    try:
        business = Business.objects.get(pk=int(business_id))
    except (Business.DoesNotExist, ValueError):
        return
    business.stripe_subscription_id = sub.get("id", "")
    business.subscription_status = (sub.get("status") or "").lower() or ""
    plan_tier = (sub.get("metadata") or {}).get("plan_tier")
    if plan_tier in {"solo", "core"}:
        business.subscription_plan_tier = plan_tier
    period_end = sub.get("current_period_end")
    if period_end:
        business.subscription_current_period_end = timezone.datetime.fromtimestamp(period_end, tz=timezone.utc)
    else:
        business.subscription_current_period_end = None
    customer_id = sub.get("customer")
    if customer_id:
        business.stripe_customer_id = customer_id
    business.save(update_fields=[
        "stripe_customer_id", "stripe_subscription_id", "subscription_status",
        "subscription_current_period_end", "subscription_plan_tier",
    ])


def _subscription_deleted(event):
    """Clear subscription on Business when canceled."""
    sub = event["data"]["object"]
    business_id = (sub.get("metadata") or {}).get("business_id")
    if not business_id:
        return
    try:
        business = Business.objects.get(pk=int(business_id))
    except (Business.DoesNotExist, ValueError):
        return
    business.stripe_subscription_id = ""
    business.subscription_status = "canceled"
    business.subscription_current_period_end = None
    business.save(update_fields=["stripe_subscription_id", "subscription_status", "subscription_current_period_end"])


def _invoice_paid(event):
    """Optional: when a subscription invoice is paid, ensure customer_id is stored on Business."""
    inv = event["data"]["object"]
    if inv.get("billing_reason") != "subscription_cycle":
        return
    customer_id = inv.get("customer")
    subscription_id = inv.get("subscription")
    if not customer_id or not subscription_id:
        return
    # Find business by subscription and ensure stripe_customer_id is set
    business = Business.objects.filter(stripe_subscription_id=subscription_id).first()
    if business and not business.stripe_customer_id:
        business.stripe_customer_id = customer_id
        business.save(update_fields=["stripe_customer_id"])


def _account_updated(event):
    """Stripe Connect: when connected account is updated, set charges_enabled on Business."""
    acc = event["data"]["object"]
    if acc.get("object") != "account":
        return
    account_id = acc.get("id")
    if not account_id:
        return
    business = Business.objects.filter(stripe_connect_account_id=account_id).first()
    if not business:
        return
    business.stripe_connect_charges_enabled = bool(acc.get("charges_enabled"))
    business.save(update_fields=["stripe_connect_charges_enabled"])


def _checkout_session_completed(event):
    """
    When a Connect invoice payment completes, mark the invoice as paid.
    Extracts and stores payment intent and charge IDs for tracking.
    """
    session = event["data"]["object"]
    if session.get("mode") != "payment":
        return  # Only handle payment mode, not subscription mode
    
    metadata = session.get("metadata") or {}
    estimate_id = metadata.get("estimate_id")
    if estimate_id:
        _estimate_deposit_checkout_completed(event, session, estimate_id)
        return

    invoice_id = metadata.get("invoice_id")
    if not invoice_id:
        return
    payment_status = session.get("payment_status")
    if payment_status and payment_status != "paid":
        return
    
    from billing.models import Invoice
    try:
        invoice = Invoice.objects.get(pk=int(invoice_id))
    except (Invoice.DoesNotExist, ValueError, TypeError):
        return
    
    # Extract payment intent ID from session
    payment_intent_id = session.get("payment_intent")
    charge_id = ""
    if payment_intent_id:
        # Try to get charge ID from payment intent (if available)
        # Note: For Connect accounts, we may need to fetch this separately
        # For now, we'll store what we have from the session
        try:
            import stripe
            from django.conf import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Check if this is a connected account payment
            account_id = event.get("account")  # Connected account ID if present
            if account_id:
                # Fetch payment intent from connected account
                pi = stripe.PaymentIntent.retrieve(
                    payment_intent_id,
                    stripe_account=account_id
                )
            else:
                # Platform payment intent
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            latest_charge = pi.get("latest_charge")
            if latest_charge:
                charge_id = latest_charge if isinstance(latest_charge, str) else latest_charge.get("id", "")
            if not charge_id:
                charges = pi.get("charges", {}).get("data", [])
                if charges and len(charges) > 0:
                    charge_id = charges[0].get("id", "")
        except Exception:
            # If we can't fetch payment intent details, continue anyway
            # The payment intent ID is already stored
            pass

    amount_total = session.get("amount_total")
    amount = None
    if amount_total is not None:
        try:
            from decimal import Decimal
            amount = (Decimal(str(amount_total)) / Decimal("100")).quantize(Decimal("0.01"))
        except Exception:
            amount = None

    from billing.services import mark_invoice_paid_from_stripe
    mark_invoice_paid_from_stripe(
        invoice,
        checkout_session_id=session.get("id", ""),
        payment_intent_id=payment_intent_id or "",
        charge_id=charge_id,
        amount=amount,
        source="stripe_webhook",
    )


def _estimate_deposit_checkout_completed(event, session, estimate_id):
    """When an estimate deposit Checkout Session completes, mark the deposit paid."""
    from billing.models import Estimate

    try:
        estimate = Estimate.objects.get(pk=int(estimate_id))
    except (Estimate.DoesNotExist, ValueError, TypeError):
        return

    payment_intent_id = session.get("payment_intent") or ""
    charge_id = ""
    if payment_intent_id:
        try:
            import stripe
            from django.conf import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            account_id = event.get("account")
            if account_id:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id, stripe_account=account_id)
            else:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            charges = pi.get("charges", {}).get("data", [])
            if charges:
                charge_id = charges[0].get("id", "")
        except Exception:
            pass

    estimate.deposit_paid = True
    estimate.deposit_paid_at = timezone.now()
    estimate.stripe_deposit_checkout_session_id = session.get("id", "")
    estimate.stripe_deposit_payment_intent_id = payment_intent_id
    estimate.stripe_deposit_charge_id = charge_id
    estimate.save(update_fields=[
        "deposit_paid",
        "deposit_paid_at",
        "stripe_deposit_checkout_session_id",
        "stripe_deposit_payment_intent_id",
        "stripe_deposit_charge_id",
    ])

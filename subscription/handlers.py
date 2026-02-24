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
        "subscription_current_period_end",
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
    """When a Connect invoice payment completes, mark the invoice as paid."""
    session = event["data"]["object"]
    if session.get("mode") != "payment":
        return
    metadata = session.get("metadata") or {}
    invoice_id = metadata.get("invoice_id")
    if not invoice_id:
        return
    from billing.models import Invoice
    try:
        invoice = Invoice.objects.get(pk=int(invoice_id))
    except (Invoice.DoesNotExist, ValueError, TypeError):
        return
    if invoice.status != "sent":
        return
    invoice.status = "paid"
    invoice.save(update_fields=["status"])

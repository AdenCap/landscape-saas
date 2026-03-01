"""
Stripe webhook event handlers: subscription (platform), Connect account.updated, invoice payment.

This module handles both regular webhook events and V2 thin events for Stripe Connect accounts.
"""
import logging
from django.utils import timezone
from django.conf import settings

from businesses.models import Business
from stripe_connect.models import ConnectedAccountSubscription

logger = logging.getLogger(__name__)


def handle_stripe_webhook(event):
    """
    Dispatch to the right handler by event type.
    
    Supports both regular events and V2 thin events.
    For thin events, we need to fetch the full event data first.
    
    Note: When using thin events, you need to configure your webhook endpoint
    in Stripe Dashboard to send "Thin" payloads and listen for V2 events.
    """
    event_type = event.get("type", "")
    event_id = event.get("id")
    
    # Check if this is a thin event (V2 events)
    # Thin events have a different structure and need to be expanded
    # Thin events typically have minimal data and need to be fetched
    if event_type.startswith("v2.") or (event_id and event.get("object") == "event" and not event.get("data")):
        # This is a V2 thin event - fetch the full event data
        try:
            import stripe
            from stripe import StripeClient
            
            stripe_secret_key = getattr(settings, "STRIPE_SECRET_KEY", None)
            if not stripe_secret_key:
                logger.error("STRIPE_SECRET_KEY not set, cannot process V2 thin event")
                return
            
            stripe_client = StripeClient(stripe_secret_key)
            
            # Fetch the full event data using the event ID
            if event_id:
                full_event = stripe_client.v2.core.events.retrieve(event_id)
                event_type = full_event.get("type", event_type)
                event = full_event
            else:
                logger.warning("V2 thin event missing event ID, cannot fetch full event")
                return
        except Exception as e:
            logger.error(f"Error fetching full V2 event: {e}", exc_info=True)
            return
    
    # Handle subscription events first - need to check if it's platform or connected account
    if event_type in ["customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"]:
        # Check if this is for a connected account (customer_account field exists in V2)
        sub_data = event.get("data", {}).get("object", {})
        customer_account = sub_data.get("customer_account")
        if customer_account:
            # This is a connected account subscription event
            if event_type == "customer.subscription.created":
                _connect_subscription_created(event)
            elif event_type == "customer.subscription.updated":
                _connect_subscription_updated(event)
            elif event_type == "customer.subscription.deleted":
                _connect_subscription_deleted(event)
        else:
            # This is a platform subscription event - use existing handler
            if event_type == "customer.subscription.created":
                _subscription_updated(event)
            elif event_type == "customer.subscription.updated":
                _subscription_updated(event)
            elif event_type == "customer.subscription.deleted":
                _subscription_deleted(event)
        return
    
    # Map other event types to handlers
    handlers = {
        "invoice.paid": _invoice_paid,
        
        # Connect account events (V1)
        "account.updated": _account_updated,
        
        # Connect account events (V2 thin events)
        "v2.core.account[requirements].updated": _v2_account_requirements_updated,
        "v2.core.account[configuration.merchant].capability_status_updated": _v2_merchant_capability_updated,
        "v2.core.account[configuration.customer].capability_status_updated": _v2_customer_capability_updated,
        "v2.core.account[.recipient].capability_status_updated": _v2_recipient_capability_updated,
        
        # Checkout events
        "checkout.session.completed": _checkout_session_completed,
        
        # Payment method events
        "payment_method.attached": _payment_method_attached,
        "payment_method.detached": _payment_method_detached,
        
        # Customer events
        "customer.updated": _customer_updated,
        
        # Tax ID events
        "customer.tax_id.created": _customer_tax_id_created,
        "customer.tax_id.deleted": _customer_tax_id_deleted,
        "customer.tax_id.updated": _customer_tax_id_updated,
        
        # Billing portal events
        "billing_portal.configuration.created": _billing_portal_config_created,
        "billing_portal.configuration.updated": _billing_portal_config_updated,
        "billing_portal.session.created": _billing_portal_session_created,
    }
    
    handler = handlers.get(event_type)
    if handler:
        handler(event)
    else:
        logger.debug(f"No handler for event type: {event_type}")


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
    """Stripe Connect V1: when connected account is updated, set charges_enabled on Business."""
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


def _v2_account_requirements_updated(event):
    """
    V2 thin event: Account requirements updated.
    
    This event is sent when account requirements change (e.g., new information needed).
    You should check the requirements and prompt the user to complete them if needed.
    """
    # For thin events, the account ID is in the event object
    account_id = event.get("account")
    if not account_id:
        return
    
    # TODO: In production, you might want to:
    # 1. Fetch the account to get current requirements status
    # 2. Notify the business owner if action is needed
    # 3. Update the business record with requirements status
    logger.info(f"V2 account requirements updated for account: {account_id}")


def _v2_merchant_capability_updated(event):
    """
    V2 thin event: Merchant capability status updated.
    
    This event is sent when the merchant capability (card_payments, etc.) status changes.
    """
    account_id = event.get("account")
    if not account_id:
        return
    
    business = Business.objects.filter(stripe_connect_account_id=account_id).first()
    if not business:
        return
    
    # Check if card payments are now active
    # The event data structure may vary, so we'll fetch the account to be sure
    try:
        import stripe
        from stripe import StripeClient
        
        stripe_secret_key = getattr(settings, "STRIPE_SECRET_KEY", None)
        if stripe_secret_key:
            stripe_client = StripeClient(stripe_secret_key)
            account = stripe_client.v2.core.accounts.retrieve(
                account_id,
                include=["configuration.merchant"]
            )
            
            merchant_config = account.get("configuration", {}).get("merchant", {})
            capabilities = merchant_config.get("capabilities", {})
            card_payments = capabilities.get("card_payments", {})
            status = card_payments.get("status")
            
            # Update business if card payments are active
            if status == "active":
                business.stripe_connect_charges_enabled = True
                business.save(update_fields=["stripe_connect_charges_enabled"])
    except Exception as e:
        logger.error(f"Error processing merchant capability update: {e}", exc_info=True)


def _v2_customer_capability_updated(event):
    """V2 thin event: Customer capability status updated."""
    account_id = event.get("account")
    if not account_id:
        return
    logger.info(f"V2 customer capability updated for account: {account_id}")


def _v2_recipient_capability_updated(event):
    """V2 thin event: Recipient capability status updated."""
    account_id = event.get("account")
    if not account_id:
        return
    logger.info(f"V2 recipient capability updated for account: {account_id}")


def _connect_subscription_created(event):
    """
    Connected account subscription created.
    
    When a connected account subscribes to your platform, store the subscription.
    """
    sub = event["data"]["object"]
    subscription_id = sub.get("id")
    customer_account = sub.get("customer_account")  # V2: use customer_account, not customer
    
    if not subscription_id or not customer_account:
        return
    
    # Find business by connected account ID
    business = Business.objects.filter(stripe_connect_account_id=customer_account).first()
    if not business:
        return
    
    # Create or update subscription record
    subscription, created = ConnectedAccountSubscription.objects.update_or_create(
        stripe_subscription_id=subscription_id,
        defaults={
            "business": business,
            "status": sub.get("status", "active"),
            "current_period_end": timezone.datetime.fromtimestamp(
                sub.get("current_period_end", 0), tz=timezone.utc
            ) if sub.get("current_period_end") else None,
        }
    )
    
    logger.info(f"Connected account subscription {'created' if created else 'updated'}: {subscription_id}")


def _connect_subscription_updated(event):
    """
    Connected account subscription updated.
    
    Handle subscription upgrades, downgrades, quantity changes, pauses, etc.
    """
    sub = event["data"]["object"]
    subscription_id = sub.get("id")
    customer_account = sub.get("customer_account")
    
    if not subscription_id:
        return
    
    subscription = ConnectedAccountSubscription.objects.filter(
        stripe_subscription_id=subscription_id
    ).first()
    
    if not subscription:
        # If subscription doesn't exist, try to create it
        if customer_account:
            business = Business.objects.filter(stripe_connect_account_id=customer_account).first()
            if business:
                subscription = ConnectedAccountSubscription.objects.create(
                    business=business,
                    stripe_subscription_id=subscription_id,
                    status=sub.get("status", "active"),
                    current_period_end=timezone.datetime.fromtimestamp(
                        sub.get("current_period_end", 0), tz=timezone.utc
                    ) if sub.get("current_period_end") else None,
                )
        return
    
    # Update subscription status
    subscription.status = sub.get("status", subscription.status)
    if sub.get("current_period_end"):
        subscription.current_period_end = timezone.datetime.fromtimestamp(
            sub.get("current_period_end"), tz=timezone.utc
        )
    subscription.save()
    
    # TODO: In production, you should:
    # 1. Check subscription.items.data[0].price for upgrades/downgrades
    # 2. Check subscription.items.data[0].quantity for quantity changes
    # 3. Check subscription.pause_collection for paused subscriptions
    # 4. Grant or revoke access based on subscription status
    
    logger.info(f"Connected account subscription updated: {subscription_id}")


def _connect_subscription_deleted(event):
    """Connected account subscription deleted (canceled)."""
    sub = event["data"]["object"]
    subscription_id = sub.get("id")
    
    if not subscription_id:
        return
    
    subscription = ConnectedAccountSubscription.objects.filter(
        stripe_subscription_id=subscription_id
    ).first()
    
    if subscription:
        subscription.status = "canceled"
        subscription.save()
        # TODO: Revoke access to platform features
    
    logger.info(f"Connected account subscription deleted: {subscription_id}")


def _payment_method_attached(event):
    """Payment method attached to customer."""
    # TODO: Update customer payment method information if needed
    logger.debug("Payment method attached")


def _payment_method_detached(event):
    """Payment method detached from customer."""
    # TODO: Update customer payment method information if needed
    logger.debug("Payment method detached")


def _customer_updated(event):
    """
    Customer updated.
    
    Check invoice_settings.default_payment_method for new default payment method.
    All updates must be treated as billing information changes only.
    """
    # TODO: Update customer billing information
    # NOTE: Do not use customer billing email as a login credential
    logger.debug("Customer updated")


def _customer_tax_id_created(event):
    """Customer tax ID created."""
    # TODO: Handle tax ID creation if needed
    logger.debug("Customer tax ID created")


def _customer_tax_id_deleted(event):
    """Customer tax ID deleted."""
    # TODO: Handle tax ID deletion if needed
    logger.debug("Customer tax ID deleted")


def _customer_tax_id_updated(event):
    """Customer tax ID updated (validation status)."""
    # TODO: Handle tax ID validation updates if needed
    logger.debug("Customer tax ID updated")


def _billing_portal_config_created(event):
    """Billing portal configuration created."""
    logger.debug("Billing portal configuration created")


def _billing_portal_config_updated(event):
    """Billing portal configuration updated."""
    logger.debug("Billing portal configuration updated")


def _billing_portal_session_created(event):
    """Billing portal session created."""
    logger.debug("Billing portal session created")


def _checkout_session_completed(event):
    """
    When a Connect invoice payment completes, mark the invoice as paid.
    Extracts and stores payment intent and charge IDs for tracking.
    """
    session = event["data"]["object"]
    if session.get("mode") != "payment":
        return  # Only handle payment mode, not subscription mode
    
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
        return  # Only update if invoice is in "sent" status
    
    # Extract payment intent ID from session
    payment_intent_id = session.get("payment_intent")
    if payment_intent_id:
        invoice.stripe_payment_intent_id = payment_intent_id
        
        # Try to get charge ID from payment intent (if available)
        # Note: For Connect accounts, we may need to fetch this separately
        try:
            from stripe import StripeClient
            
            stripe_secret_key = getattr(settings, "STRIPE_SECRET_KEY", None)
            if not stripe_secret_key:
                logger.warning("STRIPE_SECRET_KEY not set, cannot fetch payment intent details")
            else:
                stripe_client = StripeClient(stripe_secret_key)
                
                # Check if this is a connected account payment
                account_id = event.get("account")  # Connected account ID if present
                if account_id:
                    # Fetch payment intent from connected account
                    pi = stripe_client.payment_intents.retrieve(
                        payment_intent_id,
                        stripe_account=account_id
                    )
                else:
                    # Platform payment intent
                    pi = stripe_client.payment_intents.retrieve(payment_intent_id)
                
                # Get the charge ID from the payment intent
                charges = pi.get("charges", {}).get("data", [])
                if charges and len(charges) > 0:
                    invoice.stripe_charge_id = charges[0].get("id", "")
        except Exception as e:
            # If we can't fetch payment intent details, continue anyway
            # The payment intent ID is already stored
            logger.debug(f"Could not fetch payment intent details: {e}")
    
    # Update invoice status and store Stripe IDs
    invoice.status = "paid"
    invoice.stripe_checkout_session_id = session.get("id", "")
    invoice.save(update_fields=[
        "status",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "stripe_charge_id",
    ])

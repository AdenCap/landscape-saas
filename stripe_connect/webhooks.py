"""
Webhook handlers for Stripe Connect V2 events.

This module handles:
- V2 account requirements updates (thin events)
- V2 account capability status updates (thin events)
- Subscription lifecycle events
- Payment method events
- Customer events
- Billing portal events
"""
import json
from django.utils import timezone
from django.conf import settings

try:
    import stripe
except ImportError:
    stripe = None

from .models import ConnectedAccount, ConnectedSubscription, ConnectWebhookEvent


def handle_thin_event(thin_event, stripe_client):
    """
    Handle a thin webhook event.
    
    Thin events contain minimal data and require fetching the full event
    to get all details. This is used for V2 account events.
    
    Args:
        thin_event: Parsed thin event object
        stripe_client: Stripe client instance
    
    Returns:
        bool: True if event was processed successfully
    """
    if not stripe_client:
        return False
    
    # Check if we've already processed this event (idempotency)
    event_id = thin_event.id
    webhook_event, created = ConnectWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': thin_event.type,
            'processed': False,
        }
    )
    
    if not created and webhook_event.processed:
        # Already processed, skip
        return True
    
    try:
        # Fetch the full event to get all details
        event = stripe_client.v2.core.events.retrieve(thin_event.id)
        
        # Handle based on event type
        event_type = event.type
        
        if event_type == 'v2.core.account[requirements].updated':
            handle_account_requirements_updated(event, stripe_client)
        elif event_type == 'v2.core.account[configuration.merchant].capability_status_updated':
            handle_merchant_capability_updated(event, stripe_client)
        elif event_type == 'v2.core.account[configuration.customer].capability_status_updated':
            handle_customer_capability_updated(event, stripe_client)
        else:
            # Unknown event type, log it
            print(f"Unknown thin event type: {event_type}")
            return False
        
        # Mark as processed
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
        return True
        
    except Exception as e:
        print(f"Error processing thin event {event_id}: {str(e)}")
        return False


def handle_account_requirements_updated(event, stripe_client):
    """
    Handle v2.core.account[requirements].updated event.
    
    This event is sent when account requirements change (e.g., new documents needed).
    We should notify the business owner or update the account status.
    
    Args:
        event: Full Stripe event object
        stripe_client: Stripe client instance
    """
    account_id = event.data.object.id
    
    try:
        connected_account = ConnectedAccount.objects.get(account_id=account_id)
        
        # Fetch updated account to get latest requirements
        account = stripe_client.v2.core.accounts.retrieve(
            account_id,
            include=["requirements"],
        )
        
        # Check requirements status
        if account.requirements and account.requirements.summary:
            requirements_status = account.requirements.summary.minimum_deadline.status
            
            # TODO: Store requirements status in database
            # TODO: Send notification to business owner if requirements are due
            # For now, we just log it
            print(f"Account {account_id} requirements status: {requirements_status}")
        
    except ConnectedAccount.DoesNotExist:
        print(f"Connected account not found for account_id: {account_id}")
    except Exception as e:
        print(f"Error handling requirements update: {str(e)}")


def handle_merchant_capability_updated(event, stripe_client):
    """
    Handle v2.core.account[configuration.merchant].capability_status_updated event.
    
    This event is sent when merchant capabilities (like card_payments) change status.
    
    Args:
        event: Full Stripe event object
        stripe_client: Stripe client instance
    """
    account_id = event.data.object.id
    
    try:
        connected_account = ConnectedAccount.objects.get(account_id=account_id)
        
        # Fetch updated account to get latest capability status
        account = stripe_client.v2.core.accounts.retrieve(
            account_id,
            include=["configuration.merchant"],
        )
        
        # Check card payments capability status
        if account.configuration and account.configuration.merchant:
            card_payments_status = account.configuration.merchant.capabilities.card_payments.status
            
            # TODO: Update database with capability status
            # TODO: Notify business owner if capability becomes active
            print(f"Account {account_id} card_payments capability: {card_payments_status}")
        
    except ConnectedAccount.DoesNotExist:
        print(f"Connected account not found for account_id: {account_id}")
    except Exception as e:
        print(f"Error handling merchant capability update: {str(e)}")


def handle_customer_capability_updated(event, stripe_client):
    """
    Handle v2.core.account[configuration.customer].capability_status_updated event.
    
    This event is sent when customer capabilities change status.
    
    Args:
        event: Full Stripe event object
        stripe_client: Stripe client instance
    """
    account_id = event.data.object.id
    
    try:
        connected_account = ConnectedAccount.objects.get(account_id=account_id)
        
        # TODO: Handle customer capability updates
        # This might affect subscription functionality
        print(f"Account {account_id} customer capability updated")
        
    except ConnectedAccount.DoesNotExist:
        print(f"Connected account not found for account_id: {account_id}")
    except Exception as e:
        print(f"Error handling customer capability update: {str(e)}")


def handle_subscription_event(event, stripe_client):
    """
    Handle subscription-related events.
    
    Events handled:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    
    Args:
        event: Stripe event object
        stripe_client: Stripe client instance
    """
    event_id = event.id
    event_type = event.type
    
    # Check idempotency
    webhook_event, created = ConnectWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': event_type,
            'processed': False,
        }
    )
    
    if not created and webhook_event.processed:
        return True
    
    try:
        subscription = event.data.object
        
        # For V2 accounts, use customer_account instead of customer
        # The customer_account is the connected account ID (acct_xxx)
        account_id = subscription.customer_account
        
        if not account_id:
            print(f"No customer_account found in subscription event {event_id}")
            return False
        
        try:
            connected_account = ConnectedAccount.objects.get(account_id=account_id)
        except ConnectedAccount.DoesNotExist:
            print(f"Connected account not found for account_id: {account_id}")
            return False
        
        if event_type == 'customer.subscription.created':
            handle_subscription_created(subscription, connected_account)
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(subscription, connected_account)
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(subscription, connected_account)
        
        # Mark as processed
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
        return True
        
    except Exception as e:
        print(f"Error processing subscription event {event_id}: {str(e)}")
        return False


def handle_subscription_created(subscription, connected_account):
    """
    Handle subscription creation.
    
    Store subscription information in database.
    
    Args:
        subscription: Stripe subscription object
        connected_account: ConnectedAccount instance
    """
    # Get price ID from subscription items
    price_id = None
    if subscription.items and subscription.items.data:
        price_id = subscription.items.data[0].price.id
    
    ConnectedSubscription.objects.update_or_create(
        stripe_subscription_id=subscription.id,
        defaults={
            'connected_account': connected_account,
            'status': subscription.status,
            'price_id': price_id or '',
            'current_period_start': timezone.datetime.fromtimestamp(
                subscription.current_period_start,
                tz=timezone.utc
            ) if subscription.current_period_start else None,
            'current_period_end': timezone.datetime.fromtimestamp(
                subscription.current_period_end,
                tz=timezone.utc
            ) if subscription.current_period_end else None,
            'cancel_at_period_end': subscription.cancel_at_period_end or False,
        }
    )
    
    print(f"Subscription {subscription.id} created for account {connected_account.account_id}")


def handle_subscription_updated(subscription, connected_account):
    """
    Handle subscription updates.
    
    Updates subscription status, price, quantity, cancellation status, etc.
    
    Args:
        subscription: Stripe subscription object
        connected_account: ConnectedAccount instance
    """
    # Get price ID from subscription items
    price_id = None
    if subscription.items and subscription.items.data:
        price_id = subscription.items.data[0].price.id
    
    # Check for upgrades/downgrades
    # Check for quantity changes
    # Check for cancellation/reactivation
    
    ConnectedSubscription.objects.update_or_create(
        stripe_subscription_id=subscription.id,
        defaults={
            'connected_account': connected_account,
            'status': subscription.status,
            'price_id': price_id or '',
            'current_period_start': timezone.datetime.fromtimestamp(
                subscription.current_period_start,
                tz=timezone.utc
            ) if subscription.current_period_start else None,
            'current_period_end': timezone.datetime.fromtimestamp(
                subscription.current_period_end,
                tz=timezone.utc
            ) if subscription.current_period_end else None,
            'cancel_at_period_end': subscription.cancel_at_period_end or False,
        }
    )
    
    # TODO: Grant/revoke access based on subscription status
    # TODO: Handle trial ending when switching prices
    # TODO: Handle paused collections
    
    print(f"Subscription {subscription.id} updated for account {connected_account.account_id}")


def handle_subscription_deleted(subscription, connected_account):
    """
    Handle subscription cancellation/deletion.
    
    Revoke access to products/services.
    
    Args:
        subscription: Stripe subscription object
        connected_account: ConnectedAccount instance
    """
    try:
        db_subscription = ConnectedSubscription.objects.get(
            stripe_subscription_id=subscription.id
        )
        db_subscription.status = 'canceled'
        db_subscription.save()
        
        # TODO: Revoke access to products/services
        print(f"Subscription {subscription.id} canceled for account {connected_account.account_id}")
        
    except ConnectedSubscription.DoesNotExist:
        print(f"Subscription {subscription.id} not found in database")


def handle_payment_method_event(event, stripe_client):
    """
    Handle payment method events.
    
    Events:
    - payment_method.attached
    - payment_method.detached
    
    Args:
        event: Stripe event object
        stripe_client: Stripe client instance
    """
    event_id = event.id
    
    # Check idempotency
    webhook_event, created = ConnectWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': event.type,
            'processed': False,
        }
    )
    
    if not created and webhook_event.processed:
        return True
    
    # TODO: Handle payment method attachment/detachment
    # This might be useful for tracking payment methods on connected accounts
    
    webhook_event.processed = True
    webhook_event.processed_at = timezone.now()
    webhook_event.save()
    
    return True


def handle_customer_event(event, stripe_client):
    """
    Handle customer events.
    
    Events:
    - customer.updated
    - customer.tax_id.created
    - customer.tax_id.updated
    - customer.tax_id.deleted
    
    Args:
        event: Stripe event object
        stripe_client: Stripe client instance
    """
    event_id = event.id
    
    # Check idempotency
    webhook_event, created = ConnectWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': event.type,
            'processed': False,
        }
    )
    
    if not created and webhook_event.processed:
        return True
    
    # TODO: Handle customer updates
    # For V2 accounts, customer updates might affect billing information
    # Don't use customer email as login credential
    
    webhook_event.processed = True
    webhook_event.processed_at = timezone.now()
    webhook_event.save()
    
    return True


def handle_billing_portal_event(event, stripe_client):
    """
    Handle billing portal events.
    
    Events:
    - billing_portal.configuration.created
    - billing_portal.configuration.updated
    - billing_portal.session.created
    
    Args:
        event: Stripe event object
        stripe_client: Stripe client instance
    """
    event_id = event.id
    
    # Check idempotency
    webhook_event, created = ConnectWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': event.type,
            'processed': False,
        }
    )
    
    if not created and webhook_event.processed:
        return True
    
    # TODO: Handle billing portal events
    # These might be useful for tracking portal usage
    
    webhook_event.processed = True
    webhook_event.processed_at = timezone.now()
    webhook_event.save()
    
    return True

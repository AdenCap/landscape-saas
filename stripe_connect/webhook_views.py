"""
Webhook endpoint for Stripe Connect V2 events.

This endpoint handles both thin events (for V2 accounts) and regular events
(for subscriptions and other operations).
"""
import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

try:
    import stripe
except ImportError:
    stripe = None

from .webhooks import (
    handle_thin_event,
    handle_subscription_event,
    handle_payment_method_event,
    handle_customer_event,
    handle_billing_portal_event,
)


@csrf_exempt
@require_POST
def stripe_connect_webhook(request):
    """
    Handle Stripe Connect webhook events.
    
    Supports both thin events (for V2 accounts) and regular events
    (for subscriptions, payment methods, etc.).
    
    Configure this endpoint in Stripe Dashboard:
    - URL: https://yourdomain.com/webhooks/stripe-connect/
    - Events: See webhook configuration in README
    
    For local testing, use Stripe CLI:
    stripe listen --thin-events 'v2.core.account[requirements].updated,...' --forward-thin-to http://localhost:8000/webhooks/stripe-connect/
    """
    if not stripe:
        return JsonResponse({'error': 'Stripe SDK not installed'}, status=500)
    
    # Get webhook secret from settings
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    if not webhook_secret:
        return JsonResponse({'error': 'STRIPE_WEBHOOK_SECRET not configured'}, status=500)
    
    # Get signature from headers
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    payload = request.body
    
    # Create Stripe client
    secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not secret_key:
        return JsonResponse({'error': 'STRIPE_SECRET_KEY not configured'}, status=500)
    
    stripe_client = stripe.StripeClient(secret_key)
    
    try:
        # Try to parse as thin event first (for V2 account events)
        try:
            thin_event = stripe_client.parse_thin_event(payload, sig_header, webhook_secret)
            
            # Handle thin event
            success = handle_thin_event(thin_event, stripe_client)
            
            if success:
                return HttpResponse(status=200)
            else:
                return JsonResponse({'error': 'Failed to process thin event'}, status=400)
                
        except ValueError:
            # Not a thin event, try parsing as regular event
            pass
        
        # Parse as regular event
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        
        event_type = event.type
        
        # Route to appropriate handler
        if event_type.startswith('customer.subscription.'):
            success = handle_subscription_event(event, stripe_client)
        elif event_type.startswith('payment_method.'):
            success = handle_payment_method_event(event, stripe_client)
        elif event_type.startswith('customer.'):
            success = handle_customer_event(event, stripe_client)
        elif event_type.startswith('billing_portal.'):
            success = handle_billing_portal_event(event, stripe_client)
        else:
            # Unknown event type, log but don't fail
            print(f"Unknown event type: {event_type}")
            success = True
        
        if success:
            return HttpResponse(status=200)
        else:
            return JsonResponse({'error': 'Failed to process event'}, status=400)
            
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        # Return 200 to prevent Stripe from retrying (idempotency handled)
        return HttpResponse(status=200)

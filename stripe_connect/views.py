"""
Stripe Connect V2 integration views.

This module handles:
- Connected account onboarding
- Product creation and management
- Storefront for customers
- Checkout with application fees
- Subscription management
"""
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from accounts.decorators import role_required
from accounts.utils import get_business
from businesses.models import Business

# Import Stripe SDK
# NOTE: Make sure stripe package is installed: pip install stripe
try:
    import stripe
except ImportError:
    stripe = None
    # If stripe is not installed, we'll handle this in the views

from .models import ConnectedAccount, ConnectedProduct, ConnectedSubscription


def _get_stripe_client():
    """
    Create and return a Stripe client instance.
    
    Uses STRIPE_SECRET_KEY from settings. If not set, returns None
    and views will show appropriate error messages.
    
    Returns:
        stripe.StripeClient or None: Stripe client instance
    """
    if not stripe:
        return None
    
    secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not secret_key:
        return None
    
    # Create Stripe client using the secret key
    # The SDK will automatically use the latest API version (2026-02-25.clover)
    return stripe.StripeClient(secret_key)


def _check_stripe_configured():
    """
    Check if Stripe is properly configured.
    
    Returns:
        tuple: (is_configured: bool, error_message: str or None)
    """
    if not stripe:
        return False, "Stripe SDK is not installed. Please install it: pip install stripe"
    
    secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not secret_key:
        return False, "STRIPE_SECRET_KEY is not configured. Please set it in your .env file."
    
    return True, None


# ============================================================================
# CONNECTED ACCOUNT ONBOARDING
# ============================================================================

@role_required("owner")
def connect_onboard(request):
    """
    Onboard a business to Stripe Connect V2.
    
    Creates a V2 connected account if one doesn't exist,
    then creates an account link for onboarding.
    
    Flow:
    1. Check if business already has a connected account
    2. If not, create a V2 account with required properties
    3. Create account link for onboarding
    4. Redirect user to Stripe onboarding page
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect('dashboard')
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    stripe_client = _get_stripe_client()
    
    try:
        # Check if business already has a connected account
        connected_account = None
        try:
            connected_account = ConnectedAccount.objects.get(business=business)
            account_id = connected_account.account_id
        except ConnectedAccount.DoesNotExist:
            # Create a new V2 connected account
            # NOTE: Get these values from the user (form or request)
            # For this demo, we'll use business information
            display_name = business.name or "Business Account"
            contact_email = business.contact_email or request.user.email
            
            # Create V2 account with required properties
            # IMPORTANT: Do NOT use top-level 'type' parameter
            # Use the V2 API structure as specified
            account = stripe_client.v2.core.accounts.create(
                display_name=display_name,
                contact_email=contact_email,
                identity={
                    'country': 'us',  # TODO: Get from user or business settings
                },
                dashboard='full',
                defaults={
                    'responsibilities': {
                        'fees_collector': 'stripe',
                        'losses_collector': 'stripe',
                    },
                },
                configuration={
                    'customer': {},
                    'merchant': {
                        'capabilities': {
                            'card_payments': {
                                'requested': True,
                            },
                        },
                    },
                },
            )
            
            account_id = account.id
            
            # Store the mapping from business to account ID
            connected_account = ConnectedAccount.objects.create(
                business=business,
                account_id=account_id,
                display_name=display_name,
                contact_email=contact_email,
            )
        
        # Create account link for onboarding
        # Get the base URL for redirect URLs
        # TODO: Replace with your actual domain in production
        base_url = request.build_absolute_uri('/').rstrip('/')
        
        account_link = stripe_client.v2.core.account_links.create(
            account=account_id,
            use_case={
                'type': 'account_onboarding',
                'account_onboarding': {
                    'configurations': ['merchant', 'customer'],
                    'refresh_url': f'{base_url}/stripe-connect/onboard/',
                    'return_url': f'{base_url}/stripe-connect/onboard/return/?account_id={account_id}',
                },
            },
        )
        
        # Redirect to Stripe onboarding
        return redirect(account_link.url)
        
    except stripe.error.StripeError as e:
        messages.error(request, f"Stripe error: {e.user_message or str(e)}")
        return redirect('stripe_connect:dashboard')
    except Exception as e:
        messages.error(request, f"Error during onboarding: {str(e)}")
        return redirect('stripe_connect:dashboard')


@role_required("owner")
def connect_onboard_return(request):
    """
    Handle return from Stripe onboarding.
    
    User is redirected here after completing onboarding.
    We check the account status to see if onboarding is complete.
    """
    account_id = request.GET.get('account_id')
    if not account_id:
        messages.error(request, "Missing account ID.")
        return redirect('stripe_connect:dashboard')
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    # Verify this account belongs to the business
    try:
        connected_account = ConnectedAccount.objects.get(
            business=business,
            account_id=account_id
        )
    except ConnectedAccount.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('stripe_connect:dashboard')
    
    messages.success(request, "Onboarding completed! Check your account status below.")
    return redirect('stripe_connect:dashboard')


@role_required("owner")
def connect_dashboard(request):
    """
    Dashboard showing connected account status and onboarding button.
    
    Fetches account status directly from Stripe API (not from database)
    to get real-time information about onboarding status.
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        return render(request, 'stripe_connect/dashboard.html', {
            'error': error_msg,
            'stripe_configured': False,
        })
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    stripe_client = _get_stripe_client()
    
    # Check if business has a connected account
    try:
        connected_account = ConnectedAccount.objects.get(business=business)
        account_id = connected_account.account_id
    except ConnectedAccount.DoesNotExist:
        return render(request, 'stripe_connect/dashboard.html', {
            'connected_account': None,
            'account_status': None,
            'ready_to_process_payments': False,
            'onboarding_complete': False,
            'stripe_configured': True,
        })
    
    # Fetch account status directly from API
    # This ensures we always have the latest status
    try:
        account = stripe_client.v2.core.accounts.retrieve(
            account_id,
            include=["configuration.merchant", "requirements"],
        )
        
        # Check if account is ready to process payments
        # Card payments capability must be active
        card_payments_status = (
            account.configuration
            .merchant.capabilities.card_payments.status
            if account.configuration and account.configuration.merchant
            else None
        )
        ready_to_process_payments = card_payments_status == "active"
        
        # Check onboarding completion status
        # Requirements should not be currently_due or past_due
        requirements_status = (
            account.requirements.summary.minimum_deadline.status
            if account.requirements and account.requirements.summary
            else None
        )
        onboarding_complete = (
            requirements_status is not None
            and requirements_status != "currently_due"
            and requirements_status != "past_due"
        )
        
        # Update cached information
        connected_account.display_name = account.display_name or connected_account.display_name
        connected_account.contact_email = account.contact_email or connected_account.contact_email
        connected_account.save()
        
        return render(request, 'stripe_connect/dashboard.html', {
            'connected_account': connected_account,
            'account': account,
            'account_status': {
                'card_payments_status': card_payments_status,
                'requirements_status': requirements_status,
                'ready_to_process_payments': ready_to_process_payments,
                'onboarding_complete': onboarding_complete,
            },
            'stripe_configured': True,
        })
        
    except stripe.error.StripeError as e:
        return render(request, 'stripe_connect/dashboard.html', {
            'connected_account': connected_account,
            'error': f"Error fetching account status: {e.user_message or str(e)}",
            'stripe_configured': True,
        })


# ============================================================================
# PRODUCT MANAGEMENT
# ============================================================================

@role_required("owner")
def product_list(request):
    """
    List all products for the connected account.
    
    Products are fetched from Stripe using the Stripe-Account header
    to ensure we get products from the connected account.
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect('stripe_connect:dashboard')
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    try:
        connected_account = ConnectedAccount.objects.get(business=business)
    except ConnectedAccount.DoesNotExist:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect('stripe_connect:dashboard')
    
    stripe_client = _get_stripe_client()
    
    try:
        # List products from the connected account
        # Use stripeAccount parameter to specify the connected account
        products_response = stripe_client.products.list(
            limit=20,
            active=True,
            expand=['data.default_price'],
            stripe_account=connected_account.account_id,
        )
        
        products = products_response.data
        
        # Sync products with database (optional, for quick access)
        for product in products:
            default_price = product.default_price
            if default_price:
                ConnectedProduct.objects.update_or_create(
                    stripe_product_id=product.id,
                    defaults={
                        'connected_account': connected_account,
                        'stripe_price_id': default_price.id if isinstance(default_price, str) else default_price.id,
                        'name': product.name,
                        'description': product.description or '',
                        'price_amount': Decimal(default_price.unit_amount) if hasattr(default_price, 'unit_amount') else 0,
                        'currency': default_price.currency if hasattr(default_price, 'currency') else 'usd',
                        'active': product.active,
                    }
                )
        
        # Get products from database for display
        db_products = ConnectedProduct.objects.filter(
            connected_account=connected_account,
            active=True
        ).order_by('-created_at')
        
        return render(request, 'stripe_connect/product_list.html', {
            'products': db_products,
            'connected_account': connected_account,
        })
        
    except stripe.error.StripeError as e:
        messages.error(request, f"Error fetching products: {e.user_message or str(e)}")
        return render(request, 'stripe_connect/product_list.html', {
            'products': [],
            'connected_account': connected_account,
        })


@role_required("owner")
def product_create(request):
    """
    Create a new product on the connected account.
    
    Uses Stripe-Account header to create the product on the connected account.
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect('stripe_connect:product_list')
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    try:
        connected_account = ConnectedAccount.objects.get(business=business)
    except ConnectedAccount.DoesNotExist:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect('stripe_connect:dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price_str = request.POST.get('price', '').strip()
        currency = request.POST.get('currency', 'usd').strip().lower()
        
        if not name:
            messages.error(request, "Product name is required.")
            return render(request, 'stripe_connect/product_create.html', {
                'connected_account': connected_account,
            })
        
        try:
            # Convert price to cents
            price_dollars = Decimal(price_str)
            price_in_cents = int(price_dollars * 100)
            
            if price_in_cents <= 0:
                raise ValueError("Price must be greater than 0")
                
        except (ValueError, TypeError):
            messages.error(request, "Invalid price. Please enter a valid number.")
            return render(request, 'stripe_connect/product_create.html', {
                'connected_account': connected_account,
            })
        
        stripe_client = _get_stripe_client()
        
        try:
            # Create product on the connected account
            # Use stripeAccount parameter to specify the connected account
            product = stripe_client.products.create(
                name=name,
                description=description,
                default_price_data={
                    'unit_amount': price_in_cents,
                    'currency': currency,
                },
                stripe_account=connected_account.account_id,
            )
            
            # Store in database
            default_price = product.default_price
            ConnectedProduct.objects.create(
                connected_account=connected_account,
                stripe_product_id=product.id,
                stripe_price_id=default_price.id if hasattr(default_price, 'id') else str(default_price),
                name=product.name,
                description=product.description or '',
                price_amount=Decimal(price_in_cents),
                currency=currency,
                active=product.active,
            )
            
            messages.success(request, f"Product '{name}' created successfully!")
            return redirect('stripe_connect:product_list')
            
        except stripe.error.StripeError as e:
            messages.error(request, f"Error creating product: {e.user_message or str(e)}")
    
    return render(request, 'stripe_connect/product_create.html', {
        'connected_account': connected_account,
    })


# ============================================================================
# STOREFRONT
# ============================================================================

def storefront(request, account_id):
    """
    Public storefront for a connected account.
    
    Displays products that customers can purchase.
    Uses account_id in URL (in production, use a more secure identifier).
    
    Args:
        account_id: Stripe Connect account ID (acct_xxx)
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        return render(request, 'stripe_connect/storefront.html', {
            'error': error_msg,
            'products': [],
        })
    
    try:
        connected_account = ConnectedAccount.objects.get(account_id=account_id)
    except ConnectedAccount.DoesNotExist:
        return render(request, 'stripe_connect/storefront.html', {
            'error': 'Store not found.',
            'products': [],
        })
    
    stripe_client = _get_stripe_client()
    
    try:
        # List products from the connected account
        # Use stripeAccount parameter to get products from the connected account
        products_response = stripe_client.products.list(
            limit=20,
            active=True,
            expand=['data.default_price'],
            stripe_account=account_id,
        )
        
        products = products_response.data
        
        return render(request, 'stripe_connect/storefront.html', {
            'connected_account': connected_account,
            'products': products,
            'account_id': account_id,
        })
        
    except stripe.error.StripeError as e:
        return render(request, 'stripe_connect/storefront.html', {
            'connected_account': connected_account,
            'error': f"Error loading products: {e.user_message or str(e)}",
            'products': [],
        })


# ============================================================================
# CHECKOUT
# ============================================================================

@require_POST
def create_checkout_session(request, account_id):
    """
    Create a Stripe Checkout session for purchasing a product.
    
    Uses Direct Charge with application fee to monetize the transaction.
    Uses hosted checkout for simplicity.
    
    Args:
        account_id: Stripe Connect account ID (acct_xxx)
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        return JsonResponse({'error': error_msg}, status=400)
    
    try:
        connected_account = ConnectedAccount.objects.get(account_id=account_id)
    except ConnectedAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)
    
    product_id = request.POST.get('product_id')
    price_id = request.POST.get('price_id')
    quantity = int(request.POST.get('quantity', 1))
    
    if not price_id:
        return JsonResponse({'error': 'Price ID is required'}, status=400)
    
    stripe_client = _get_stripe_client()
    
    try:
        # Get application fee amount
        # Use platform fee percentage from settings or business settings
        fee_percent = getattr(connected_account.business, 'stripe_connect_application_fee_percent', None)
        if fee_percent is None:
            fee_percent = getattr(settings, 'STRIPE_CONNECT_APPLICATION_FEE_PERCENT', 0) or 0
        
        # For this demo, we'll use a fixed fee amount
        # In production, calculate based on product price
        application_fee_amount = 123  # TODO: Calculate based on product price and fee_percent
        
        # Get base URL for redirect URLs
        base_url = request.build_absolute_uri('/').rstrip('/')
        
        # Create checkout session
        # Use stripeAccount parameter to make the connected account the merchant
        session = stripe_client.checkout.sessions.create(
            line_items=[
                {
                    'price': price_id,
                    'quantity': quantity,
                },
            ],
            payment_intent_data={
                # Application fee - platform takes this amount from the transaction
                'application_fee_amount': application_fee_amount,
            },
            mode='payment',
            success_url=f'{base_url}/stripe-connect/success/?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{base_url}/stripe-connect/storefront/{account_id}/',
            stripe_account=account_id,  # Use stripeAccount to specify connected account
        )
        
        return JsonResponse({
            'session_id': session.id,
            'url': session.url,
        })
        
    except stripe.error.StripeError as e:
        return JsonResponse({
            'error': e.user_message or str(e)
        }, status=400)


def checkout_success(request):
    """
    Handle successful checkout redirect.
    
    User is redirected here after successful payment.
    """
    session_id = request.GET.get('session_id')
    
    if not session_id:
        messages.error(request, "Missing session ID.")
        return redirect('dashboard')
    
    stripe_client = _get_stripe_client()
    
    try:
        # Retrieve the checkout session to get details
        session = stripe_client.checkout.sessions.retrieve(session_id)
        
        return render(request, 'stripe_connect/checkout_success.html', {
            'session': session,
        })
        
    except stripe.error.StripeError as e:
        messages.error(request, f"Error retrieving session: {e.user_message or str(e)}")
        return redirect('dashboard')


# ============================================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================================

@role_required("owner")
def subscription_create(request):
    """
    Create a subscription for the connected account.
    
    Uses customer_account parameter to charge the connected account.
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect('stripe_connect:dashboard')
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    try:
        connected_account = ConnectedAccount.objects.get(business=business)
    except ConnectedAccount.DoesNotExist:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect('stripe_connect:dashboard')
    
    # Get price ID from settings or request
    # TODO: In production, this should come from a product/price selection UI
    price_id = getattr(settings, 'STRIPE_SUBSCRIPTION_PRICE_ID', None)
    if not price_id:
        messages.error(request, "STRIPE_SUBSCRIPTION_PRICE_ID is not configured. Please set it in your .env file.")
        return redirect('stripe_connect:dashboard')
    
    stripe_client = _get_stripe_client()
    
    try:
        base_url = request.build_absolute_uri('/').rstrip('/')
        
        # Create checkout session for subscription
        # Use customer_account to charge the connected account
        session = stripe_client.checkout.sessions.create(
            customer_account=connected_account.account_id,  # Use customer_account for V2 accounts
            mode='subscription',
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            success_url=f'{base_url}/stripe-connect/subscription/success/?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{base_url}/stripe-connect/dashboard/',
        )
        
        return redirect(session.url)
        
    except stripe.error.StripeError as e:
        messages.error(request, f"Error creating subscription: {e.user_message or str(e)}")
        return redirect('stripe_connect:dashboard')


@role_required("owner")
def subscription_success(request):
    """
    Handle successful subscription creation.
    """
    session_id = request.GET.get('session_id')
    
    if not session_id:
        messages.error(request, "Missing session ID.")
        return redirect('stripe_connect:dashboard')
    
    stripe_client = _get_stripe_client()
    
    try:
        session = stripe_client.checkout.sessions.retrieve(session_id)
        messages.success(request, "Subscription created successfully!")
        return redirect('stripe_connect:dashboard')
        
    except stripe.error.StripeError as e:
        messages.error(request, f"Error retrieving session: {e.user_message or str(e)}")
        return redirect('stripe_connect:dashboard')


@role_required("owner")
def billing_portal(request):
    """
    Create a billing portal session for managing subscription.
    
    Allows connected account to manage their subscription (upgrade, downgrade, cancel).
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect('stripe_connect:dashboard')
    
    business = get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect('dashboard')
    
    try:
        connected_account = ConnectedAccount.objects.get(business=business)
    except ConnectedAccount.DoesNotExist:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect('stripe_connect:dashboard')
    
    stripe_client = _get_stripe_client()
    
    try:
        base_url = request.build_absolute_uri('/').rstrip('/')
        
        # Create billing portal session
        # Use customer_account for V2 accounts
        session = stripe_client.billing_portal.sessions.create(
            customer_account=connected_account.account_id,  # Use customer_account for V2 accounts
            return_url=f'{base_url}/stripe-connect/dashboard/',
        )
        
        return redirect(session.url)
        
    except stripe.error.StripeError as e:
        messages.error(request, f"Error creating billing portal session: {e.user_message or str(e)}")
        return redirect('stripe_connect:dashboard')

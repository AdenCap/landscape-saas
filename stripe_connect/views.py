"""
Stripe Connect V2 Integration Views

This module implements a complete Stripe Connect V2 integration including:
- Creating connected accounts using V2 API
- Onboarding connected accounts with Account Links
- Product management (create/list)
- Storefront for customers
- Direct Charge checkout with application fees
- Connected account subscriptions
- Billing portal for connected accounts
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET

from accounts.decorators import role_required
from accounts.utils import get_business
from businesses.models import Business
from stripe_connect.models import ConnectedAccountProduct, ConnectedAccountSubscription

# Initialize Stripe client
# NOTE: STRIPE_SECRET_KEY must be set in environment variables
# If not set, operations will fail with helpful error messages
try:
    import stripe
    from stripe import StripeClient
    
    # Get the Stripe secret key from settings
    # This should be set in your .env file as STRIPE_SECRET_KEY=sk_test_... or sk_live_...
    stripe_secret_key = getattr(settings, "STRIPE_SECRET_KEY", None)
    if not stripe_secret_key:
        raise ValueError("STRIPE_SECRET_KEY is not set in settings. Please add it to your .env file.")
    
    # Create Stripe client instance
    # This client will be used for all Stripe API requests
    stripe_client = StripeClient(stripe_secret_key)
except ImportError:
    stripe = None
    StripeClient = None
    stripe_client = None
except ValueError as e:
    stripe = None
    StripeClient = None
    stripe_client = None
    logging.error(f"Stripe configuration error: {e}")

logger = logging.getLogger(__name__)


def _check_stripe_configured():
    """Helper to check if Stripe is properly configured."""
    if not stripe_client:
        return False, "Stripe is not configured. Please set STRIPE_SECRET_KEY in your environment variables."
    return True, None


def _get_application_fee_amount(amount_cents, business):
    """
    Calculate application fee amount in cents.
    
    Args:
        amount_cents: Total amount in cents
        business: Business model instance
    
    Returns:
        Application fee in cents (integer)
    """
    # Check if business has a custom fee percentage
    fee_percent = business.stripe_connect_application_fee_percent
    if fee_percent is None:
        # Use global default from settings
        fee_percent = getattr(settings, "STRIPE_CONNECT_APPLICATION_FEE_PERCENT", 0) or 0
    else:
        fee_percent = float(fee_percent)
    
    if fee_percent <= 0:
        return 0
    
    # Calculate fee: amount * (fee_percent / 100)
    fee_cents = int(amount_cents * (fee_percent / 100))
    return fee_cents


@role_required("owner")
@require_http_methods(["GET", "POST"])
def connect_onboarding(request):
    """
    Onboard a business to Stripe Connect.
    
    GET: Shows onboarding status and button to start onboarding
    POST: Creates a connected account and redirects to onboarding
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return render(request, "stripe_connect/onboarding.html", {
            "error": error_msg,
            "business": get_business(request),
        })
    
    business = get_business(request)
    if not business:
        messages.error(request, "No business associated with your account.")
        return redirect("/")
    
    # If account already exists, show status
    if business.stripe_connect_account_id:
        account_id = business.stripe_connect_account_id
        
        try:
            # Retrieve account status from Stripe API
            # Using V2 API to get account with requirements and merchant configuration
            account = stripe_client.v2.core.accounts.retrieve(
                account_id,
                include=["configuration.merchant", "requirements"]
            )
            
            # Check if account is ready to process payments
            # For V2 accounts, check merchant capability status
            merchant_config = account.get("configuration", {}).get("merchant", {})
            capabilities = merchant_config.get("capabilities", {})
            card_payments = capabilities.get("card_payments", {})
            ready_to_process_payments = card_payments.get("status") == "active"
            
            # Check onboarding requirements status
            requirements = account.get("requirements", {})
            summary = requirements.get("summary", {})
            minimum_deadline = summary.get("minimum_deadline", {})
            requirements_status = minimum_deadline.get("status")
            
            # Onboarding is complete when requirements are not currently_due or past_due
            onboarding_complete = (
                requirements_status != "currently_due" and 
                requirements_status != "past_due"
            )
            
            # Get account display name and email
            display_name = account.get("display_name", "")
            contact_email = account.get("contact_email", "")
            
            return render(request, "stripe_connect/onboarding.html", {
                "business": business,
                "account_id": account_id,
                "display_name": display_name,
                "contact_email": contact_email,
                "ready_to_process_payments": ready_to_process_payments,
                "onboarding_complete": onboarding_complete,
                "requirements_status": requirements_status,
            })
        except stripe.StripeError as e:
            logger.error(f"Error retrieving Stripe account {account_id}: {e}")
            messages.error(request, f"Error retrieving account status: {str(e)}")
            return render(request, "stripe_connect/onboarding.html", {
                "business": business,
                "error": str(e),
            })
    
    # If POST, create new connected account
    if request.method == "POST":
        try:
            # Get user information for account creation
            # In production, you might want to collect this from a form
            display_name = business.name or request.user.get_full_name() or request.user.username
            contact_email = request.user.email or business.contact_email or ""
            
            if not contact_email:
                messages.error(request, "Email address is required for Stripe Connect onboarding.")
                return redirect("stripe_connect:onboarding")
            
            # Create connected account using V2 API
            # IMPORTANT: Do NOT use top-level 'type' parameter
            # Only use the properties specified in the requirements
            account = stripe_client.v2.core.accounts.create(
                display_name=display_name,
                contact_email=contact_email,
                identity={
                    "country": "us",  # TODO: Allow user to select country
                },
                dashboard="full",  # Full dashboard access
                defaults={
                    "responsibilities": {
                        "fees_collector": "stripe",  # Stripe collects fees
                        "losses_collector": "stripe",  # Stripe handles losses
                    },
                },
                configuration={
                    "customer": {},  # Enable customer configuration
                    "merchant": {
                        "capabilities": {
                            "card_payments": {
                                "requested": True,  # Request card payment capability
                            },
                        },
                    },
                },
            )
            
            # Store the account ID in the database
            # This maps the business to the Stripe connected account
            account_id = account.get("id")
            business.stripe_connect_account_id = account_id
            business.save(update_fields=["stripe_connect_account_id"])
            
            # Create account link for onboarding
            return redirect("stripe_connect:create_account_link")
            
        except stripe.StripeError as e:
            logger.error(f"Error creating Stripe Connect account: {e}")
            messages.error(request, f"Error creating account: {str(e)}")
            return render(request, "stripe_connect/onboarding.html", {
                "business": business,
                "error": str(e),
            })
        except Exception as e:
            logger.error(f"Unexpected error creating Stripe Connect account: {e}", exc_info=True)
            messages.error(request, "An unexpected error occurred. Please try again.")
            return render(request, "stripe_connect/onboarding.html", {
                "business": business,
            })
    
    # GET: Show onboarding page
    return render(request, "stripe_connect/onboarding.html", {
        "business": business,
    })


@role_required("owner")
@require_GET
def create_account_link(request):
    """
    Create an Account Link for onboarding and redirect user to Stripe.
    
    This endpoint creates a Stripe Account Link that allows the connected account
    to complete onboarding. The user will be redirected to Stripe's hosted onboarding flow.
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect("stripe_connect:onboarding")
    
    business = get_business(request)
    if not business or not business.stripe_connect_account_id:
        messages.error(request, "No connected account found. Please create an account first.")
        return redirect("stripe_connect:onboarding")
    
    account_id = business.stripe_connect_account_id
    
    try:
        # Build URLs for redirect
        # refresh_url: Where to redirect if user needs to refresh the link
        # return_url: Where to redirect after onboarding is complete
        base_url = request.build_absolute_uri("/")
        refresh_url = base_url + reverse("stripe_connect:onboarding")
        return_url = base_url + reverse("stripe_connect:onboarding") + f"?accountId={account_id}"
        
        # Create account link using V2 API
        # This link allows the connected account to complete onboarding
        account_link = stripe_client.v2.core.accountLinks.create(
            account=account_id,
            use_case={
                "type": "account_onboarding",
                "account_onboarding": {
                    "configurations": ["merchant", "customer"],  # Configure both merchant and customer
                    "refresh_url": refresh_url,
                    "return_url": return_url,
                },
            },
        )
        
        # Redirect to Stripe's hosted onboarding page
        onboarding_url = account_link.get("url")
        if onboarding_url:
            return redirect(onboarding_url)
        else:
            messages.error(request, "Failed to generate onboarding link.")
            return redirect("stripe_connect:onboarding")
            
    except stripe.StripeError as e:
        logger.error(f"Error creating account link: {e}")
        messages.error(request, f"Error creating onboarding link: {str(e)}")
        return redirect("stripe_connect:onboarding")
    except Exception as e:
        logger.error(f"Unexpected error creating account link: {e}", exc_info=True)
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect("stripe_connect:onboarding")


@role_required("owner")
@require_http_methods(["GET", "POST"])
def product_list(request):
    """
    List products for the connected account.
    
    GET: Shows list of products
    POST: Creates a new product (form submission)
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect("/")
    
    business = get_business(request)
    if not business or not business.stripe_connect_account_id:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect("stripe_connect:onboarding")
    
    account_id = business.stripe_connect_account_id
    
    # GET: Show product list
    if request.method == "GET":
        try:
            # List products from connected account
            # Use Stripe-Account header to specify the connected account
            products_response = stripe_client.products.list(
                limit=20,
                active=True,
                expand=["data.default_price"],
                stripe_account=account_id,  # This sets the Stripe-Account header
            )
            
            products = []
            for product in products_response.data:
                # Extract price information
                default_price = product.get("default_price")
                price_amount = None
                price_id = None
                currency = "usd"
                
                if default_price:
                    if isinstance(default_price, str):
                        price_id = default_price
                    else:
                        price_id = default_price.get("id")
                        price_amount = default_price.get("unit_amount", 0) / 100  # Convert cents to dollars
                        currency = default_price.get("currency", "usd")
                
                products.append({
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "description": product.get("description", ""),
                    "price_amount": price_amount,
                    "price_id": price_id,
                    "currency": currency,
                    "active": product.get("active", True),
                })
            
            return render(request, "stripe_connect/product_list.html", {
                "business": business,
                "products": products,
            })
            
        except stripe.StripeError as e:
            logger.error(f"Error listing products: {e}")
            messages.error(request, f"Error loading products: {str(e)}")
            return render(request, "stripe_connect/product_list.html", {
                "business": business,
                "products": [],
            })
    
    # POST: Create new product
    try:
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        price_str = request.POST.get("price", "").strip()
        currency = request.POST.get("currency", "usd").strip().lower()
        
        # Validate inputs
        if not name:
            messages.error(request, "Product name is required.")
            return redirect("stripe_connect:product_list")
        
        try:
            price = Decimal(price_str)
            if price <= 0:
                raise ValueError("Price must be greater than 0")
            price_in_cents = int(price * 100)  # Convert to cents
        except (ValueError, TypeError):
            messages.error(request, "Invalid price. Please enter a valid number.")
            return redirect("stripe_connect:product_list")
        
        # Create product on connected account
        # Use Stripe-Account header to create product on the connected account
        product = stripe_client.products.create(
            name=name,
            description=description or None,
            default_price_data={
                "unit_amount": price_in_cents,
                "currency": currency,
            },
            stripe_account=account_id,  # This sets the Stripe-Account header
        )
        
        messages.success(request, f"Product '{name}' created successfully!")
        return redirect("stripe_connect:product_list")
        
    except stripe.StripeError as e:
        logger.error(f"Error creating product: {e}")
        messages.error(request, f"Error creating product: {str(e)}")
        return redirect("stripe_connect:product_list")
    except Exception as e:
        logger.error(f"Unexpected error creating product: {e}", exc_info=True)
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect("stripe_connect:product_list")


@require_GET
def storefront(request, account_id):
    """
    Public storefront for a connected account's products.
    
    This is a simple storefront where customers can view and purchase products.
    In production, you might want to use a different identifier (like a slug)
    instead of the account_id in the URL.
    
    Args:
        account_id: Stripe connected account ID (acct_...)
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        return render(request, "stripe_connect/storefront.html", {
            "error": error_msg,
            "account_id": account_id,
        })
    
    try:
        # Retrieve account information
        account = stripe_client.v2.core.accounts.retrieve(account_id)
        display_name = account.get("display_name", "Store")
        
        # List products from connected account
        # Use Stripe-Account header to retrieve products from the connected account
        products_response = stripe_client.products.list(
            limit=20,
            active=True,
            expand=["data.default_price"],
            stripe_account=account_id,  # This sets the Stripe-Account header
        )
        
        products = []
        for product in products_response.data:
            default_price = product.get("default_price")
            price_amount = None
            price_id = None
            currency = "usd"
            
            if default_price:
                if isinstance(default_price, str):
                    price_id = default_price
                else:
                    price_id = default_price.get("id")
                    price_amount = default_price.get("unit_amount", 0) / 100
                    currency = default_price.get("currency", "usd")
            
            products.append({
                "id": product.get("id"),
                "name": product.get("name"),
                "description": product.get("description", ""),
                "price_amount": price_amount,
                "price_id": price_id,
                "currency": currency,
            })
        
        return render(request, "stripe_connect/storefront.html", {
            "account_id": account_id,
            "display_name": display_name,
            "products": products,
        })
        
    except stripe.StripeError as e:
        logger.error(f"Error loading storefront: {e}")
        return render(request, "stripe_connect/storefront.html", {
            "account_id": account_id,
            "error": f"Error loading store: {str(e)}",
            "products": [],
        })


@require_POST
def create_checkout_session(request, account_id):
    """
    Create a Stripe Checkout Session for a product purchase.
    
    Uses Direct Charge with application fee to monetize the transaction.
    The payment goes to the connected account, and the platform takes an application fee.
    
    Args:
        account_id: Stripe connected account ID (acct_...)
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        return JsonResponse({"error": error_msg}, status=500)
    
    try:
        # Get product and price information from request
        price_id = request.POST.get("price_id")
        quantity = int(request.POST.get("quantity", 1))
        
        if not price_id:
            return JsonResponse({"error": "Price ID is required"}, status=400)
        
        # Get business to calculate application fee
        # In production, you might want to store this mapping differently
        business = Business.objects.filter(stripe_connect_account_id=account_id).first()
        
        # Get price information to calculate application fee
        try:
            price_obj = stripe_client.prices.retrieve(
                price_id,
                stripe_account=account_id,
            )
            amount_cents = price_obj.get("unit_amount", 0) * quantity
        except stripe.StripeError:
            return JsonResponse({"error": "Invalid price"}, status=400)
        
        # Calculate application fee
        application_fee_amount = 0
        if business:
            application_fee_amount = _get_application_fee_amount(amount_cents, business)
        
        # Build success and cancel URLs
        base_url = request.build_absolute_uri("/")
        success_url = base_url + reverse("stripe_connect:checkout_success") + "?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = base_url + reverse("stripe_connect:storefront", args=[account_id])
        
        # Create checkout session with Direct Charge
        # Use Stripe-Account header to create session for the connected account
        session = stripe_client.checkout.sessions.create(
            line_items=[
                {
                    "price": price_id,
                    "quantity": quantity,
                },
            ],
            payment_intent_data={
                "application_fee_amount": application_fee_amount,  # Platform fee
            },
            mode="payment",  # One-time payment
            success_url=success_url,
            cancel_url=cancel_url,
            stripe_account=account_id,  # This sets the Stripe-Account header for Direct Charge
        )
        
        return JsonResponse({"url": session.url})
        
    except stripe.StripeError as e:
        logger.error(f"Error creating checkout session: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected error occurred"}, status=500)


@require_GET
def checkout_success(request):
    """Success page after checkout completion."""
    session_id = request.GET.get("session_id")
    return render(request, "stripe_connect/checkout_success.html", {
        "session_id": session_id,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def connect_subscription(request):
    """
    Allow connected accounts to subscribe to your platform.
    
    GET: Shows subscription status
    POST: Creates checkout session for subscription
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect("/")
    
    business = get_business(request)
    if not business or not business.stripe_connect_account_id:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect("stripe_connect:onboarding")
    
    account_id = business.stripe_connect_account_id
    
    # Get subscription price ID from settings
    # TODO: In production, you might want to allow multiple plans or store this per business
    price_id = getattr(settings, "STRIPE_SUBSCRIPTION_PRICE_ID", None)
    if not price_id:
        messages.error(request, "Subscription pricing is not configured. Please contact support.")
        return render(request, "stripe_connect/subscription.html", {
            "business": business,
            "error": "Subscription pricing not configured",
        })
    
    # Check for existing subscription
    subscription = ConnectedAccountSubscription.objects.filter(
        business=business,
        status__in=["active", "trialing"],
    ).first()
    
    # GET: Show subscription status
    if request.method == "GET":
        return render(request, "stripe_connect/subscription.html", {
            "business": business,
            "subscription": subscription,
            "price_id": price_id,
        })
    
    # POST: Create subscription checkout
    try:
        base_url = request.build_absolute_uri("/")
        success_url = base_url + reverse("stripe_connect:subscription_success") + "?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = base_url + reverse("stripe_connect:connect_subscription")
        
        # Create checkout session for subscription
        # For V2 accounts, use customer_account instead of customer
        # The connected account ID can be used as both the customer and account
        session = stripe_client.checkout.sessions.create(
            customer_account=account_id,  # Use connected account ID as customer
            mode="subscription",
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        
        return redirect(session.url)
        
    except stripe.StripeError as e:
        logger.error(f"Error creating subscription checkout: {e}")
        messages.error(request, f"Error creating subscription: {str(e)}")
        return redirect("stripe_connect:connect_subscription")
    except Exception as e:
        logger.error(f"Unexpected error creating subscription checkout: {e}", exc_info=True)
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect("stripe_connect:connect_subscription")


@require_GET
def subscription_success(request):
    """Success page after subscription checkout."""
    session_id = request.GET.get("session_id")
    messages.success(request, "Subscription activated successfully!")
    return redirect("stripe_connect:connect_subscription")


@role_required("owner")
@require_POST
def create_billing_portal_session(request):
    """
    Create a billing portal session for connected account to manage subscription.
    
    This allows the connected account to update payment methods, view invoices,
    and manage their subscription.
    """
    is_configured, error_msg = _check_stripe_configured()
    if not is_configured:
        messages.error(request, error_msg)
        return redirect("stripe_connect:connect_subscription")
    
    business = get_business(request)
    if not business or not business.stripe_connect_account_id:
        messages.error(request, "Please complete Stripe Connect onboarding first.")
        return redirect("stripe_connect:onboarding")
    
    account_id = business.stripe_connect_account_id
    
    try:
        # Build return URL
        return_url = request.build_absolute_uri(reverse("stripe_connect:connect_subscription"))
        
        # Create billing portal session
        # For V2 accounts, use customer_account instead of customer
        session = stripe_client.billing_portal.sessions.create(
            customer_account=account_id,  # Use connected account ID as customer
            return_url=return_url,
        )
        
        return redirect(session.url)
        
    except stripe.StripeError as e:
        logger.error(f"Error creating billing portal session: {e}")
        messages.error(request, f"Error opening billing portal: {str(e)}")
        return redirect("stripe_connect:connect_subscription")
    except Exception as e:
        logger.error(f"Unexpected error creating billing portal session: {e}", exc_info=True)
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect("stripe_connect:connect_subscription")

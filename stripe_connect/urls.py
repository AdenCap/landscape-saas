"""
URL configuration for Stripe Connect V2 integration.
"""
from django.urls import path
from . import views

app_name = "stripe_connect"

urlpatterns = [
    # Onboarding
    path("onboarding/", views.connect_onboarding, name="onboarding"),
    path("onboarding/create-link/", views.create_account_link, name="create_account_link"),
    
    # Product management
    path("products/", views.product_list, name="product_list"),
    
    # Storefront (public)
    path("store/<str:account_id>/", views.storefront, name="storefront"),
    path("store/<str:account_id>/checkout/", views.create_checkout_session, name="create_checkout_session"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    
    # Connected account subscription
    path("subscription/", views.connect_subscription, name="connect_subscription"),
    path("subscription/success/", views.subscription_success, name="subscription_success"),
    path("subscription/portal/", views.create_billing_portal_session, name="create_billing_portal_session"),
]

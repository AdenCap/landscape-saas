"""
URL patterns for Stripe Connect V2 integration.
"""
from django.urls import path
from . import views

app_name = 'stripe_connect'

urlpatterns = [
    # Connected account onboarding
    path('onboard/', views.connect_onboard, name='onboard'),
    path('onboard/return/', views.connect_onboard_return, name='onboard_return'),
    
    # Dashboard
    path('dashboard/', views.connect_dashboard, name='dashboard'),
    
    # Product management
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    
    # Storefront (public)
    path('storefront/<str:account_id>/', views.storefront, name='storefront'),
    
    # Checkout
    path('checkout/<str:account_id>/', views.create_checkout_session, name='create_checkout'),
    path('success/', views.checkout_success, name='checkout_success'),
    
    # Subscription management
    path('subscription/create/', views.subscription_create, name='subscription_create'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('billing-portal/', views.billing_portal, name='billing_portal'),
]

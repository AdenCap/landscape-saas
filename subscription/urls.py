from django.urls import path
from . import views

app_name = "subscription"

urlpatterns = [
    path("", views.subscription_status, name="status"),
    path("create-checkout/", views.create_checkout_session, name="create_checkout"),
    path("success/", views.checkout_success, name="success"),
    path("portal/", views.create_portal_session, name="portal"),
]

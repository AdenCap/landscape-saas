from django.urls import path
from . import views

app_name = "subscription"

urlpatterns = [
    path("", views.subscription_status, name="status"),
    path("create-checkout/", views.create_checkout_session, name="create_checkout"),
    path("start-trial/", views.start_free_trial, name="start_trial"),
    path("success/", views.checkout_success, name="success"),
    path("portal/", views.create_portal_session, name="portal"),
]

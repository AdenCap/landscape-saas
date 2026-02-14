from django.urls import path
from . import views

app_name = "quickbooks"

urlpatterns = [
    path("", views.quickbooks_settings, name="settings"),
    path("connect/", views.oauth_start, name="oauth_start"),
    path("callback/", views.oauth_callback, name="oauth_callback"),
    path("disconnect/", views.oauth_disconnect, name="oauth_disconnect"),
    path("invoice/<int:invoice_id>/push/", views.push_invoice, name="push_invoice"),
]

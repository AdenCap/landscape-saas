from django.urls import path
from . import views

urlpatterns = [
    path("", views.business_settings, name="business_settings"),
    path("test-email/", views.test_gmail_connection, name="test_gmail_connection"),
    path("disconnect-gmail/", views.disconnect_gmail, name="disconnect_gmail"),
]

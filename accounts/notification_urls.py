"""URLs for employee notifications: inbox and mark-read."""
from django.urls import path
from . import views

urlpatterns = [
    path("inbox/", views.notification_inbox, name="notification_inbox"),
    path("<int:notification_id>/read/", views.notification_mark_read, name="notification_mark_read"),
]

from django.urls import path
from . import views

app_name = "service_agreements"

urlpatterns = [
    path("", views.hub, name="hub"),
]

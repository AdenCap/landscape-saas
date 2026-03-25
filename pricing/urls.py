from django.urls import path
from . import views

urlpatterns = [
    path("", views.service_pricing, name="service_pricing"),
]

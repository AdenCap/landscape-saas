from django.urls import path
from . import views

app_name = "pricebook"

urlpatterns = [
    path("", views.hub, name="hub"),
]

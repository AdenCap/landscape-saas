from django.urls import path
from . import views

app_name = "inspections"

urlpatterns = [
    path("", views.hub, name="hub"),
]

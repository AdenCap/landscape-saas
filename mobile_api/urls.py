from django.urls import path

from . import views

app_name = "mobile_api"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("auth/login/", views.login, name="login"),
    path("auth/refresh/", views.refresh, name="refresh"),
    path("auth/logout/", views.logout, name="logout"),
]

from django.urls import path

from . import views

app_name = "mobile_api"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("bootstrap/", views.bootstrap, name="bootstrap"),
    path("auth/login/", views.login, name="login"),
    path("auth/apple/", views.apple_login, name="apple_login"),
    path("auth/google/", views.google_login, name="google_login"),
    path("auth/refresh/", views.refresh, name="refresh"),
    path("auth/logout/", views.logout, name="logout"),
]

from django.urls import path
from .views import owner_dashboard, crew_day_detail

urlpatterns = [
    path("", owner_dashboard, name="owner_dashboard"),
    path("crew/<int:user_id>/", crew_day_detail, name="crew_day_detail"),
]

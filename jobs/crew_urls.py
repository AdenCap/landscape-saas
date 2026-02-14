from django.urls import path
from . import crew_views

urlpatterns = [
    path("", crew_views.crew_list, name="crew_list"),
    path("add/", crew_views.crew_add, name="crew_add"),
    path("<int:crew_id>/", crew_views.crew_edit, name="crew_edit"),
]

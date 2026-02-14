from django.urls import path
from django.views.generic import RedirectView
from . import crew_views

urlpatterns = [
    path("", RedirectView.as_view(url="/employee-management/", permanent=False), name="crew_list"),
    path("add/", crew_views.crew_add, name="crew_add"),
    path("<int:crew_id>/", crew_views.crew_edit, name="crew_edit"),
]

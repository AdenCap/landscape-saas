from django.urls import path
from . import views

app_name = "service_agreements"

urlpatterns = [
    path("", views.maintenance_hub, name="hub"),
    path("list/", views.hub, name="agreement_list"),
    path("create/", views.agreement_create, name="agreement_create"),
    path("<int:agreement_id>/", views.agreement_detail, name="agreement_detail"),
    path("<int:agreement_id>/delete/", views.agreement_delete, name="agreement_delete"),
    path("service/<int:line_item_id>/complete/", views.complete_service, name="complete_service"),
    path("service/<int:line_item_id>/schedule/", views.schedule_service, name="schedule_service"),
]

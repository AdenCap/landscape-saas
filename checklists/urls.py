from django.urls import path
from . import views

app_name = "checklists"

urlpatterns = [
    path("", views.template_list, name="template_list"),
    path("create/", views.template_create, name="template_create"),
    path("<int:template_id>/edit/", views.template_edit, name="template_edit"),
    path("<int:template_id>/delete/", views.template_delete, name="template_delete"),
]

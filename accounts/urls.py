from django.urls import path
from . import views

urlpatterns = [
    path("", views.employee_list, name="employee_list"),
    path("add/", views.employee_add, name="employee_add"),
    path("<int:user_id>/", views.employee_edit, name="employee_edit"),
    path("<int:user_id>/password/", views.employee_password, name="employee_password"),
]

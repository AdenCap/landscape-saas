from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path("", RedirectView.as_view(url="/employee-management/", permanent=False), name="employee_list"),
    path("add/", views.employee_add, name="employee_add"),
    path("<int:user_id>/payments/", views.employee_record_payment, name="employee_record_payment"),
    path("<int:user_id>/password/", views.employee_password, name="employee_password"),
    path("<int:user_id>/", views.employee_edit, name="employee_edit"),
]

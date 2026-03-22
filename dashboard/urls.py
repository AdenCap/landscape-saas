from django.urls import path
from .views import owner_dashboard, owner_onboarding, dispatch_command_center, reliability_center, crew_day_detail, employee_management, morning_brief, crew_locations_api
from . import em_api_views

urlpatterns = [
    path("", owner_dashboard, name="owner_dashboard"),
    path("onboarding/", owner_onboarding, name="owner_onboarding"),
    path("command-center/", dispatch_command_center, name="dispatch_command_center"),
    path("command-center/crew-locations/", crew_locations_api, name="crew_locations_api"),
    path("reliability/", reliability_center, name="reliability_center"),
    path("crew/<int:user_id>/", crew_day_detail, name="crew_day_detail"),
    path("employee-management/", employee_management, name="employee_management"),
    path("morning-brief/", morning_brief, name="morning_brief"),

    # Employee Management API (AJAX endpoints for modals)
    path("employee-management/api/employee/add/", em_api_views.em_employee_add, name="em_employee_add"),
    path("employee-management/api/employee/<int:user_id>/", em_api_views.em_employee_detail, name="em_employee_detail"),
    path("employee-management/api/employee/<int:user_id>/edit/", em_api_views.em_employee_edit, name="em_employee_edit"),
    path("employee-management/api/employee/<int:user_id>/toggle-active/", em_api_views.em_employee_toggle_active, name="em_employee_toggle_active"),
    path("employee-management/api/employee/<int:user_id>/password/", em_api_views.em_employee_password, name="em_employee_password"),
    path("employee-management/api/crew/add/", em_api_views.em_crew_add, name="em_crew_add"),
    path("employee-management/api/crew/<int:crew_id>/", em_api_views.em_crew_detail, name="em_crew_detail"),
    path("employee-management/api/crew/<int:crew_id>/edit/", em_api_views.em_crew_edit, name="em_crew_edit"),
    path("employee-management/api/crew/<int:crew_id>/delete/", em_api_views.em_crew_delete, name="em_crew_delete"),
    path("employee-management/api/payment/record/", em_api_views.em_payment_record, name="em_payment_record"),
    path("employee-management/api/payment/calculate/", em_api_views.em_payment_calculate, name="em_payment_calculate"),
    path("employee-management/api/time-entries/", em_api_views.em_time_entries, name="em_time_entries"),
    path("employee-management/api/time-entry/<int:entry_id>/edit/", em_api_views.em_time_entry_edit, name="em_time_entry_edit"),
]

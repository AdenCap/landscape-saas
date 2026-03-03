from django.urls import path
from .views import owner_dashboard, owner_onboarding, dispatch_command_center, reliability_center, crew_day_detail, employee_management

urlpatterns = [
    path("", owner_dashboard, name="owner_dashboard"),
    path("onboarding/", owner_onboarding, name="owner_onboarding"),
    path("command-center/", dispatch_command_center, name="dispatch_command_center"),
    path("reliability/", reliability_center, name="reliability_center"),
    path("crew/<int:user_id>/", crew_day_detail, name="crew_day_detail"),
    path("employee-management/", employee_management, name="employee_management"),
]

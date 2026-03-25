from django.urls import path
from . import views

app_name = "financials"

urlpatterns = [
    path("", views.financials_dashboard, name="dashboard"),
    path("revenue/", views.revenue_breakdown, name="revenue_breakdown"),
    path("revenue/categories/", views.revenue_categories_list, name="revenue_categories"),
    path("revenue/categories/add/", views.revenue_category_add, name="revenue_category_add"),
    path("revenue/categories/<int:category_id>/edit/", views.revenue_category_edit, name="revenue_category_edit"),
    path("revenue/categories/<int:category_id>/delete/", views.revenue_category_delete, name="revenue_category_delete"),
    path("revenue/categories/assign/", views.revenue_category_assign, name="revenue_category_assign"),
    path("receipts/", views.receipt_list, name="receipt_list"),
    path("parse-receipt/", views.parse_receipt, name="parse_receipt"),
    path("upload/", views.receipt_upload, name="receipt_upload"),
    path("upload/job/<int:job_id>/", views.receipt_upload, name="receipt_upload_for_job"),
    path("job/<int:job_id>/add-material-cost/", views.job_add_material_cost, name="job_add_material_cost"),
    path("<int:receipt_id>/edit/", views.receipt_edit, name="receipt_edit"),
    path("<int:receipt_id>/download/", views.receipt_download, name="receipt_download"),
    path("<int:receipt_id>/delete/", views.receipt_delete, name="receipt_delete"),

    # Overhead & Business Cost Tracking
    path("overhead/", views.overhead_hub, name="overhead_hub"),
    path("overhead/expense/save/", views.overhead_expense_save, name="overhead_expense_save"),
    path("overhead/expense/<int:pk>/delete/", views.overhead_expense_delete, name="overhead_expense_delete"),
    path("overhead/equipment/save/", views.equipment_save, name="equipment_save"),
    path("overhead/equipment/<int:pk>/delete/", views.equipment_delete, name="equipment_delete"),
    path("overhead/vehicle/save/", views.vehicle_save, name="vehicle_save"),
    path("overhead/vehicle/<int:pk>/delete/", views.vehicle_delete, name="vehicle_delete"),
    path("overhead/burden/save/", views.burden_save, name="burden_save"),
]

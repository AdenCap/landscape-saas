from django.urls import path
from . import views

app_name = "fertilization"

urlpatterns = [
    # Main hub page
    path("", views.hub, name="hub"),
    path("program/create/", views.program_builder, name="program_builder"),
    path("program/<int:program_id>/edit/", views.program_builder, name="program_builder_edit"),
    path("enroll/", views.enrollment_builder, name="enrollment_builder"),

    # Programs CRUD (AJAX)
    path("api/programs/", views.program_list_create, name="program_list_create"),
    path("api/programs/<int:pk>/", views.program_detail, name="program_detail"),
    path("api/programs/<int:pk>/delete/", views.program_delete, name="program_delete"),
    path("api/programs/<int:pk>/duplicate/", views.program_duplicate, name="program_duplicate"),

    # Rounds CRUD (AJAX)
    path("api/rounds/<int:program_id>/", views.round_list_create, name="round_list_create"),
    path("api/rounds/<int:program_id>/<int:pk>/", views.round_update_delete, name="round_update_delete"),

    # Products CRUD (AJAX)
    path("api/products/", views.product_list_create, name="product_list_create"),
    path("api/products/<int:pk>/", views.product_detail, name="product_detail"),

    # Enrollment CRUD (AJAX)
    path("api/enrollments/", views.enrollment_list_create, name="enrollment_list_create"),
    path("api/enrollments/<int:pk>/", views.enrollment_detail, name="enrollment_detail"),
    path("api/enrollments/<int:pk>/cancel/", views.enrollment_cancel, name="enrollment_cancel"),

    # Pricing calculator (AJAX)
    path("api/calculate-pricing/", views.calculate_pricing, name="calculate_pricing"),
    path("api/calculate-product/", views.calculate_product, name="calculate_product"),
    path("api/route-calculator/", views.route_calculator, name="route_calculator"),

    # Applications CRUD (AJAX)
    path("api/applications/", views.application_list_create, name="application_list_create"),
    path("api/applications/<int:pk>/", views.application_detail, name="application_detail"),

    # Reports (downloadable)
    path("api/reports/compliance/", views.report_compliance, name="report_compliance"),
    path("api/reports/profit/", views.report_profit, name="report_profit"),
    path("api/reports/material-usage/", views.report_material_usage, name="report_material_usage"),
]

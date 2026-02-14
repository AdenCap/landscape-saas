from django.urls import path
from . import views

urlpatterns = [
    path("", views.estimator_index, name="estimator_index"),
    path("property/", views.estimator_list, name="estimator_list"),
    path("fertilizer/", views.fertilizer_calculator, name="fertilizer_calculator"),
    path("mulch-rock/", views.mulch_rock_calculator, name="mulch_rock_calculator"),
    path("property/<int:property_id>/satellite/", views.estimator_satellite_image, name="estimator_satellite_image"),
    path("property/<int:property_id>/", views.estimator_new, name="estimator_new"),
    path("property/<int:property_id>/<int:estimate_id>/", views.estimator_detail, name="estimator_detail"),
    path("property/<int:property_id>/<int:estimate_id>/upload/", views.estimator_upload, name="estimator_upload"),
    path("property/<int:property_id>/<int:estimate_id>/analyze/<int:image_id>/", views.estimator_analyze, name="estimator_analyze"),
    path("property/<int:property_id>/<int:estimate_id>/save/", views.estimator_save, name="estimator_save"),
]

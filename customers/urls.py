from django.urls import path
from . import views

urlpatterns = [
    path("", views.customer_list, name="customer_list"),
    path("messages/", views.client_messages_list, name="client_messages_list"),
    path("mass-communications/", views.mass_communications, name="mass_communications"),
    path("add/", views.customer_create, name="customer_create"),
    path("import/", views.customer_import, name="customer_import"),
    path("import/template/", views.customer_import_template, name="customer_import_template"),
    path("export/", views.customer_export, name="customer_export"),
    path("<int:customer_id>/", views.customer_detail, name="customer_detail"),
    path("<int:customer_id>/edit/", views.customer_edit, name="customer_edit"),
    path("<int:customer_id>/message/", views.customer_send_message, name="customer_send_message"),
    path("<int:customer_id>/properties/add/", views.property_add, name="property_add"),
    path("<int:customer_id>/properties/<int:property_id>/edit/", views.property_edit, name="property_edit"),
    path("<int:customer_id>/contracts/add/", views.contract_add, name="contract_add"),
    path("<int:customer_id>/contracts/<int:contract_id>/edit/", views.contract_edit, name="contract_edit"),
    path("<int:customer_id>/properties/<int:property_id>/photos/", views.property_photo_gallery, name="property_photo_gallery"),
    path("reviews/confirm/<str:token>/", views.review_mark_done, name="review_mark_done"),
    path("reviews/opt-out/<str:token>/", views.review_opt_out, name="review_opt_out"),
    
    # Customer Portal (public access via token)
    path("portal/<str:token>/", views.customer_portal, name="customer_portal"),
    path("portal/<str:token>/booking/", views.customer_portal_booking, name="customer_portal_booking"),
    path("portal/<str:token>/jobs/<int:job_id>/reschedule/", views.customer_portal_reschedule, name="customer_portal_reschedule"),
    path("portal/<str:token>/jobs/<int:job_id>/cancel/", views.customer_portal_cancel, name="customer_portal_cancel"),
]

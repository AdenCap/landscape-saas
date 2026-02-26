from django.urls import path
from . import views

urlpatterns = [
    path("", views.customer_list, name="customer_list"),
    path("messages/", views.client_messages_list, name="client_messages_list"),
    path("add/", views.customer_create, name="customer_create"),
    path("import/", views.customer_import, name="customer_import"),
    path("<int:customer_id>/", views.customer_detail, name="customer_detail"),
    path("<int:customer_id>/edit/", views.customer_edit, name="customer_edit"),
    path("<int:customer_id>/message/", views.customer_send_message, name="customer_send_message"),
    path("<int:customer_id>/properties/add/", views.property_add, name="property_add"),
    path("<int:customer_id>/properties/<int:property_id>/edit/", views.property_edit, name="property_edit"),
    path("<int:customer_id>/contracts/add/", views.contract_add, name="contract_add"),
    path("<int:customer_id>/contracts/<int:contract_id>/edit/", views.contract_edit, name="contract_edit"),
    path("<int:customer_id>/communication-history/", views.customer_communication_history, name="customer_communication_history"),
]

from django.urls import path
from . import views

urlpatterns = [
    path("", views.invoice_list, name="invoice_list"),
    path("<int:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("<int:invoice_id>/send/", views.send_invoice, name="send_invoice"),
    path("<int:invoice_id>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("estimates/", views.estimate_list, name="estimate_list"),
    path("estimates/create/", views.estimate_create, name="estimate_create"),
    path("estimates/<int:estimate_id>/", views.estimate_detail, name="estimate_detail"),
    path("estimates/<int:estimate_id>/edit/", views.estimate_edit, name="estimate_edit"),
    path("estimates/<int:estimate_id>/pdf/", views.estimate_pdf, name="estimate_pdf"),
    path("estimates/<int:estimate_id>/send/", views.estimate_send, name="estimate_send"),
    path("estimates/<int:estimate_id>/images/add/", views.estimate_add_image, name="estimate_add_image"),
    path("estimates/<int:estimate_id>/view/<str:token>/", views.estimate_client_view, name="estimate_client_view"),
    path("estimates/<int:estimate_id>/accept/<str:token>/", views.estimate_client_accept, name="estimate_client_accept"),
]

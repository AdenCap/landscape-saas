from django.urls import path
from .views import invoice_list_view, invoice_detail
from . import views

urlpatterns = [
    path("", views.invoice_list_view, name="invoice_list"),
    path("<int:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("<int:invoice_id>/send/", views.send_invoice, name="send_invoice"),
    path("<int:invoice_id>/pdf/", views.invoice_pdf, name="invoice_pdf"),
]

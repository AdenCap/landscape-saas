from django.urls import path
from . import views

urlpatterns = [
    path("", views.invoice_list, name="invoice_list"),
    path("create/", views.invoice_create, name="invoice_create"),
    path("outstanding/", views.outstanding_invoices, name="outstanding_invoices"),
    path("monthly/", views.monthly_invoice_list, name="monthly_invoice_list"),
    path("<int:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("<int:invoice_id>/update-dates/", views.invoice_update_dates, name="invoice_update_dates"),
    path("<int:invoice_id>/edit-custom-fields/", views.invoice_edit_custom_fields, name="invoice_edit_custom_fields"),
    path("<int:invoice_id>/edit-line-items/", views.invoice_edit_line_items, name="invoice_edit_line_items"),
    path("<int:invoice_id>/send/", views.send_invoice, name="send_invoice"),
    path("<int:invoice_id>/resend/", views.resend_invoice, name="resend_invoice"),
    path("<int:invoice_id>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("<int:invoice_id>/pay/<str:token>/", views.invoice_pay_page, name="invoice_pay_page"),
    path("<int:invoice_id>/pay/<str:token>/stripe/", views.create_invoice_checkout_session, name="create_invoice_checkout"),
    path("<int:invoice_id>/pay/<str:token>/notify-paid/", views.invoice_customer_paid_notify, name="invoice_customer_paid_notify"),
    path("connect/onboarding/", views.connect_onboarding, name="connect_onboarding"),
    path("connect/return/", views.connect_return, name="connect_return"),
    path("connect/dashboard/", views.connect_dashboard, name="connect_dashboard"),
    path("<int:invoice_id>/mark-paid/", views.mark_invoice_paid, name="mark_invoice_paid"),
    path("<int:invoice_id>/toggle-card-payment/", views.invoice_toggle_card_payment, name="invoice_toggle_card_payment"),
    path("estimates/", views.estimate_list, name="estimate_list"),
    path("estimates/field-capture/", views.field_capture, name="field_capture"),
    path("estimates/queue/", views.estimate_queue, name="estimate_queue"),
    path("estimates/queue/<int:estimate_id>/discard/", views.estimate_queue_discard, name="estimate_queue_discard"),
    path("estimates/create/", views.estimate_create, name="estimate_create"),
    path("estimates/create-from-fertilizer/", views.estimate_create_from_fertilizer, name="estimate_create_from_fertilizer"),
    path("estimates/create-from-mulch/", views.estimate_create_from_mulch, name="estimate_create_from_mulch"),
    path("estimates/<int:estimate_id>/", views.estimate_detail, name="estimate_detail"),
    path("estimates/<int:estimate_id>/edit/", views.estimate_edit, name="estimate_edit"),
    path("estimates/<int:estimate_id>/pdf/", views.estimate_pdf, name="estimate_pdf"),
    path("estimates/<int:estimate_id>/send/", views.estimate_send, name="estimate_send"),
    path("estimates/<int:estimate_id>/send-followup/", views.estimate_send_followup, name="estimate_send_followup"),
    path("estimates/<int:estimate_id>/images/add/", views.estimate_add_image, name="estimate_add_image"),
    path("estimates/<int:estimate_id>/images/<int:image_id>/delete/", views.estimate_delete_image, name="estimate_delete_image"),
    path("estimates/<int:estimate_id>/view/<str:token>/", views.estimate_client_view, name="estimate_client_view"),
    path("estimates/<int:estimate_id>/accept/<str:token>/", views.estimate_client_accept, name="estimate_client_accept"),
    path("templates/", views.document_templates_list, name="document_templates_list"),
    path("templates/<str:doc_type>/", views.document_template_edit, name="document_template_edit"),
    path("templates/<str:doc_type>/email-preview/", views.email_template_preview, name="email_template_preview"),

    # API endpoints
    path("api/customer-properties/<int:customer_id>/", views.api_customer_properties, name="api_customer_properties"),

    # Fertilizer Products
    path("fertilizer-products/", views.fertilizer_products_list, name="fertilizer_products_list"),
    path("fertilizer-products/create/", views.fertilizer_product_create, name="fertilizer_product_create"),
    path("fertilizer-products/<int:product_id>/edit/", views.fertilizer_product_edit, name="fertilizer_product_edit"),
    path("fertilizer-products/<int:product_id>/delete/", views.fertilizer_product_delete, name="fertilizer_product_delete"),
    
    # Property Fertilizer History
    path("properties/<int:property_id>/fertilizer-history/", views.property_fertilizer_history, name="property_fertilizer_history"),
]

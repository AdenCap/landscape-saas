from django.urls import path
from . import views

app_name = 'customer_portal'

urlpatterns = [
    path('login/', views.portal_login, name='login'),
    path('logout/', views.portal_logout, name='logout'),
    path('', views.portal_dashboard, name='dashboard'),
    path('invoices/', views.portal_invoices, name='invoices'),
    path('invoices/<int:invoice_id>/', views.portal_invoice_detail, name='invoice_detail'),
    path('estimates/', views.portal_estimates, name='estimates'),
    path('estimates/<int:estimate_id>/', views.portal_estimate_detail, name='estimate_detail'),
    path('jobs/', views.portal_jobs, name='jobs'),
]

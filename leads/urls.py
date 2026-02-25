from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.lead_list, name='lead_list'),
    path('add/', views.lead_create, name='lead_create'),
    path('<int:lead_id>/', views.lead_detail, name='lead_detail'),
    path('<int:lead_id>/edit/', views.lead_edit, name='lead_edit'),
    path('<int:lead_id>/convert/', views.lead_convert, name='lead_convert'),
]

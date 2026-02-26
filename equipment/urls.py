from django.urls import path
from . import views

app_name = 'equipment'

urlpatterns = [
    path('', views.equipment_list, name='equipment_list'),
    path('add/', views.equipment_create, name='equipment_create'),
    path('<int:equipment_id>/', views.equipment_detail, name='equipment_detail'),
    path('<int:equipment_id>/edit/', views.equipment_edit, name='equipment_edit'),
    path('<int:equipment_id>/maintenance/add/', views.maintenance_add, name='maintenance_add'),
]

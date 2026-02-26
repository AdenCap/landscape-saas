from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('add/', views.inventory_item_create, name='inventory_item_create'),
    path('<int:item_id>/', views.inventory_item_detail, name='inventory_item_detail'),
    path('<int:item_id>/edit/', views.inventory_item_edit, name='inventory_item_edit'),
    path('purchase-orders/', views.purchase_order_list, name='purchase_order_list'),
    path('purchase-orders/add/', views.purchase_order_create, name='purchase_order_create'),
]

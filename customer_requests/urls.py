from django.urls import path
from . import views

app_name = 'customer_requests'

urlpatterns = [
    path('', views.request_list, name='request_list'),
    path('public/', views.request_create_public, name='request_create_public'),
    path('<int:request_id>/', views.request_detail, name='request_detail'),
    path('<int:request_id>/review/', views.request_review, name='request_review'),
]

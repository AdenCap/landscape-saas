from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='document_list'),
    path('add/', views.document_upload, name='document_upload'),
    path('<int:document_id>/', views.document_detail, name='document_detail'),
    path('<int:document_id>/delete/', views.document_delete, name='document_delete'),
]

from django.urls import path
from . import views

app_name = 'referrals'

urlpatterns = [
    path('', views.referral_list, name='referral_list'),
    path('add/', views.referral_create, name='referral_create'),
    path('<int:referral_id>/', views.referral_detail, name='referral_detail'),
]

from django.urls import path
from . import views

app_name = 'surveys'

urlpatterns = [
    path('', views.survey_list, name='survey_list'),
    path('<int:survey_id>/', views.survey_detail, name='survey_detail'),
    path('respond/<str:token>/', views.survey_respond, name='survey_respond'),
]

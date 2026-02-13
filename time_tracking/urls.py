from django.urls import path
from . import views

urlpatterns = [
    path('', views.clock_view, name='time_clock'),
    path('clock-in/', views.clock_in, name='time_clock_in'),
    path('clock-out/', views.clock_out, name='time_clock_out'),
    path('timesheets/', views.timesheets_view, name='time_timesheets'),
]

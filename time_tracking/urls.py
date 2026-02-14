from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.clock_view, name='time_clock'),
    path('clock-in/', views.clock_in, name='time_clock_in'),
    path('clock-out/', views.clock_out, name='time_clock_out'),
    path('timesheets/', RedirectView.as_view(url='/employee-management/', permanent=False), name='time_timesheets'),
]

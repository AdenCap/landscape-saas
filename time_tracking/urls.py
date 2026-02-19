from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.clock_view, name='time_clock'),
    path('clock-in/', views.clock_in, name='time_clock_in'),
    path('clock-out/', views.clock_out, name='time_clock_out'),
    path('timesheets/', RedirectView.as_view(url='/employee-management/', permanent=False), name='time_timesheets'),
    path('entries/pending/', views.time_entries_pending, name='time_entries_pending'),
    path('entries/<int:entry_id>/approve/', views.time_entry_approve, name='time_entry_approve'),
    path('entries/<int:entry_id>/reject/', views.time_entry_reject, name='time_entry_reject'),
    # Time off and schedule live on Employee Management; redirect list/view to there
    path('requests/', RedirectView.as_view(url='/employee-management/#timeoff', permanent=False), name='time_off_list'),
    path('requests/new/', views.time_off_create, name='time_off_create'),
    path('requests/<int:pk>/approve/', views.time_off_approve, name='time_off_approve'),
    path('requests/<int:pk>/deny/', views.time_off_deny, name='time_off_deny'),
    path('schedule/', RedirectView.as_view(url='/employee-management/#schedule', permanent=False), name='time_schedule'),
    path('schedule/edit/', views.schedule_edit, name='time_schedule_edit'),
]

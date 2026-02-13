from django.urls import path
from .import views

urlpatterns = [
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/events/', views.calendar_events, name='calendar_events'),

    path('routes/', views.daily_route_view, name='daily_route'),
    path('routes/update/', views.update_route_order, name='update_route'),

    path('crew/', views.crew_today_view, name='crew_today'),
    path('<int:job_id>/complete/', views.complete_job, name='complete_job'),

    path('<int:job_id>/start/', views.start_job, name='start_job'),
    path('<int:job_id>/complete/', views.complete_job, name='complete_job'),

    path("<int:job_id>/", views.job_detail, name="job_detail"),
    path("<int:job_id>/items/add/", views.add_job_service_item, name="add_job_service_item"),
    path("<int:job_id>/items/<int:item_id>/remove/", views.remove_job_service_item, name="remove_job_service_item"),

]

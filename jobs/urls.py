from django.urls import path
from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("create/", views.create_job, name="create_job"),
    path("schedule-from-estimate/<int:estimate_id>/", views.schedule_from_estimate, name="schedule_from_estimate"),
    path("fertilization-schedule/", views.fertilization_schedule, name="fertilization_schedule"),
    path("mowing/", views.mowing_hub, name="mowing_hub"),
    path("mowing/bulk-message/", views.mowing_bulk_message, name="mowing_bulk_message"),
    path("mowing/add-client/", views.add_mowing_client, name="add_mowing_client"),
    path("mowing/bulk-schedule/", views.mowing_bulk_schedule, name="mowing_bulk_schedule"),
    path("<int:job_id>/billing/", views.job_billing_options, name="job_billing_options"),
    path("<int:job_id>/bill-now/", views.job_bill_now, name="job_bill_now"),
    path("<int:job_id>/add-to-monthly/", views.job_add_to_monthly, name="job_add_to_monthly"),
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/events/', views.calendar_events, name='calendar_events'),
    path('calendar/job/<int:job_id>/', views.calendar_job_data, name='calendar_job_data'),
    path('calendar/job/<int:job_id>/update/', views.calendar_job_update, name='calendar_job_update'),
    path('calendar/job/<int:job_id>/reschedule/', views.calendar_job_reschedule, name='calendar_job_reschedule'),
    path('calendar/quick-create/', views.calendar_quick_create, name='calendar_quick_create'),
    path('calendar/customer-search/', views.calendar_customer_search, name='calendar_customer_search'),
    path('calendar/unscheduled/', views.calendar_unscheduled_jobs, name='calendar_unscheduled_jobs'),
    path('calendar/bulk-reschedule/', views.calendar_bulk_reschedule, name='calendar_bulk_reschedule'),
    path('calendar/meeting/<int:meeting_id>/', views.calendar_meeting_data, name='calendar_meeting_data'),

    path('meetings/', views.meeting_list, name='meeting_list'),
    path('meetings/create/', views.meeting_create, name='meeting_create'),
    path('meetings/<int:meeting_id>/edit/', views.meeting_edit, name='meeting_edit'),
    path('meetings/<int:meeting_id>/delete/', views.meeting_delete, name='meeting_delete'),

    path('routes/', views.daily_route_view, name='daily_route'),
    path('routes/update/', views.update_route_order, name='update_route'),

    path('crew/', views.crew_today_view, name='crew_today'),
    path('crew/quick/', views.crew_quick_view, name='crew_quick'),
    path('<int:job_id>/start/', views.start_job, name='start_job'),
    path('<int:job_id>/en-route/', views.notify_en_route, name='notify_en_route'),
    path('<int:job_id>/complete/', views.complete_job, name='complete_job'),
    path('<int:job_id>/report-issue/', views.report_issue, name='report_issue'),
    path('<int:job_id>/upload-completion-photo/', views.upload_completion_photo, name='upload_completion_photo'),
    path('<int:job_id>/field-request/', views.crew_field_request, name='crew_field_request'),
    path('<int:job_id>/photos/upload/', views.upload_job_photo, name='upload_job_photo'),
    path('<int:job_id>/photos/<int:photo_id>/delete/', views.delete_job_photo, name='delete_job_photo'),
    path('issues/<int:issue_id>/resolve/', views.resolve_issue, name='resolve_issue'),

    path("<int:job_id>/", views.job_detail, name="job_detail"),
    path("<int:job_id>/delete/", views.job_delete, name="job_delete"),
    path("<int:job_id>/items/add/", views.add_job_service_item, name="add_job_service_item"),
    path("<int:job_id>/items/<int:item_id>/remove/", views.remove_job_service_item, name="remove_job_service_item"),
    path("<int:job_id>/costs/", views.job_update_costs, name="job_update_costs"),
    
    # Notes (all roles)
    path("<int:job_id>/notes/", views.get_job_notes, name="get_job_notes"),
    path("<int:job_id>/notes/add/", views.add_job_note, name="add_job_note"),
    path("<int:job_id>/property-notes/add/", views.add_property_note, name="add_property_note"),

    # Real-time tracking (owner only)
    path("<int:job_id>/tracking/update/", views.update_job_location, name="update_job_location"),
    path("<int:job_id>/tracking/", views.get_job_tracking, name="get_job_tracking"),

]

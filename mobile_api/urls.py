from django.urls import path

from . import views

app_name = "mobile_api"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("bootstrap/", views.bootstrap, name="bootstrap"),
    path("time-clock/", views.time_clock_status, name="time_clock_status"),
    path("time-clock/clock-in/", views.time_clock_in, name="time_clock_in"),
    path("time-clock/clock-out/", views.time_clock_out, name="time_clock_out"),
    path("time-clock/location/", views.time_clock_location, name="time_clock_location"),
    path("today/", views.today, name="today"),
    path("jobs/<int:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<int:job_id>/start/", views.job_start, name="job_start"),
    path("jobs/<int:job_id>/complete/", views.job_complete, name="job_complete"),
    path("jobs/<int:job_id>/skip/", views.job_skip, name="job_skip"),
    path("jobs/<int:job_id>/completion-photo/", views.job_completion_photo, name="job_completion_photo"),
    path("jobs/<int:job_id>/photos/", views.job_photos, name="job_photos"),
    path("jobs/<int:job_id>/notes/", views.job_notes, name="job_notes"),
    path("jobs/<int:job_id>/issues/", views.job_issues, name="job_issues"),
    path("sync/pull/", views.sync_pull, name="sync_pull"),
    path("sync/push/", views.sync_push, name="sync_push"),
    path("auth/login/", views.login, name="login"),
    path("auth/apple/", views.apple_login, name="apple_login"),
    path("auth/google/", views.google_login, name="google_login"),
    path("auth/refresh/", views.refresh, name="refresh"),
    path("auth/logout/", views.logout, name="logout"),
]

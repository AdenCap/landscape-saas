"""Signals for job automation: review requests, surveys, etc."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Job
from reviews.models import Review
from surveys.models import Survey


@receiver(post_save, sender=Job)
def on_job_completed(sender, instance, created, **kwargs):
    """When a job is marked as completed, log for review/survey automation."""
    if instance.status == 'completed' and not created:
        # Review and survey requests are handled by management commands
        # that run on a schedule (send_review_requests, send_survey_invitations)
        # This signal just ensures the job is ready for those commands
        pass

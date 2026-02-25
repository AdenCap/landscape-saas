"""Signals for job automation: review requests, surveys, etc."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Job
from reviews.models import Review
from surveys.models import Survey
from customers.sms_utils import send_sms


@receiver(post_save, sender=Job)
def on_job_completed(sender, instance, created, **kwargs):
    """When a job is marked as completed, trigger review request and survey."""
    if instance.status == 'completed' and not created:
        # Check if review already exists
        if not Review.objects.filter(job=instance, customer=instance.property.customer).exists():
            # Create a placeholder review request (in production, this would send an email/SMS)
            pass
        
        # Check if survey already exists
        if not Survey.objects.filter(job=instance, customer=instance.property.customer).exists():
            # Create survey invitation (in production, this would send an email with survey link)
            pass

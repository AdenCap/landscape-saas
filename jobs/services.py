from datetime import timedelta
from django.utils import timezone
from .models import RecurringJob, Job


def generate_jobs(days_ahead=14):
    today = timezone.now().date()
    end_date = today + timedelta(days=days_ahead)

    recurring_jobs = RecurringJob.objects.filter(active=True)

    for rj in recurring_jobs:
        current_date = rj.start_date

        while current_date <= end_date:
            Job.objects.get_or_create(
                property=rj.property,
                scheduled_date=current_date,
                recurring_job=rj,
                defaults={
                    'assigned_to': rj.assigned_to,
                    'notes': rj.notes,
                }
            )

            if rj.frequency == 'weekly':
                current_date += timedelta(weeks=1)
            elif rj.frequency == 'biweekly':
                current_date += timedelta(weeks=2)
            elif rj.frequency == 'monthly':
                current_date += timedelta(days=30)

"""Management command to send satisfaction survey invitations."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import Job
from surveys.models import Survey
from customers.sms_utils import send_sms
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send satisfaction survey invitations for jobs completed 1-2 days ago'

    def handle(self, *args, **options):
        two_days_ago = timezone.now().date() - timedelta(days=2)
        one_day_ago = timezone.now().date() - timedelta(days=1)
        
        jobs = Job.objects.filter(
            status='completed',
            property__customer__isnull=False
        ).select_related('property__customer', 'business')
        
        jobs = jobs.filter(scheduled_date__gte=two_days_ago, scheduled_date__lte=one_day_ago)
        
        sent = 0
        skipped = 0
        
        for job in jobs:
            customer = job.property.customer
            
            # Skip if survey already exists
            if Survey.objects.filter(job=job, customer=customer).exists():
                skipped += 1
                continue
            
            # Generate survey link
            survey_url = f"https://yourdomain.com/surveys/respond/{job.id}/"
            
            # Send via email if available
            if customer.email:
                try:
                    send_mail(
                        subject=f'Quick Survey: How was your service?',
                        message=(
                            f"Hi {customer.name},\n\n"
                            f"We'd love to hear about your experience with our service at {job.property.address}.\n\n"
                            f"Take our quick 2-minute survey: {survey_url}\n\n"
                            f"Thank you!\n{job.business.name}"
                        ),
                        from_email=job.business.get_from_email() or settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[customer.email],
                        fail_silently=False,
                    )
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent survey to {customer.name} via email'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to send email to {customer.name}: {e}'))
            
            # Send via SMS if phone available
            elif customer.phone and customer.communication_preference in ['sms', 'both']:
                message = (
                    f"Hi {customer.name}, we'd love your feedback! "
                    f"Quick survey: {survey_url}"
                )
                success, result = send_sms(customer.phone, message, job.business)
                if success:
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent survey to {customer.name} via SMS'))
                else:
                    self.stdout.write(self.style.ERROR(f'Failed to send SMS to {customer.name}: {result}'))
            else:
                skipped += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Skipped: {skipped}'))

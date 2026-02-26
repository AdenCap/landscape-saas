"""Management command to send review requests after job completion."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import Job
from reviews.models import Review
from customers.sms_utils import send_sms
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send review requests for jobs completed 1-3 days ago'

    def handle(self, *args, **options):
        # Jobs completed 1-3 days ago
        three_days_ago = timezone.now().date() - timedelta(days=3)
        one_day_ago = timezone.now().date() - timedelta(days=1)
        
        jobs = Job.objects.filter(
            status='completed',
            property__customer__isnull=False
        ).select_related('property__customer', 'business')
        
        # Filter by completion date (if we had a completed_at field)
        # For now, use scheduled_date as proxy
        jobs = jobs.filter(scheduled_date__gte=three_days_ago, scheduled_date__lte=one_day_ago)
        
        sent = 0
        skipped = 0
        
        for job in jobs:
            customer = job.property.customer
            
            # Skip if review already exists
            if Review.objects.filter(job=job, customer=customer).exists():
                skipped += 1
                continue
            
            # Generate review link (in production, this would be a secure token)
            review_url = f"https://yourdomain.com/reviews/respond/{job.id}/"
            
            # Send via email if available
            if customer.email:
                try:
                    send_mail(
                        subject=f'How was your service from {job.business.name}?',
                        message=(
                            f"Hi {customer.name},\n\n"
                            f"We hope you're happy with the service we provided at {job.property.address}.\n\n"
                            f"Please take a moment to leave a review: {review_url}\n\n"
                            f"Thank you!\n{job.business.name}"
                        ),
                        from_email=job.business.get_from_email() or settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[customer.email],
                        fail_silently=False,
                    )
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent review request to {customer.name} via email'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to send email to {customer.name}: {e}'))
            
            # Send via SMS if phone available and prefers SMS
            elif customer.phone and customer.communication_preference in ['sms', 'both']:
                message = (
                    f"Hi {customer.name}, how was your service at {job.property.address}? "
                    f"Please leave a review: {review_url}"
                )
                success, result = send_sms(customer.phone, message, job.business)
                if success:
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent review request to {customer.name} via SMS'))
                else:
                    self.stdout.write(self.style.ERROR(f'Failed to send SMS to {customer.name}: {result}'))
            else:
                skipped += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Skipped: {skipped}'))

"""Management command to send SMS reminders for upcoming jobs."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import Job
from customers.sms_utils import send_sms


class Command(BaseCommand):
    help = 'Send SMS reminders for jobs scheduled tomorrow'

    def handle(self, *args, **options):
        tomorrow = timezone.now().date() + timedelta(days=1)
        jobs = Job.objects.filter(
            scheduled_date=tomorrow,
            status='scheduled',
            property__customer__phone__isnull=False
        ).select_related('property__customer', 'business')
        
        sent = 0
        failed = 0
        
        for job in jobs:
            customer = job.property.customer
            if not customer.phone:
                continue
            
            # Check if customer prefers SMS
            if customer.communication_preference not in ['sms', 'both']:
                continue
            
            message = (
                f"Reminder: {job.business.name} will be at {job.property.address} "
                f"tomorrow ({tomorrow.strftime('%B %d')}). "
                f"Questions? Reply to this message or call {job.business.contact_phone or 'us'}."
            )
            
            success, result = send_sms(customer.phone, message, job.business)
            if success:
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent reminder to {customer.name}'))
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f'Failed to send to {customer.name}: {result}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Failed: {failed}'))

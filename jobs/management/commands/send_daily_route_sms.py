"""Management command to send daily route SMS to crew members."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job
from accounts.models import User
from customers.sms_utils import send_sms


class Command(BaseCommand):
    help = 'Send daily route SMS to crew members with their assigned jobs for today'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Get all crew members
        crew_members = User.objects.filter(role='crew', phone__isnull=False)
        
        sent = 0
        failed = 0
        
        for crew in crew_members:
            # Get today's jobs for this crew member
            from django.db.models import Q
            jobs = Job.objects.filter(
                scheduled_date=today
            ).filter(
                Q(assigned_to=crew) |
                Q(assigned_crew__members=crew) |
                Q(assigned_crew__crew_leader=crew)
            ).select_related('property', 'property__customer', 'business').distinct().order_by('route_order')
            
            if not jobs.exists():
                continue
            
            business = crew.business
            if not business:
                continue
            
            # Build route message
            job_list = []
            for i, job in enumerate(jobs, 1):
                job_list.append(f"{i}. {job.property.address}")
            
            message = (
                f"Good morning! Your route for today ({today.strftime('%B %d')}):\n\n"
                + "\n".join(job_list) +
                f"\n\nTotal: {jobs.count()} job(s). Clock in when ready!"
            )
            
            success, result = send_sms(crew.phone, message, business)
            if success:
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent route to {crew.get_full_name() or crew.username}'))
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f'Failed to send to {crew.get_full_name() or crew.username}: {result}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Failed: {failed}'))

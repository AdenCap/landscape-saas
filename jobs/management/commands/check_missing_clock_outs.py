"""Management command to check for employees who forgot to clock out."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from time_tracking.models import TimeEntry
from accounts.models import User
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Alert owners about employees who forgot to clock out (more than 12 hours ago)'

    def handle(self, *args, **options):
        # Find entries clocked in more than 12 hours ago without clock out
        cutoff_time = timezone.now() - timedelta(hours=12)
        
        open_entries = TimeEntry.objects.filter(
            clock_out__isnull=True,
            clock_in__lt=cutoff_time
        ).select_related('user', 'user__business')
        
        if not open_entries.exists():
            self.stdout.write(self.style.SUCCESS('No missing clock-outs found'))
            return
        
        # Group by business
        by_business = {}
        for entry in open_entries:
            business = entry.user.business
            if not business:
                continue
            if business not in by_business:
                by_business[business] = []
            by_business[business].append(entry)
        
        sent = 0
        for business, entries in by_business.items():
            # Get business owner email
            owner = business.users.filter(role='owner').first()
            if not owner or not owner.email:
                continue
            
            entry_list = '\n'.join([
                f"- {entry.user.get_full_name() or entry.user.username}: Clocked in {entry.clock_in.strftime('%Y-%m-%d %H:%M')} ({timezone.now() - entry.clock_in} ago)"
                for entry in entries
            ])
            
            try:
                send_mail(
                    subject=f'Missing Clock-Outs: {len(entries)} employee(s)',
                    message=(
                        f"The following employees forgot to clock out:\n\n"
                        f"{entry_list}\n\n"
                        f"Please remind them to clock out or manually adjust their time entries."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    fail_silently=False,
                )
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent alert to {owner.email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send alert: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent alerts: {sent}'))

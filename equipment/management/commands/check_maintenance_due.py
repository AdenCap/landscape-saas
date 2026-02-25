"""Management command to check for equipment maintenance due soon."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from equipment.models import Equipment
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send alerts for equipment maintenance due in the next 7 days'

    def handle(self, *args, **options):
        today = timezone.now().date()
        next_week = today + timedelta(days=7)
        
        equipment_due = Equipment.objects.filter(
            is_active=True,
            next_maintenance_date__lte=next_week,
            next_maintenance_date__gte=today
        ).select_related('business')
        
        if not equipment_due.exists():
            self.stdout.write(self.style.SUCCESS('No maintenance due in the next 7 days'))
            return
        
        # Group by business
        by_business = {}
        for eq in equipment_due:
            if eq.business not in by_business:
                by_business[eq.business] = []
            by_business[eq.business].append(eq)
        
        sent = 0
        for business, equipment_list in by_business.items():
            # Get business owner email
            owner = business.users.filter(role='owner').first()
            if not owner or not owner.email:
                continue
            
            equipment_names = ', '.join([eq.name for eq in equipment_list])
            
            try:
                send_mail(
                    subject=f'Equipment Maintenance Due: {equipment_names}',
                    message=(
                        f"The following equipment is due for maintenance:\n\n"
                        f"{chr(10).join([f'- {eq.name}: Due {eq.next_maintenance_date}' for eq in equipment_list])}\n\n"
                        f"Please schedule maintenance soon."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    fail_silently=False,
                )
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent maintenance alert to {owner.email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send alert: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent alerts: {sent}'))

"""Management command to auto-complete jobs that are in_progress for more than 24 hours."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import Job


class Command(BaseCommand):
    help = 'Auto-complete jobs that have been in_progress for more than 24 hours (safety measure)'

    def handle(self, *args, **options):
        # Find jobs in_progress for more than 24 hours
        # This is a safety measure in case crew forgot to mark jobs complete
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        # We need to track when jobs were started - for now, use updated_at as proxy
        # In production, you might want to add a started_at field
        old_in_progress = Job.objects.filter(
            status='in_progress',
            updated_at__lt=cutoff_time
        ).select_related('property__customer__business')
        
        completed = 0
        skipped = 0
        
        for job in old_in_progress:
            # Skip if completion photos are required but missing
            business = job.property.customer.business if job.property.customer else None
            if business and getattr(business, "require_completion_photo", False):
                if not job.completion_photos.exists():
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f'Skipped job #{job.id} - missing required completion photo'))
                    continue
            
            job.status = 'completed'
            job.save(update_fields=['status'])
            completed += 1
            self.stdout.write(self.style.SUCCESS(f'Auto-completed job #{job.id} at {job.property.address}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nCompleted: {completed}, Skipped: {skipped}'))

"""Management command to cleanup old completion photos (optional maintenance)."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import JobCompletionPhoto
import os


class Command(BaseCommand):
    help = 'Delete completion photos older than specified days (default: 365 days)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete photos older than this many days (default: 365)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_photos = JobCompletionPhoto.objects.filter(captured_at__lt=cutoff_date)
        count = old_photos.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f'No photos older than {days} days found'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would delete {count} photos older than {days} days'))
            return
        
        deleted = 0
        for photo in old_photos:
            try:
                # Delete file if it exists
                if photo.image and os.path.exists(photo.image.path):
                    os.remove(photo.image.path)
                photo.delete()
                deleted += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error deleting photo {photo.id}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} old photos'))

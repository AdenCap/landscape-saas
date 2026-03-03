from django.core.management.base import BaseCommand
from django.utils import timezone

from subscription.models import StripeWebhookEvent
from subscription.handlers import handle_stripe_webhook


class Command(BaseCommand):
    help = "Retry unprocessed Stripe webhook events from stored raw_data"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Max events to retry")

    def handle(self, *args, **options):
        limit = options["limit"]
        qs = StripeWebhookEvent.objects.filter(processed=False).order_by("created_at")[:limit]
        retried = 0
        succeeded = 0
        failed = 0

        for ev in qs:
            retried += 1
            raw = ev.raw_data or {}
            if not isinstance(raw, dict) or "type" not in raw:
                ev.error_message = "Missing/invalid raw_data payload for retry"
                ev.save(update_fields=["error_message", "updated_at"])
                failed += 1
                continue
            try:
                handle_stripe_webhook(raw)
                ev.processed = True
                ev.processed_at = timezone.now()
                ev.error_message = ""
                ev.save(update_fields=["processed", "processed_at", "error_message", "updated_at"])
                succeeded += 1
            except Exception as e:
                ev.error_message = str(e)[:1000]
                ev.save(update_fields=["error_message", "updated_at"])
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Retried={retried} succeeded={succeeded} failed={failed}"))

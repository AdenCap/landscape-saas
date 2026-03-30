"""
Fix mowing JobServiceItem prices that were set to $0 during bulk scheduling.

For each mowing JobServiceItem with unit_price=0:
1. Check PropertyServiceRate for the property override
2. Check RecurringJob service_snapshot for saved price
3. Skip if no price source found (leaves as $0)

Run with: python manage.py fix_mowing_prices
Add --dry-run to preview without saving.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q

from jobs.models import Job, JobServiceItem, RecurringJob
from pricing.models import ServiceTemplate


class Command(BaseCommand):
    help = "Fix $0 mowing prices on scheduled jobs by reading from PropertyServiceRate or RecurringJob snapshot"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Find all mowing services
        mowing_svcs = ServiceTemplate.objects.filter(name__icontains="mow", active=True)
        if not mowing_svcs.exists():
            self.stdout.write(self.style.WARNING("No mowing service templates found."))
            return

        mowing_svc_ids = set(mowing_svcs.values_list("id", flat=True))

        # Find JobServiceItems with mowing service and $0 price
        zero_items = JobServiceItem.objects.filter(
            service_id__in=mowing_svc_ids,
            unit_price=Decimal("0"),
            job__status__in=["scheduled", "en_route"],
        ).select_related("job__property", "service")

        self.stdout.write(f"Found {zero_items.count()} mowing jobs with $0 price")

        fixed = 0
        skipped = 0

        for item in zero_items:
            prop = item.job.property
            svc = item.service
            new_price = None
            source = ""

            # 1. Check PropertyServiceRate
            from pricing.utils import get_effective_rate
            _unit, _rate = get_effective_rate(prop, svc)
            if _rate > 0:
                new_price = _rate
                source = "PropertyServiceRate"

            # 2. Check RecurringJob snapshot
            if not new_price:
                rj = RecurringJob.objects.filter(
                    property=prop, active=True
                ).first()
                if rj and rj.service_snapshot:
                    for snap in rj.service_snapshot:
                        sp = snap.get("unit_price")
                        if sp and Decimal(str(sp)) > 0:
                            new_price = Decimal(str(sp))
                            source = "RecurringJob snapshot"
                            break

            if new_price:
                self.stdout.write(
                    f"  {'[DRY RUN] ' if dry_run else ''}Fix: Job #{item.job.id} "
                    f"({prop.customer.name} - {prop.address}) "
                    f"$0 -> ${new_price} (from {source})"
                )
                if not dry_run:
                    item.unit_price = new_price
                    item.save(update_fields=["unit_price"])
                fixed += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skip: Job #{item.job.id} ({prop.customer.name}) - no price source found"
                    )
                )
                skipped += 1

        action = "Would fix" if dry_run else "Fixed"
        self.stdout.write(
            self.style.SUCCESS(f"\n{action} {fixed} jobs, skipped {skipped}")
        )

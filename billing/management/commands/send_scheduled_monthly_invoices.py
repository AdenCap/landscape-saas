"""
Send scheduled monthly invoices.

Usage (daily, e.g. 9 AM):
  python manage.py send_scheduled_monthly_invoices
  python manage.py send_scheduled_monthly_invoices --dry-run

Behavior:
- Finds draft monthly invoices for current month.
- Sends when day-of-month matches customer.monthly_invoice_send_day,
  or falls back to business.default_monthly_invoice_send_day.
- Marks invoice as sent and sets payment token.
"""

import secrets
from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Invoice, InvoiceAuditLog


class Command(BaseCommand):
    help = "Send scheduled monthly invoices based on customer/business send day settings."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print actions without writing changes")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.localdate()
        sent_count = 0

        invoices = (
            Invoice.objects.select_related("customer", "business")
            .filter(status="draft", job__isnull=True, period_start__year=today.year, period_start__month=today.month)
            .order_by("id")
        )

        for inv in invoices:
            send_day = getattr(inv.customer, "monthly_invoice_send_day", None) or getattr(inv.business, "default_monthly_invoice_send_day", None)
            if not send_day:
                continue
            if int(send_day) != today.day:
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] would send invoice #{inv.id} for {inv.customer.name}")
                sent_count += 1
                continue

            inv.status = "sent"
            if not inv.payment_token:
                inv.payment_token = secrets.token_urlsafe(32)
            inv.approved_at = timezone.now()
            inv.approved_by = None
            inv.save(update_fields=["status", "payment_token", "approved_at", "approved_by"])
            InvoiceAuditLog.objects.create(
                invoice=inv,
                action="approved_sent",
                user=None,
                details={"source": "automation", "trigger": "monthly_schedule"},
            )
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Processed scheduled monthly invoices: {sent_count}"))

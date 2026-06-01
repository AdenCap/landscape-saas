from decimal import Decimal

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand

from billing.models import Invoice
from billing.services import mark_invoice_paid_from_stripe


class Command(BaseCommand):
    help = "Reconcile sent invoices with stored Stripe Checkout Sessions and mark paid sessions as paid."

    def add_arguments(self, parser):
        parser.add_argument("--invoice-id", type=int, help="Only reconcile one invoice.")
        parser.add_argument("--business-id", type=int, help="Only reconcile invoices for one business.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be marked paid without saving.")
        parser.add_argument("--limit", type=int, default=100, help="Maximum invoices to inspect.")

    def handle(self, *args, **options):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        qs = (
            Invoice.objects.select_related("business", "customer")
            .filter(status="sent", stripe_checkout_session_id__isnull=False)
            .exclude(stripe_checkout_session_id="")
            .order_by("-id")
        )
        if options.get("invoice_id"):
            qs = qs.filter(id=options["invoice_id"])
        if options.get("business_id"):
            qs = qs.filter(business_id=options["business_id"])

        inspected = 0
        repaired = 0
        dry_run = options["dry_run"]
        for invoice in qs[: options["limit"]]:
            inspected += 1
            account_id = (invoice.business.stripe_connect_account_id or "").strip()
            if not account_id:
                self.stdout.write(self.style.WARNING(f"Invoice #{invoice.id}: skipped, business has no Stripe account."))
                continue
            try:
                session = stripe.checkout.Session.retrieve(invoice.stripe_checkout_session_id, stripe_account=account_id)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Invoice #{invoice.id}: Stripe lookup failed: {exc}"))
                continue

            if session.get("payment_status") != "paid":
                self.stdout.write(f"Invoice #{invoice.id}: session {session.get('id')} is {session.get('payment_status') or 'unknown'}.")
                continue

            amount = None
            if session.get("amount_total") is not None:
                amount = (Decimal(str(session.get("amount_total"))) / Decimal("100")).quantize(Decimal("0.01"))
            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"Invoice #{invoice.id}: would mark paid from session {session.get('id')} for ${amount or invoice.total}."
                ))
                repaired += 1
                continue

            mark_invoice_paid_from_stripe(
                invoice,
                checkout_session_id=session.get("id", ""),
                payment_intent_id=session.get("payment_intent") or "",
                amount=amount,
                source="stripe_reconciliation",
            )
            repaired += 1
            self.stdout.write(self.style.SUCCESS(f"Invoice #{invoice.id}: marked paid."))

        self.stdout.write(self.style.SUCCESS(f"Inspected {inspected}; {'would repair' if dry_run else 'repaired'} {repaired}."))

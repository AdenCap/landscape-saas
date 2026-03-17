"""
Send automatic payment reminder emails for overdue invoices.

Run daily via cron, e.g.:
  0 10 * * * cd /path/to/project && python manage.py send_invoice_reminders

Only sends for businesses with invoice_reminder_enabled=True. Uses
invoice_reminder_days (comma-separated, e.g. 7,14,21) — sends when
days overdue matches one of those, and no reminder sent in the last 6 days.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings

from billing.models import Invoice
from businesses.models import Business
from businesses.email_sender import send_business_email, is_email_configured


def _parse_reminder_days(s):
    """Return list of int from '7,14,21'."""
    if not s or not s.strip():
        return [7, 14, 21]
    out = []
    for part in s.replace(" ", "").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return sorted(out) if out else [7, 14, 21]


def _build_pay_url(invoice):
    """Build absolute URL for customer pay page."""
    host = getattr(settings, "SITE_DOMAIN", None) or (settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost")
    scheme = getattr(settings, "SITE_SCHEME", "https" if host not in ("localhost", "127.0.0.1") else "http")
    if not invoice.payment_token:
        return ""
    path = reverse("billing:invoice_pay_page", args=[invoice.id, invoice.payment_token])
    return f"{scheme}://{host}{path}"


class Command(BaseCommand):
    help = "Send payment reminder emails for overdue invoices (when reminder days match)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without sending")
        parser.add_argument("--force", action="store_true", help="Bypass owner-approval gate for reminders")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        today = timezone.localdate()

        for business in Business.objects.filter(invoice_reminder_enabled=True):
            if getattr(business, "invoice_reminder_require_owner_approval", True) and not force:
                self.stdout.write(self.style.WARNING(f"Business {business.name}: owner approval gate enabled, skipping (use --force)"))
                continue
            reminder_days = _parse_reminder_days(getattr(business, "invoice_reminder_days", "") or "7,14,21")
            if not is_email_configured(business):
                self.stdout.write(self.style.WARNING(f"Business {business.name}: no email configured, skipping reminders"))
                continue

            invoices = (
                Invoice.objects.filter(
                    business=business,
                    status="sent",
                    due_date__isnull=False,
                    due_date__lt=today,
                )
                .exclude(customer__email__isnull=True)
                .exclude(customer__email="")
                .select_related("customer")
            )

            for invoice in invoices:
                days_overdue = (today - invoice.due_date).days
                if days_overdue not in reminder_days:
                    continue
                if invoice.last_reminder_at:
                    days_since_reminder = (timezone.now() - invoice.last_reminder_at).days
                    if days_since_reminder < 6:
                        continue

                self.stdout.write(
                    f"Would send reminder: Invoice #{invoice.id} to {invoice.customer.email} ({days_overdue} days overdue)"
                    if dry_run
                    else f"Sending reminder: Invoice #{invoice.id} to {invoice.customer.email}"
                )
                if dry_run:
                    continue

                pay_url = _build_pay_url(invoice)
                subject = f"Payment reminder: Invoice #{invoice.id} from {business.name}"
                body_text = (
                    f"Hi {invoice.customer.name},\n\n"
                    f"This is a friendly reminder that Invoice #{invoice.id} (total ${invoice.total}) was due on {invoice.due_date}.\n\n"
                )
                if pay_url:
                    body_text += f"You can pay here: {pay_url}\n\n"
                body_text += f"Thank you,\n{business.name}"

                html_content = render_to_string(
                    "billing/invoice_reminder_email.html",
                    {"invoice": invoice, "business": business, "pay_url": pay_url, "days_overdue": days_overdue},
                )

                ok, detail = send_business_email(
                    business=business,
                    to=invoice.customer.email,
                    subject=subject,
                    body_text=body_text,
                    body_html=html_content,
                )
                if ok:
                    invoice.last_reminder_at = timezone.now()
                    invoice.save(update_fields=["last_reminder_at"])
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to send reminder for invoice #{invoice.id}: {detail}"))

        self.stdout.write(self.style.SUCCESS("Done."))

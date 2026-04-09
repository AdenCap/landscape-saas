"""
Send scheduled monthly invoices.

Usage (daily, e.g. 9 AM):
  python manage.py send_scheduled_monthly_invoices
  python manage.py send_scheduled_monthly_invoices --dry-run

Behavior:
- Finds draft monthly invoices for current month.
- Sends when day-of-month matches customer.monthly_invoice_send_day,
  or falls back to business.default_monthly_invoice_send_day.
- Marks invoice as sent, sets payment token, and emails the customer.
"""

import secrets
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from billing.models import Invoice, InvoiceAuditLog, DocumentTemplate


class Command(BaseCommand):
    help = "Send scheduled monthly invoices based on customer/business send day settings."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print actions without writing changes")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.localdate()
        sent_count = 0
        emailed_count = 0

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

            # Mark as sent
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

            # Send email to customer
            if inv.customer.email:
                emailed = self._send_invoice_email(inv)
                if emailed:
                    emailed_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Processed scheduled monthly invoices: {sent_count} sent, {emailed_count} emailed"
        ))

    def _send_invoice_email(self, invoice):
        """Send the invoice email to the customer. Returns True if sent successfully."""
        from businesses.email_sender import send_business_email, is_email_configured

        business = invoice.business
        if not is_email_configured(business):
            self.stdout.write(self.style.WARNING(
                f"  Invoice #{invoice.id}: email not configured for {business.name}, skipping"
            ))
            return False

        invoice.recompute_totals()

        # Build pay URL using SITE_URL (no request object in management commands)
        site_url = getattr(settings, "SITE_URL", "https://fieldlgx.com").rstrip("/")
        pay_path = reverse("billing:invoice_pay_page", args=[invoice.id, invoice.payment_token])
        pay_url = site_url + pay_path

        customer_name = invoice.customer.name
        business_name = business.name

        # Subject
        subject = f"Invoice #{invoice.id} from {business_name}"
        custom_subject = (business.invoice_email_subject or "").strip()
        if custom_subject:
            subject = (custom_subject
                       .replace("{{invoice_id}}", str(invoice.id))
                       .replace("{{customer_name}}", customer_name)
                       .replace("{{business_name}}", business_name))

        # Intro
        intro = (business.invoice_email_intro or "").strip()
        if not intro:
            intro = f"Hi {customer_name}, please find your invoice from {business_name} below."
        else:
            intro = (intro
                     .replace("{{invoice_id}}", str(invoice.id))
                     .replace("{{customer_name}}", customer_name)
                     .replace("{{business_name}}", business_name))

        # Closing
        closing = (business.invoice_email_closing or "").strip()
        if not closing:
            closing = "Thank you for your business."
        else:
            closing = (closing
                       .replace("{{customer_name}}", customer_name)
                       .replace("{{business_name}}", business_name))

        doc_template = DocumentTemplate.get_default_for_business(business, "invoice")
        accent_color = "#22c55e"
        if doc_template and getattr(doc_template, "primary_color", None):
            accent_color = doc_template.primary_color

        try:
            html_content = render_to_string("billing/invoice_email.html", {
                "invoice": invoice,
                "business": business,
                "pay_url": pay_url,
                "enable_card_payment": invoice.enable_card_payment,
                "logo_url": "",
                "email_intro": intro,
                "email_closing": closing,
                "accent_color": accent_color,
                "template_style": doc_template.template_key if doc_template else "modern_dark",
                "header_text": doc_template.header_text if doc_template else "",
                "footer_text": doc_template.footer_text if doc_template else "",
                "terms_text": doc_template.terms_and_conditions if doc_template else "",
            })
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Invoice #{invoice.id}: template error: {e}"))
            return False

        body_text = (
            f"{intro}\n\n"
            f"Invoice #{invoice.id} · Total: ${invoice.total}\n\n"
            f"{'Pay online' if invoice.enable_card_payment else 'View invoice'}: {pay_url}\n\n"
            f"{closing}\n\n{business_name}"
        )

        reply_to = [business.contact_email] if business.contact_email else None
        ok, detail = send_business_email(
            business=business,
            to=invoice.customer.email,
            subject=subject,
            body_text=body_text,
            body_html=html_content,
            reply_to=reply_to,
        )
        if ok:
            self.stdout.write(f"  Invoice #{invoice.id}: emailed to {invoice.customer.email}")
        else:
            self.stdout.write(self.style.WARNING(f"  Invoice #{invoice.id}: email failed: {detail}"))
        return ok

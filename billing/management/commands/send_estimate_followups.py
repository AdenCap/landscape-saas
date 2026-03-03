"""
Management command to send automatic estimate follow-ups.

Run via cron daily, e.g.:
  0 9 * * * cd /path/to/project && python manage.py send_estimate_followups

Only sends for businesses with estimate_follow_up_days > 0 and estimates
that were sent X+ days ago with no response (not accepted).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings

from billing.models import Estimate
from businesses.models import Business


def _parse_days_csv(s, fallback="3,7,14"):
    raw = (s or fallback or "").replace(" ", "")
    out = []
    for part in raw.split(","):
        if part.isdigit():
            out.append(int(part))
    out = sorted(set(x for x in out if x > 0))
    return out or [3, 7, 14]


def _build_view_url(estimate):
    """Build absolute URL for estimate client view."""
    host = getattr(settings, "SITE_DOMAIN", None) or (settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost")
    scheme = getattr(settings, "SITE_SCHEME", "https" if host not in ("localhost", "127.0.0.1") else "http")
    path = reverse("billing:estimate_client_view", args=[estimate.id, estimate.view_token])
    return f"{scheme}://{host}{path}"


class Command(BaseCommand):
    help = "Send automatic follow-up emails for estimates awaiting response"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        for business in Business.objects.filter(estimate_follow_up_days__gte=0):
            cadence_days = _parse_days_csv(getattr(business, "estimate_follow_up_cadence_days", "") or "")

            estimates = Estimate.objects.filter(
                business=business,
                status="sent",
                sent_at__isnull=False,
                customer__email__isnull=False,
            ).exclude(customer__email="").select_related("customer")

            connection = business.get_smtp_connection()
            if not connection:
                continue

            for estimate in estimates:
                days_since_sent = (timezone.localdate() - estimate.sent_at.date()).days if estimate.sent_at else 0
                if days_since_sent not in cadence_days:
                    continue
                if estimate.last_follow_up_at and (timezone.now() - estimate.last_follow_up_at).days < 2:
                    continue

                self.stdout.write(
                    f"Would send follow-up: Estimate #{estimate.id} to {estimate.customer.email}"
                    if dry_run
                    else f"Sending follow-up: Estimate #{estimate.id} to {estimate.customer.email}"
                )
                if dry_run:
                    continue

                if not estimate.view_token:
                    import secrets
                    estimate.view_token = secrets.token_urlsafe(32)
                    estimate.save(update_fields=["view_token"])

                view_url = _build_view_url(estimate)
                logo_url = None
                if business.logo:
                    try:
                        logo_url = business.logo.url
                    except Exception:
                        pass

                upsells = [x.strip() for x in (getattr(business, "quote_upsell_suggestions", "") or "").splitlines() if x.strip()]
                html_content = render_to_string(
                    "billing/estimate_followup_email.html",
                    {
                        "estimate": estimate,
                        "customer": estimate.customer,
                        "business": business,
                        "view_url": view_url,
                        "logo_url": logo_url,
                        "upsells": upsells,
                    },
                )

                subject = f"Reminder: {estimate.title} - {business.name}"
                from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fieldops.local")
                reply_to = [business.contact_email] if business.contact_email else None

                from django.core.mail import EmailMultiAlternatives
                msg = EmailMultiAlternatives(
                    subject,
                    f"Friendly reminder about your estimate from {business.name}.",
                    from_email,
                    [estimate.customer.email],
                    reply_to=reply_to,
                    connection=connection,
                )
                msg.attach_alternative(html_content, "text/html")

                try:
                    from billing.views import _build_estimate_pdf
                    from io import BytesIO
                    pdf_bytes = _build_estimate_pdf(estimate, business)
                    msg.attach(f"estimate_{estimate.id}.pdf", pdf_bytes, "application/pdf")
                except Exception as e:
                    self.stderr.write(f"  PDF error: {e}")

                try:
                    msg.send()
                    estimate.last_follow_up_at = now
                    estimate.save(update_fields=["last_follow_up_at"])
                    self.stdout.write(self.style.SUCCESS(f"  Sent to {estimate.customer.email}"))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"  Send failed: {e}"))

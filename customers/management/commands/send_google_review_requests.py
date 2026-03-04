import base64
import json
from urllib import parse, request as urlrequest
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils import timezone

from billing.models import InvoiceAuditLog
from businesses.models import Business
from customers.models import ClientMessage, Customer
from customers.views import make_review_action_token


def _base_url():
    host = getattr(settings, "SITE_DOMAIN", None) or (settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost")
    scheme = getattr(settings, "SITE_SCHEME", "https" if host not in ("localhost", "127.0.0.1") else "http")
    return f"{scheme}://{host}"


def _infer_timezone_for_customer(customer):
    state = (getattr(customer, "state", "") or "").strip().upper()
    mapping = {
        "CA": "America/Los_Angeles", "WA": "America/Los_Angeles", "OR": "America/Los_Angeles",
        "AZ": "America/Phoenix", "CO": "America/Denver", "UT": "America/Denver", "NM": "America/Denver",
        "TX": "America/Chicago", "IL": "America/Chicago", "MN": "America/Chicago", "WI": "America/Chicago",
        "NY": "America/New_York", "FL": "America/New_York", "GA": "America/New_York", "NC": "America/New_York",
    }
    return mapping.get(state, "America/New_York")


def _within_customer_hours(customer, start_hour, end_hour, now_utc):
    tz_name = _infer_timezone_for_customer(customer)
    local_hour = now_utc.astimezone(ZoneInfo(tz_name)).hour
    return start_hour <= local_hour < end_hour


def _send_twilio_sms(to_number, body):
    sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "")
    if not (sid and token and from_number):
        return False, "Twilio not configured"

    payload = parse.urlencode({"To": to_number, "From": from_number, "Body": body}).encode()
    req = urlrequest.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=payload,
        method="POST",
    )
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            ok = 200 <= resp.status < 300
            data = resp.read().decode("utf-8", errors="ignore")
            return ok, data[:200]
    except Exception as exc:
        return False, str(exc)


class Command(BaseCommand):
    help = "Send Google review request emails while respecting stop rules (reviewed/opted-out/max attempts)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would send without actually sending")
        parser.add_argument("--max-per-run", type=int, default=200, help="Safety cap for sends per execution")
        parser.add_argument("--start-hour", type=int, default=9, help="Earliest local hour to send (0-23)")
        parser.add_argument("--end-hour", type=int, default=20, help="Latest local hour to send (1-24, exclusive)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        max_per_run = max(1, int(options.get("max_per_run") or 200))
        start_hour = int(options.get("start_hour") or 9)
        end_hour = int(options.get("end_hour") or 20)
        now = timezone.now()
        sent = 0

        if not (0 <= start_hour <= 23 and 1 <= end_hour <= 24 and start_hour < end_hour):
            self.stderr.write(self.style.ERROR("Invalid quiet-hours window. Use start-hour < end-hour."))
            return

        if not (start_hour <= now.hour < end_hour):
            self.stdout.write(self.style.WARNING(
                f"Skipping sends: current local hour {now.hour}:00 outside allowed window {start_hour}:00-{end_hour}:00"
            ))
            return

        for business in Business.objects.filter(google_review_requests_enabled=True).exclude(google_review_link=""):
            connection = business.get_smtp_connection()
            if not connection and not dry_run:
                continue

            max_attempts = max(1, int(business.google_review_max_attempts or 2))
            delay_hours = max(0, int(business.google_review_request_delay_hours or 24))
            followup_days = max(1, int(business.google_review_followup_days or 7))

            paid_cutoff = now - timezone.timedelta(hours=delay_hours)
            followup_cutoff = now - timezone.timedelta(days=followup_days)

            paid_log_exists = InvoiceAuditLog.objects.filter(
                invoice__customer=OuterRef("pk"),
                invoice__business=business,
                action="paid",
                created_at__lte=paid_cutoff,
            )

            candidates = (
                Customer.objects.filter(business=business)
                .exclude(email="")
                .annotate(has_paid_invoice=Exists(paid_log_exists))
                .filter(has_paid_invoice=True)
            )

            candidates = candidates.exclude(google_review_status__in=["reviewed", "opted_out"])\
                .filter(google_review_attempts__lt=max_attempts)

            first_asks = candidates.filter(google_review_status="never_asked")
            followups = candidates.filter(
                google_review_status="asked",
                google_review_last_prompt_at__lte=followup_cutoff,
            )

            for customer in first_asks.union(followups):
                if sent >= max_per_run:
                    self.stdout.write(self.style.WARNING(f"Reached --max-per-run cap ({max_per_run}). Stopping."))
                    break
                if not _within_customer_hours(customer, start_hour, end_hour, now):
                    continue

                done_token = make_review_action_token(customer.id, "done")
                optout_token = make_review_action_token(customer.id, "optout")
                done_url = f"{_base_url()}{reverse('review_mark_done', args=[done_token])}"
                optout_url = f"{_base_url()}{reverse('review_opt_out', args=[optout_token])}"

                subject = f"Quick favor? Share your experience with {business.name}"
                text_body = (
                    f"Hi {customer.name},\n\n"
                    f"Thanks again for working with {business.name}. If you have 30 seconds, we'd really appreciate a Google review:\n"
                    f"{business.google_review_link}\n\n"
                    f"Already left a review? Confirm here and we'll stop reminders: {done_url}\n"
                    f"Don't want reminders? Opt out here: {optout_url}\n"
                )
                html_body = (
                    f"<p>Hi {customer.name},</p>"
                    f"<p>Thanks again for working with <strong>{business.name}</strong>. If you have 30 seconds, we'd really appreciate a Google review.</p>"
                    f"<p><a href=\"{business.google_review_link}\">Leave a Google Review</a></p>"
                    f"<p style=\"font-size:13px;color:#555;\">Already left one? <a href=\"{done_url}\">Click here so we stop reminders</a>.<br>"
                    f"Prefer not to receive review reminders? <a href=\"{optout_url}\">Opt out</a>.</p>"
                )

                sms_body = (
                    (business.google_review_sms_template or "").strip()
                    or "Hi {{customer_name}}, thanks for choosing {{business_name}}. Could you leave us a quick Google review? {{review_link}}"
                )
                sms_body = sms_body.replace("{{customer_name}}", customer.name or "there")
                sms_body = sms_body.replace("{{business_name}}", business.name or "our team")
                sms_body = sms_body.replace("{{review_link}}", business.google_review_link)

                if dry_run:
                    self.stdout.write(f"Would send review request to {customer.email or customer.phone} ({customer.name})")
                    sent += 1
                    continue

                sent_via_any = False
                if customer.email and connection:
                    msg = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                        to=[customer.email],
                        reply_to=[business.contact_email] if business.contact_email else None,
                        connection=connection,
                    )
                    msg.attach_alternative(html_body, "text/html")
                    try:
                        msg.send()
                        sent_via_any = True
                    except Exception as exc:
                        self.stderr.write(self.style.ERROR(f"Failed email to {customer.email}: {exc}"))

                if business.google_review_sms_enabled and customer.phone:
                    ok, info = _send_twilio_sms(customer.phone, sms_body)
                    if ok:
                        sent_via_any = True
                    else:
                        self.stderr.write(self.style.ERROR(f"Failed SMS to {customer.phone}: {info}"))

                if not sent_via_any:
                    continue

                customer.google_review_status = "asked"
                customer.google_review_attempts += 1
                customer.google_review_last_prompt_at = now
                if customer.google_review_requested_at is None:
                    customer.google_review_requested_at = now
                customer.save(update_fields=[
                    "google_review_status",
                    "google_review_attempts",
                    "google_review_last_prompt_at",
                    "google_review_requested_at",
                    "updated_at",
                ])

                ClientMessage.objects.create(
                    customer=customer,
                    channel=ClientMessage.CHANNEL_EMAIL if customer.email else ClientMessage.CHANNEL_SMS,
                    direction=ClientMessage.DIRECTION_SENT,
                    subject=subject if customer.email else "",
                    body="Google review request sent.",
                    to_address=customer.email or customer.phone,
                )

                sent += 1
                self.stdout.write(self.style.SUCCESS(f"Sent review request to {customer.email}"))

        mode = "Would send" if dry_run else "Sent"
        self.stdout.write(self.style.SUCCESS(f"Done. {mode} {sent} Google review request email(s)."))

"""
Client notification engine.

Sends automated SMS/email notifications to customers based on job lifecycle events.
Respects per-customer communication_preference and per-business notification toggles.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .sms import send_sms, is_sms_configured

logger = logging.getLogger(__name__)

# Maps event_type → business toggle field name
_TOGGLE_MAP = {
    "job_scheduled": "notify_job_scheduled",
    "crew_en_route": "notify_crew_en_route",
    "job_completed": "notify_job_completed",
}

# Maps event_type → business template field name
_TEMPLATE_MAP = {
    "job_scheduled": "template_job_scheduled",
    "crew_en_route": "template_crew_en_route",
    "job_completed": "template_job_completed",
}


def _build_service_list(job):
    """Return comma-separated service names for a job."""
    services = list(job.services.values_list("service__name", flat=True))
    return ", ".join(services) if services else "your service"


def _get_crew_name(job):
    """Return crew/tech first name or fallback."""
    if job.assigned_to:
        return job.assigned_to.first_name or job.assigned_to.get_full_name() or "our crew"
    if job.assigned_crew:
        return job.assigned_crew.name or "our crew"
    return "our crew"


def _render_template(template_str, context):
    """Simple {{variable}} replacement."""
    result = template_str
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def _build_context(job, business):
    """Build template context dict from job and business."""
    customer = job.property.customer
    scheduled_date = ""
    scheduled_time = ""
    if job.scheduled_date:
        scheduled_date = job.scheduled_date.strftime("%A, %B %-d")
    if job.scheduled_time:
        scheduled_time = job.scheduled_time.strftime("%-I:%M %p")

    return {
        "customer_name": customer.name.split()[0] if customer.name else "there",
        "business_name": business.name or "our team",
        "service_list": _build_service_list(job),
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time or "TBD",
        "crew_name": _get_crew_name(job),
    }


def notify_customer(customer, event_type, context_overrides=None, business=None, job=None):
    """
    Send notification to customer based on their communication_preference.

    Args:
        customer: Customer instance
        event_type: "job_scheduled", "crew_en_route", "job_completed"
        context_overrides: Optional dict to override/extend template context
        business: Business instance (auto-detected from customer if None)
        job: Job instance (required for auto-building context)

    Returns:
        bool: True if at least one notification was sent
    """
    from customers.models import ClientMessage

    if not business:
        business = customer.business

    # Check business-level toggle
    toggle_field = _TOGGLE_MAP.get(event_type)
    if toggle_field and not getattr(business, toggle_field, True):
        logger.debug("Notification %s disabled for business %s", event_type, business.name)
        return False

    # Check customer preference
    pref = (customer.communication_preference or "").strip().lower()
    # If no preference set, default to whatever channels are available
    send_email = pref in ("email", "both", "")
    send_sms_flag = pref in ("sms", "both", "")

    # Build message body from template
    template_field = _TEMPLATE_MAP.get(event_type, "")
    template_str = getattr(business, template_field, "") if template_field else ""
    if not template_str:
        logger.debug("No template for %s on business %s", event_type, business.name)
        return False

    # Build context
    if job:
        ctx = _build_context(job, business)
    else:
        ctx = {
            "customer_name": customer.name.split()[0] if customer.name else "there",
            "business_name": business.name or "our team",
        }
    if context_overrides:
        ctx.update(context_overrides)

    body = _render_template(template_str, ctx)
    sent_any = False

    # ── SMS ──
    if send_sms_flag:
        phone = customer.phone or customer.alt_phone or ""
        if phone and is_sms_configured(business):
            ok, detail = send_sms(phone, body, business=business)
            if ok:
                sent_any = True
                ClientMessage.objects.create(
                    customer=customer,
                    channel="sms",
                    direction=ClientMessage.DIRECTION_SENT,
                    subject="",
                    body=body,
                    to_address=phone,
                )
                logger.info("Sent %s SMS to %s (%s)", event_type, customer.name, phone)
            else:
                logger.warning("Failed %s SMS to %s: %s", event_type, customer.name, detail)

    # ── Email ──
    if send_email:
        email_addr = customer.email or ""
        if email_addr:
            from businesses.email_sender import send_business_email, is_email_configured
            if is_email_configured(business):
                subject_map = {
                    "job_scheduled": f"Your service is scheduled — {business.name}",
                    "crew_en_route": f"Your crew is on the way — {business.name}",
                    "job_completed": f"Service complete — {business.name}",
                }
                subject = subject_map.get(event_type, f"Update from {business.name}")
                reply_to = [business.contact_email] if business.contact_email else None

                # Build simple HTML version
                html_body = f"<p>{body.replace(chr(10), '<br>')}</p>"

                # For job_completed, optionally include completion photos
                if event_type == "job_completed" and business.notify_include_completion_photos and job:
                    photos = list(job.completion_photos.all()[:4])
                    if photos:
                        html_body += '<p style="margin-top:16px;"><strong>Completion photos:</strong></p>'
                        for photo in photos:
                            if photo.image and hasattr(photo.image, "url"):
                                html_body += (
                                    f'<p><img src="{photo.image.url}" '
                                    f'style="max-width:400px;border-radius:8px;" '
                                    f'alt="Completion photo"></p>'
                                )

                ok, detail = send_business_email(
                    business=business,
                    to=email_addr,
                    subject=subject,
                    body_text=body,
                    body_html=html_body,
                    reply_to=reply_to,
                )
                if ok:
                    sent_any = True
                    ClientMessage.objects.create(
                        customer=customer,
                        channel="email",
                        direction=ClientMessage.DIRECTION_SENT,
                        subject=subject,
                        body=body,
                        to_address=email_addr,
                    )
                    logger.info("Sent %s email to %s (%s)", event_type, customer.name, email_addr)
                else:
                    logger.error("Failed %s email to %s: %s", event_type, customer.name, detail)

    return sent_any

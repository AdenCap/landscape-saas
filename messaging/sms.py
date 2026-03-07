"""Twilio SMS utility — reusable send_sms() for the entire platform.

Usage:
    from messaging.sms import send_sms
    send_sms(business, "+15551234567", "Your appointment is confirmed!", purpose="booking_confirm")
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(business, to_phone, body, purpose="other"):
    """Send an SMS via Twilio and log it.

    Returns the SMSLog instance (always created, even on failure).
    If Twilio is not configured, the message is logged as failed with a note.
    """
    from .models import SMSLog

    log = SMSLog(
        business=business,
        to_phone=to_phone,
        body=body,
        purpose=purpose,
    )

    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_phone = getattr(settings, "TWILIO_FROM_NUMBER", "")

    if not all([account_sid, auth_token, from_phone]):
        log.status = "failed"
        log.error_message = "Twilio not configured (missing credentials)."
        log.save()
        logger.warning("SMS not sent — Twilio not configured. To: %s", to_phone)
        return log

    log.from_phone = from_phone

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=from_phone,
            to=to_phone,
        )
        log.twilio_sid = message.sid
        log.status = "sent"
    except ImportError:
        log.status = "failed"
        log.error_message = "twilio package not installed (pip install twilio)."
        logger.error("SMS failed — twilio package not installed.")
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)[:500]
        logger.error("SMS failed to %s: %s", to_phone, exc)

    log.save()
    return log

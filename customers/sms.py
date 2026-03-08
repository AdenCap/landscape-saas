"""
Shared Twilio SMS utility.

Sends SMS via the Twilio REST API using raw urllib (no SDK needed).
Uses global TWILIO_* settings from Django config / environment variables.
"""
import base64
import logging
from urllib import parse, request as urlrequest

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_twilio_credentials():
    """Return (sid, token, from_number) from global Django settings."""
    sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_num = getattr(settings, "TWILIO_FROM_NUMBER", "")
    return sid, token, from_num


def is_sms_configured(**_kwargs):
    """Check if Twilio credentials are configured."""
    sid, token, from_num = _get_twilio_credentials()
    return bool(sid and token and from_num)


def send_sms(to_number, body, **_kwargs):
    """
    Send SMS via Twilio REST API.

    Args:
        to_number: Recipient phone number (E.164 format preferred).
        body: SMS message body.

    Returns:
        (success: bool, detail: str)
    """
    sid, token, from_number = _get_twilio_credentials()
    if not (sid and token and from_number):
        return False, "Twilio not configured"

    payload = parse.urlencode({
        "To": to_number,
        "From": from_number,
        "Body": body,
    }).encode()

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
            if ok:
                logger.info("SMS sent to %s via Twilio", to_number)
            else:
                logger.warning("Twilio SMS failed (%s): %s", resp.status, data[:200])
            return ok, data[:200]
    except Exception as exc:
        logger.error("Twilio SMS exception to %s: %s", to_number, exc)
        return False, str(exc)

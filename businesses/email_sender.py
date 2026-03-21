"""
Unified email sending for the platform.

Tries Gmail OAuth first (zero-config for users who sign in with Google),
then falls back to SMTP App Password if OAuth is unavailable.

Usage:
    from businesses.email_sender import send_business_email, get_email_connection

    # Simple: send a single email (handles OAuth vs SMTP internally)
    ok, detail = send_business_email(
        business=business,
        to="client@example.com",
        subject="Your invoice",
        body_text="Plain text version",
        body_html="<p>HTML version</p>",
    )

    # Advanced: get a connection object for batch sending (SMTP-style)
    connection = get_email_connection(business)
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


def _get_business_owner(business):
    """Return the owner User for this business, or None."""
    try:
        return business.users.filter(role="owner").first()
    except Exception:
        return None


def _is_oauth_available(business):
    """Check if Gmail OAuth is available for this business's owner."""
    from .gmail_oauth import gmail_oauth_available
    owner = _get_business_owner(business)
    if not owner:
        return False
    return gmail_oauth_available(owner)


def _send_via_oauth(business, to, subject, body_text, body_html=None,
                    reply_to=None, attachments=None):
    """
    Attempt to send via Gmail OAuth API.
    Returns (True, detail) on success, (False, detail) on failure.
    """
    from .gmail_oauth import send_email_oauth

    owner = _get_business_owner(business)
    if not owner:
        return False, "No owner found for business"

    from_email = business.get_from_email() or getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@fieldlgx.com"
    )

    return send_email_oauth(
        user=owner,
        from_email=from_email,
        to_email=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        reply_to=reply_to,
        attachments=attachments,
    )


def _send_via_smtp(business, to, subject, body_text, body_html=None,
                   reply_to=None, attachments=None):
    """
    Send via SMTP (App Password).
    Returns (True, detail) on success, (False, detail) on failure.
    """
    connection = business.get_smtp_connection()
    if not connection:
        return False, "SMTP not configured"

    from_email = business.get_from_email() or getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@fieldlgx.com"
    )

    if isinstance(reply_to, str):
        reply_to = [reply_to]

    to_list = [to] if isinstance(to, str) else list(to)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=to_list,
        reply_to=reply_to,
        connection=connection,
    )
    if body_html:
        msg.attach_alternative(body_html, "text/html")

    if attachments:
        for att in attachments:
            msg.attach(
                att.get("filename", "attachment"),
                att.get("content", b""),
                att.get("mimetype", "application/octet-stream"),
            )

    try:
        msg.send()
        return True, "sent_smtp"
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        return False, str(exc)


def send_business_email(business, to, subject, body_text, body_html=None,
                        reply_to=None, attachments=None):
    """
    Send an email from this business. Tries OAuth first, falls back to SMTP.

    Args:
        business: Business instance
        to: recipient email (str) or list of emails
        subject: email subject line
        body_text: plain-text body
        body_html: optional HTML body
        reply_to: optional reply-to address (str or list)
        attachments: optional list of dicts with keys:
            - filename (str)
            - content (bytes)
            - mimetype (str, optional, default "application/octet-stream")

    Returns:
        (success: bool, detail: str)
        detail is "sent_oauth", "sent_smtp", or an error message.
    """
    oauth_error = None

    # Try OAuth first
    if _is_oauth_available(business):
        ok, detail = _send_via_oauth(
            business, to, subject, body_text, body_html, reply_to, attachments
        )
        if ok:
            return True, "sent_oauth"
        oauth_error = detail
        logger.warning("OAuth send failed (%s), falling back to SMTP", detail)

    # Fall back to SMTP
    ok, detail = _send_via_smtp(
        business, to, subject, body_text, body_html, reply_to, attachments
    )
    if ok:
        return True, detail

    # Both failed — surface the most informative error.
    # When SMTP simply isn't configured (no App Password set up), the real
    # problem is the OAuth failure.  Return that error so the user knows
    # *why* Gmail didn't work instead of seeing a confusing "SMTP not configured".
    if oauth_error and detail == "SMTP not configured":
        return False, f"gmail_oauth_error:{oauth_error}"
    return False, detail


def get_email_connection(business):
    """
    Return an email connection for this business (SMTP-style).

    For batch sends that use Django's EmailMultiAlternatives directly
    (e.g. mass communications), this returns the SMTP connection.
    OAuth is used at the individual send level via send_business_email().

    Returns:
        Django email backend connection, or None if not configured.
    """
    # For now, batch sending still uses SMTP connection
    # Individual sends via send_business_email() will prefer OAuth
    return business.get_smtp_connection()


def format_send_error(detail):
    """
    Convert an internal send-error detail string into a user-friendly message.
    Handles the 'gmail_oauth_error:...' tag returned when OAuth fails and SMTP
    is not configured, so the real Gmail error is shown instead of "SMTP not configured".
    """
    if detail.startswith("gmail_oauth_error:"):
        inner = detail[len("gmail_oauth_error:"):]
        if any(kw in inner.lower() for kw in ("insufficient", "scope", "permission", "forbidden")):
            return (
                "Gmail is connected but doesn't have send permission. "
                "Go to Settings → Email tab and click 'Connect Gmail' to reconnect with send access."
            )
        return f"Gmail send failed: {inner}. Go to Settings → Email tab and reconnect Gmail."
    return f"Could not send email: {detail}"


def is_email_configured(business):
    """
    Check if email sending is available for this business
    (either via OAuth or SMTP App Password).
    """
    if _is_oauth_available(business):
        return True
    conn = business.get_smtp_connection()
    return conn is not None


def email_diagnostic(business):
    """
    Return a human-readable diagnostic of the email configuration.
    Useful for showing actionable error messages when sending fails.

    Returns:
        dict with keys: configured (bool), oauth_status (str), smtp_status (str), message (str)
    """
    owner = _get_business_owner(business)
    oauth_ok = False
    oauth_status = "Not connected"
    smtp_ok = False
    smtp_status = "Not configured"

    # Check OAuth
    if owner:
        try:
            from allauth.socialaccount.models import SocialAccount
            has_google = SocialAccount.objects.filter(user=owner, provider="google").exists()
            if has_google:
                from .gmail_oauth import gmail_oauth_available
                if gmail_oauth_available(owner):
                    oauth_ok = True
                    oauth_status = "Connected"
                else:
                    oauth_status = "Google account linked but Gmail permission not granted. Reconnect Gmail in Settings."
            else:
                oauth_status = "No Google account linked"
        except Exception:
            oauth_status = "Could not check"

    # Check SMTP
    if business.email_smtp_user:
        if business.email_smtp_password:
            smtp_ok = True
            smtp_status = f"Configured ({business.email_smtp_user})"
        else:
            smtp_status = f"Gmail address set ({business.email_smtp_user}) but App Password is missing"
    else:
        smtp_status = "Not configured"

    configured = oauth_ok or smtp_ok

    if configured:
        method = "Gmail OAuth" if oauth_ok else "SMTP App Password"
        message = f"Email is configured via {method}."
    else:
        message = "Email is not set up. Go to Settings and either connect your Gmail account or enter a Gmail App Password."

    return {
        "configured": configured,
        "oauth_ok": oauth_ok,
        "oauth_status": oauth_status,
        "smtp_ok": smtp_ok,
        "smtp_status": smtp_status,
        "message": message,
    }

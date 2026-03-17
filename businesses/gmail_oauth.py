"""
Gmail OAuth sending utility.

Uses the stored Google OAuth tokens from django-allauth to send emails via
the Gmail API — no App Password required.  If the access token has expired
the refresh token is used to obtain a new one automatically.
"""
import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports so the module can be imported even when the packages are not
# installed (graceful degradation).
# ---------------------------------------------------------------------------
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    _GMAIL_API_AVAILABLE = True
except ImportError:
    _GMAIL_API_AVAILABLE = False


def _get_google_social_token(user):
    """
    Return the allauth SocialToken for the given user's Google account,
    or None if not found.
    """
    try:
        from allauth.socialaccount.models import SocialAccount, SocialToken
    except ImportError:
        return None

    try:
        social_account = SocialAccount.objects.get(user=user, provider="google")
        token = SocialToken.objects.filter(account=social_account).order_by("-id").first()
        return token
    except SocialAccount.DoesNotExist:
        return None


def _refresh_token_if_needed(social_token):
    """
    Check if the token is expired and refresh it using the refresh_token.
    Updates the SocialToken in the database with the new access_token.
    Returns True if the token is usable, False otherwise.
    """
    if not social_token or not social_token.token:
        return False

    # Check if expired (allauth stores token_secret = refresh_token for Google)
    if social_token.expires_at and social_token.expires_at <= timezone.now():
        refresh_token = social_token.token_secret
        if not refresh_token:
            logger.warning("Gmail OAuth token expired and no refresh token available")
            return False

        try:
            from google.auth.transport.requests import Request

            creds = Credentials(
                token=social_token.token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
                    .get("APP", {}).get("client_id", ""),
                client_secret=settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
                    .get("APP", {}).get("secret", ""),
            )
            creds.refresh(Request())

            # Persist the refreshed token
            social_token.token = creds.token
            if creds.expiry:
                social_token.expires_at = creds.expiry
            social_token.save(update_fields=["token", "expires_at"])
            logger.info("Gmail OAuth token refreshed successfully")
            return True

        except Exception as exc:
            logger.error("Failed to refresh Gmail OAuth token: %s", exc)
            return False

    return True  # token still valid


def get_gmail_service(user):
    """
    Build and return an authenticated Gmail API service for *user*.
    Returns None if OAuth tokens are unavailable or invalid.
    """
    if not _GMAIL_API_AVAILABLE:
        logger.debug("google-api-python-client not installed; Gmail OAuth unavailable")
        return None

    social_token = _get_google_social_token(user)
    if not social_token:
        return None

    if not _refresh_token_if_needed(social_token):
        return None

    creds = Credentials(
        token=social_token.token,
        refresh_token=social_token.token_secret,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
            .get("APP", {}).get("client_id", ""),
        client_secret=settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
            .get("APP", {}).get("secret", ""),
    )

    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return service
    except Exception as exc:
        logger.error("Failed to build Gmail API service: %s", exc)
        return None


def _build_mime_message(from_email, to_email, subject, body_text,
                        body_html=None, reply_to=None, attachments=None):
    """Build a MIME message suitable for the Gmail API."""
    if body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
    else:
        msg = MIMEText(body_text, "plain")

    msg["From"] = from_email
    msg["To"] = to_email if isinstance(to_email, str) else ", ".join(to_email)
    msg["Subject"] = subject
    if reply_to:
        if isinstance(reply_to, (list, tuple)):
            msg["Reply-To"] = ", ".join(reply_to)
        else:
            msg["Reply-To"] = reply_to

    # Attachments
    if attachments:
        # Wrap in mixed multipart if we have attachments
        outer = MIMEMultipart("mixed")
        outer["From"] = msg["From"]
        outer["To"] = msg["To"]
        outer["Subject"] = msg["Subject"]
        if msg.get("Reply-To"):
            outer["Reply-To"] = msg["Reply-To"]
        # Remove headers from inner msg to avoid duplication
        for key in ("From", "To", "Subject", "Reply-To"):
            if key in msg:
                del msg[key]
        outer.attach(msg)
        for attachment in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment["content"])
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{attachment["filename"]}"',
            )
            outer.attach(part)
        msg = outer

    return msg


def send_email_oauth(user, from_email, to_email, subject, body_text,
                     body_html=None, reply_to=None, attachments=None):
    """
    Send an email via the Gmail API using the user's OAuth tokens.

    Args:
        user: Django User instance (owner of the business)
        from_email: "Business Name <email@gmail.com>" or plain email
        to_email: recipient email address (str or list)
        subject: email subject
        body_text: plain text body
        body_html: optional HTML body
        reply_to: optional reply-to address (str or list)
        attachments: optional list of dicts [{"filename": "...", "content": bytes}]

    Returns:
        (success: bool, detail: str)
    """
    service = get_gmail_service(user)
    if not service:
        return False, "Gmail OAuth service not available"

    try:
        mime_msg = _build_mime_message(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=reply_to,
            attachments=attachments,
        )
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        msg_id = result.get("id", "unknown")
        logger.info("Email sent via Gmail OAuth (message id: %s)", msg_id)
        return True, msg_id
    except Exception as exc:
        logger.error("Gmail OAuth send failed: %s", exc)
        return False, str(exc)


def gmail_oauth_available(user):
    """
    Quick check: does this user have a Google social account with
    a stored token (i.e. can we attempt Gmail OAuth sending)?
    """
    if not _GMAIL_API_AVAILABLE:
        return False
    token = _get_google_social_token(user)
    return token is not None and bool(token.token)

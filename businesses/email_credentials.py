"""
Encrypt/decrypt Gmail App Password at rest so it is not stored in plain text.
Uses Fernet (symmetric) with a key derived from Django SECRET_KEY.
Requires: pip install cryptography
"""
import base64
import hashlib

from django.conf import settings

try:
    from cryptography.fernet import Fernet, InvalidToken
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False


def _get_fernet():
    """Fernet instance from SECRET_KEY. Key is SHA256(SECRET_KEY) base64url-encoded."""
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_password(plain: str) -> str:
    """Encrypt a plain-text password for storage. Returns encrypted bytes as base64 string."""
    if not plain:
        return ""
    if not _FERNET_AVAILABLE:
        return plain
    try:
        f = _get_fernet()
        return f.encrypt(plain.encode()).decode()
    except Exception:
        return plain  # fallback: store as-is if encryption fails


def decrypt_password(stored: str) -> str:
    """
    Decrypt a stored value back to plain password.
    If the value is not encrypted (legacy plain text), returns it as-is.
    """
    if not stored:
        return ""
    if not _FERNET_AVAILABLE:
        return stored
    try:
        f = _get_fernet()
        return f.decrypt(stored.encode()).decode()
    except (InvalidToken, Exception):
        return stored  # legacy: was stored in plain text

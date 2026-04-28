import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MobileDeviceSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_sessions")
    business = models.ForeignKey("businesses.Business", on_delete=models.CASCADE, related_name="mobile_sessions")
    device_name = models.CharField(max_length=120, blank=True)
    platform = models.CharField(max_length=20, default="ios")
    refresh_token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

    @classmethod
    def issue(cls, user, device_name="", platform="ios"):
        raw_refresh = secrets.token_urlsafe(48)
        session = cls.objects.create(
            user=user,
            business=user.business,
            device_name=(device_name or "")[:120],
            platform=(platform or "ios")[:20],
            refresh_token_hash=hash_token(raw_refresh),
        )
        return session, raw_refresh

    @property
    def is_active(self):
        return self.revoked_at is None

    def revoke(self):
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

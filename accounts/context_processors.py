"""Context processors for accounts app."""
from .models import Notification


def notification_unread_count(request):
    """Add notification_unread_count for authenticated users (for nav badge)."""
    if request.user.is_authenticated:
        return {
            "notification_unread_count": Notification.objects.filter(
                to_user=request.user, read_at__isnull=True
            ).count(),
        }
    return {"notification_unread_count": 0}

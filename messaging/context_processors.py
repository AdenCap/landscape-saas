"""Context processors for the messaging app."""
from django.conf import settings as django_settings
from django.db.models import Q


def messaging_unread_count(request):
    """Add messaging_unread_count for authenticated users (for floating chat badge).

    Uses the same efficient 2-query approach as the unread_count API view:
    one query for memberships, one COUNT with combined Q objects.
    """
    if not request.user.is_authenticated:
        return {"messaging_unread_count": 0}

    from .models import ConversationMember, Message

    memberships = list(
        ConversationMember.objects.filter(user=request.user)
        .values("conversation_id", "last_read_at")
    )

    if not memberships:
        return {"messaging_unread_count": 0}

    q = Q()
    for m in memberships:
        conv_q = Q(conversation_id=m["conversation_id"])
        if m["last_read_at"]:
            conv_q &= Q(created_at__gt=m["last_read_at"])
        q |= conv_q

    count = (
        Message.objects
        .filter(q, is_deleted=False)
        .exclude(sender=request.user)
        .count()
    )

    return {
        "messaging_unread_count": count,
        "supabase_project_url": getattr(django_settings, "SUPABASE_PROJECT_URL", ""),
        "supabase_anon_key": getattr(django_settings, "SUPABASE_ANON_KEY", ""),
    }

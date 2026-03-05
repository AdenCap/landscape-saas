"""
Plain serialization helpers for the messaging app.

These are simple functions that convert model instances to dicts
suitable for use with Django's JsonResponse.  No DRF dependency.
"""

from .models import ConversationMember, MessageAttachment


def _user_display(user):
    """Return a consistent {id, name} dict for a User instance."""
    return {
        "id": user.id,
        "name": user.get_full_name() or user.username,
    }


def _iso(dt):
    """Return an ISO 8601 string for a datetime, or None."""
    return dt.isoformat() if dt else None


# ------------------------------------------------------------------
# Conversation
# ------------------------------------------------------------------

def serialize_conversation(conversation, for_user, *, membership=None,
                           last_message=None, last_message_loaded=False):
    """Serialize a Conversation to a plain dict.

    Parameters
    ----------
    conversation : Conversation
        The conversation instance.
    for_user : User
        The user who is viewing the conversation (used for display title,
        unread count, and mute state).
    membership : ConversationMember | None, optional
        Pre-fetched membership for *for_user* in this conversation.
        If ``None``, one DB query will be issued to look it up.
    last_message : Message | None, optional
        Pre-fetched last message for the conversation.  Only used when
        *last_message_loaded* is True.
    last_message_loaded : bool, optional
        When True the *last_message* kwarg is treated as authoritative
        (even if it is None, meaning no messages exist).  When False
        the function will query for the latest message itself.
    """
    ctype = conversation.conversation_type

    # -- title --
    if ctype == "direct":
        other_member = (
            ConversationMember.objects
            .filter(conversation=conversation)
            .exclude(user=for_user)
            .select_related("user")
            .first()
        )
        title = _user_display(other_member.user)["name"] if other_member else "Direct Message"
    elif ctype == "crew":
        crew = getattr(conversation, "crew", None)
        title = crew.name if crew else (conversation.title or "Crew Chat")
    else:  # broadcast
        title = "All Employees"

    # -- crew color --
    crew_color = None
    if ctype == "crew":
        crew = getattr(conversation, "crew", None)
        if crew:
            crew_color = crew.color

    # -- last message --
    if not last_message_loaded:
        last_message = (
            conversation.messages
            .filter(is_deleted=False)
            .select_related("sender")
            .order_by("-created_at")
            .first()
        )

    # -- membership / muted --
    if membership is None:
        membership = (
            ConversationMember.objects
            .filter(conversation=conversation, user=for_user)
            .first()
        )
    is_muted = membership.is_muted if membership else False

    return {
        "id": conversation.id,
        "type": ctype,
        "title": title,
        "crew_color": crew_color,
        "last_message": serialize_message(last_message, include_attachments=False) if last_message else None,
        "unread_count": conversation.unread_count_for(for_user),
        "updated_at": _iso(conversation.updated_at),
        "is_muted": is_muted,
    }


# ------------------------------------------------------------------
# Message
# ------------------------------------------------------------------

def serialize_message(message, include_attachments=True):
    """Serialize a Message to a plain dict.

    Parameters
    ----------
    message : Message
        The message instance.
    include_attachments : bool, optional
        When True (the default) attachments are included in the output.
        Set to False when embedding inside a conversation summary to
        keep payloads small.
    """
    if message.is_deleted:
        content = "This message was deleted"
        attachments = []
    else:
        content = message.content
        if include_attachments:
            attachments = [
                serialize_attachment(a)
                for a in message.attachments.all()
            ]
        else:
            attachments = []

    data = {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender": _user_display(message.sender),
        "content": content,
        "created_at": _iso(message.created_at),
        "is_deleted": message.is_deleted,
        "edited_at": _iso(message.edited_at),
    }

    if include_attachments and not message.is_deleted:
        data["attachments"] = attachments

    return data


# ------------------------------------------------------------------
# Attachment
# ------------------------------------------------------------------

def serialize_attachment(attachment):
    """Serialize a MessageAttachment to a plain dict."""
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "file_size": attachment.file_size,
        "content_type": attachment.content_type,
        "url": attachment.file.url,
    }


# ------------------------------------------------------------------
# Read receipt
# ------------------------------------------------------------------

def serialize_read_receipt(receipt):
    """Serialize a MessageReadReceipt to a plain dict."""
    return {
        "user": _user_display(receipt.user),
        "read_at": _iso(receipt.read_at),
    }

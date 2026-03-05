import json
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.utils import get_business
from jobs.models import Crew

from .models import (
    Conversation,
    ConversationMember,
    Message,
    MessageAttachment,
    MessageReadReceipt,
)
from .permissions import (
    can_access_conversation,
    can_create_broadcast,
    can_delete_message,
    can_message_user,
    get_messageable_users,
)
from .serializers import (
    serialize_conversation,
    serialize_message,
    serialize_read_receipt,
)

User = get_user_model()

PAGE_SIZE = 50


# ------------------------------------------------------------------
# Conversations: list & create
# ------------------------------------------------------------------


@login_required
@require_http_methods(["GET", "POST"])
def conversation_list_or_create(request):
    """GET  -> list conversations for the current user.
    POST -> create (or find existing) conversation.
    """
    if request.method == "GET":
        return _list_conversations(request)
    return _create_conversation(request)


def _list_conversations(request):
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    user = request.user
    qs = (
        Conversation.objects
        .filter(business=business)
        .select_related("crew")
        .prefetch_related("members__user")
        .order_by("-updated_at")
    )

    # Crew role: only conversations they belong to
    if user.role not in ("owner", "manager"):
        qs = qs.filter(members__user=user)

    conversations = [
        serialize_conversation(c, user)
        for c in qs
    ]
    return JsonResponse({"conversations": conversations})


def _create_conversation(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    conv_type = data.get("type")
    user = request.user

    if conv_type == "direct":
        return _create_direct(request, data, business, user)
    elif conv_type == "crew":
        return _create_crew(request, data, business, user)
    elif conv_type == "broadcast":
        return _create_broadcast_conversation(request, business, user)
    else:
        return JsonResponse({"error": "Invalid conversation type"}, status=400)


def _create_direct(request, data, business, user):
    recipient_id = data.get("user_id")
    if not recipient_id:
        return JsonResponse({"error": "user_id is required"}, status=400)

    try:
        recipient = User.objects.get(pk=recipient_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    if not can_message_user(user, recipient):
        return JsonResponse({"error": "You cannot message this user"}, status=403)

    # Look for an existing direct conversation between these two users
    existing = (
        Conversation.objects
        .filter(
            business=business,
            conversation_type="direct",
            members__user=user,
        )
        .filter(members__user=recipient)
        .distinct()
        .first()
    )

    if existing:
        return JsonResponse({"conversation": serialize_conversation(existing, user)})

    # Create new direct conversation
    conversation = Conversation.objects.create(
        business=business,
        conversation_type="direct",
    )
    ConversationMember.objects.create(conversation=conversation, user=user)
    ConversationMember.objects.create(conversation=conversation, user=recipient)

    return JsonResponse({"conversation": serialize_conversation(conversation, user)})


def _create_crew(request, data, business, user):
    crew_id = data.get("crew_id")
    if not crew_id:
        return JsonResponse({"error": "crew_id is required"}, status=400)

    try:
        crew = Crew.objects.get(pk=crew_id, business=business)
    except Crew.DoesNotExist:
        return JsonResponse({"error": "Crew not found"}, status=404)

    # Permission: owner/manager or member/leader of the crew
    if user.role not in ("owner", "manager"):
        is_member = crew.members.filter(pk=user.pk).exists()
        is_leader = crew.crew_leader_id == user.pk
        if not is_member and not is_leader:
            return JsonResponse({"error": "You do not have access to this crew"}, status=403)

    # Find or create crew conversation
    conversation, created = Conversation.objects.get_or_create(
        business=business,
        conversation_type="crew",
        crew=crew,
        defaults={"title": crew.name},
    )

    # Auto-add all crew members + leader + owner/managers as ConversationMembers
    member_user_ids = set(crew.members.values_list("pk", flat=True))
    if crew.crew_leader_id:
        member_user_ids.add(crew.crew_leader_id)

    # Add all owners and managers in the business
    owner_manager_ids = set(
        User.objects.filter(
            business=business,
            role__in=["owner", "manager"],
            is_active=True,
        ).values_list("pk", flat=True)
    )
    member_user_ids |= owner_manager_ids

    existing_member_ids = set(
        ConversationMember.objects
        .filter(conversation=conversation)
        .values_list("user_id", flat=True)
    )
    new_members = [
        ConversationMember(conversation=conversation, user_id=uid)
        for uid in member_user_ids
        if uid not in existing_member_ids
    ]
    if new_members:
        ConversationMember.objects.bulk_create(new_members, ignore_conflicts=True)

    return JsonResponse({"conversation": serialize_conversation(conversation, user)})


def _create_broadcast_conversation(request, business, user):
    if not can_create_broadcast(user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    conversation, created = Conversation.objects.get_or_create(
        business=business,
        conversation_type="broadcast",
        defaults={"title": "All Employees"},
    )

    # Add all active business users as members
    all_user_ids = set(
        User.objects.filter(business=business, is_active=True)
        .values_list("pk", flat=True)
    )
    existing_member_ids = set(
        ConversationMember.objects
        .filter(conversation=conversation)
        .values_list("user_id", flat=True)
    )
    new_members = [
        ConversationMember(conversation=conversation, user_id=uid)
        for uid in all_user_ids
        if uid not in existing_member_ids
    ]
    if new_members:
        ConversationMember.objects.bulk_create(new_members, ignore_conflicts=True)

    return JsonResponse({"conversation": serialize_conversation(conversation, user)})


# ------------------------------------------------------------------
# Conversation messages (paginated)
# ------------------------------------------------------------------


@login_required
@require_http_methods(["GET"])
def conversation_messages(request, conversation_id):
    """Return paginated messages for a conversation."""
    try:
        conversation = (
            Conversation.objects
            .select_related("crew")
            .get(pk=conversation_id)
        )
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    if not can_access_conversation(request.user, conversation):
        return JsonResponse({"error": "Permission denied"}, status=403)

    qs = (
        Message.objects
        .filter(conversation=conversation)
        .select_related("sender")
        .prefetch_related("attachments")
        .order_by("-created_at")
    )

    # Pagination: ?before=<message_id> for older messages
    before = request.GET.get("before")
    if before:
        try:
            before_id = int(before)
            before_msg = Message.objects.filter(pk=before_id).values("created_at").first()
            if before_msg:
                qs = qs.filter(created_at__lt=before_msg["created_at"])
        except (ValueError, TypeError):
            pass

    # Catch-up: ?since=<iso_timestamp> for messages since a timestamp
    since = request.GET.get("since")
    if since:
        try:
            from django.utils.dateparse import parse_datetime
            since_dt = parse_datetime(since)
            if since_dt:
                qs = qs.filter(created_at__gt=since_dt)
        except (ValueError, TypeError):
            pass

    # Fetch one extra to know if there are more
    messages = list(qs[: PAGE_SIZE + 1])
    has_more = len(messages) > PAGE_SIZE
    messages = messages[:PAGE_SIZE]

    # Return in ascending order (oldest first)
    messages.reverse()

    return JsonResponse({
        "messages": [serialize_message(m) for m in messages],
        "has_more": has_more,
        "conversation": serialize_conversation(conversation, request.user),
    })


# ------------------------------------------------------------------
# Send message
# ------------------------------------------------------------------


@login_required
@require_http_methods(["POST"])
def send_message(request, conversation_id):
    """Send a message in a conversation. Accepts JSON or multipart/form-data."""
    try:
        conversation = Conversation.objects.get(pk=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    if not can_access_conversation(request.user, conversation):
        return JsonResponse({"error": "Permission denied"}, status=403)

    # Parse content depending on content type
    content_type_header = request.content_type or ""
    files = []

    if "multipart/form-data" in content_type_header:
        content = request.POST.get("content", "").strip()
        files = request.FILES.getlist("attachments")
    else:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        content = data.get("content", "").strip()

    if not content and not files:
        return JsonResponse(
            {"error": "Message content or attachments required"}, status=400
        )

    # Auto-add sender as ConversationMember if owner/manager and not already a member
    user = request.user
    if user.role in ("owner", "manager"):
        ConversationMember.objects.get_or_create(
            conversation=conversation, user=user
        )

    # Create message
    message = Message.objects.create(
        conversation=conversation,
        sender=user,
        content=content,
    )

    # Create attachments
    for f in files:
        MessageAttachment.objects.create(
            message=message,
            file=f,
            filename=f.name,
            file_size=f.size,
            content_type=f.content_type or "application/octet-stream",
        )

    # Update conversation timestamp
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=["updated_at"])

    # Refetch with attachments for serialization
    message = (
        Message.objects
        .select_related("sender")
        .prefetch_related("attachments")
        .get(pk=message.pk)
    )

    return JsonResponse({"message": serialize_message(message)})


# ------------------------------------------------------------------
# Mark conversation read
# ------------------------------------------------------------------


@login_required
@require_http_methods(["POST"])
def mark_read(request, conversation_id):
    """Mark all messages in a conversation as read for the current user."""
    try:
        conversation = Conversation.objects.get(pk=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    if not can_access_conversation(request.user, conversation):
        return JsonResponse({"error": "Permission denied"}, status=403)

    user = request.user
    now = timezone.now()

    # Update or create membership with last_read_at
    membership, _ = ConversationMember.objects.get_or_create(
        conversation=conversation, user=user,
    )
    old_last_read = membership.last_read_at
    membership.last_read_at = now
    membership.save(update_fields=["last_read_at"])

    # Create MessageReadReceipt for all unread messages
    unread_qs = (
        Message.objects
        .filter(conversation=conversation, is_deleted=False)
        .exclude(sender=user)
    )
    if old_last_read:
        unread_qs = unread_qs.filter(created_at__gt=old_last_read)

    receipts = [
        MessageReadReceipt(message_id=msg_id, user=user)
        for msg_id in unread_qs.values_list("pk", flat=True)
    ]
    if receipts:
        MessageReadReceipt.objects.bulk_create(receipts, ignore_conflicts=True)

    return JsonResponse({"ok": True})


# ------------------------------------------------------------------
# Read receipts
# ------------------------------------------------------------------


@login_required
@require_http_methods(["GET"])
def read_receipts(request, conversation_id):
    """Get read receipts for the last 20 messages in a conversation."""
    try:
        conversation = Conversation.objects.get(pk=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    if not can_access_conversation(request.user, conversation):
        return JsonResponse({"error": "Permission denied"}, status=403)

    # Get last 20 message IDs
    last_message_ids = list(
        Message.objects
        .filter(conversation=conversation, is_deleted=False)
        .order_by("-created_at")
        .values_list("pk", flat=True)[:20]
    )

    receipts_qs = (
        MessageReadReceipt.objects
        .filter(message_id__in=last_message_ids)
        .select_related("user")
        .order_by("read_at")
    )

    grouped = defaultdict(list)
    for receipt in receipts_qs:
        grouped[receipt.message_id].append(serialize_read_receipt(receipt))

    # Convert keys to strings for JSON serialization
    receipts_dict = {str(k): v for k, v in grouped.items()}

    return JsonResponse({"receipts": receipts_dict})


# ------------------------------------------------------------------
# Delete message (soft delete)
# ------------------------------------------------------------------


@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Soft-delete a message and remove its attachments."""
    try:
        message = (
            Message.objects
            .select_related("conversation")
            .get(pk=message_id)
        )
    except Message.DoesNotExist:
        return JsonResponse({"error": "Message not found"}, status=404)

    if not can_delete_message(request.user, message):
        return JsonResponse({"error": "Permission denied"}, status=403)

    # Soft delete
    message.is_deleted = True
    message.content = ""
    message.save(update_fields=["is_deleted", "content"])

    # Delete attachment files and records
    attachments = message.attachments.all()
    for attachment in attachments:
        attachment.file.delete(save=False)
    attachments.delete()

    return JsonResponse({"ok": True})


# ------------------------------------------------------------------
# Broadcast
# ------------------------------------------------------------------


@login_required
@require_http_methods(["POST"])
def broadcast(request):
    """Send a broadcast message to all employees."""
    user = request.user

    if not can_create_broadcast(user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    content = data.get("content", "").strip()
    if not content:
        return JsonResponse({"error": "Message content is required"}, status=400)

    # Find or create broadcast conversation
    conversation, created = Conversation.objects.get_or_create(
        business=business,
        conversation_type="broadcast",
        defaults={"title": "All Employees"},
    )

    # Add any new employees as ConversationMembers
    all_user_ids = set(
        User.objects.filter(business=business, is_active=True)
        .values_list("pk", flat=True)
    )
    existing_member_ids = set(
        ConversationMember.objects
        .filter(conversation=conversation)
        .values_list("user_id", flat=True)
    )
    new_members = [
        ConversationMember(conversation=conversation, user_id=uid)
        for uid in all_user_ids
        if uid not in existing_member_ids
    ]
    if new_members:
        ConversationMember.objects.bulk_create(new_members, ignore_conflicts=True)

    # Send message
    message = Message.objects.create(
        conversation=conversation,
        sender=user,
        content=content,
    )

    # Update conversation timestamp
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=["updated_at"])

    message = (
        Message.objects
        .select_related("sender")
        .prefetch_related("attachments")
        .get(pk=message.pk)
    )

    return JsonResponse({"message": serialize_message(message)})


# ------------------------------------------------------------------
# Unread count
# ------------------------------------------------------------------


@login_required
@require_http_methods(["GET"])
def unread_count(request):
    """Return total unread message count across all conversations."""
    user = request.user

    memberships = ConversationMember.objects.filter(user=user).select_related(
        "conversation"
    )

    total = 0
    for membership in memberships:
        qs = (
            Message.objects
            .filter(conversation=membership.conversation, is_deleted=False)
            .exclude(sender=user)
        )
        if membership.last_read_at:
            qs = qs.filter(created_at__gt=membership.last_read_at)
        total += qs.count()

    return JsonResponse({"unread_count": total})


# ------------------------------------------------------------------
# Messageable users
# ------------------------------------------------------------------


@login_required
@require_http_methods(["GET"])
def messageable_users(request):
    """Return the list of users and crews available for messaging."""
    user = request.user
    business = get_business(request)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)

    # Users available for DM
    users_qs = get_messageable_users(user)
    users_list = [
        {
            "id": u.id,
            "name": u.get_full_name() or u.username,
            "role": u.role,
        }
        for u in users_qs
    ]

    # Crews available for chat
    if user.role in ("owner", "manager"):
        crews_qs = Crew.objects.filter(business=business)
    else:
        crews_qs = Crew.objects.filter(
            Q(members=user) | Q(crew_leader=user),
            business=business,
        ).distinct()

    crews_list = [
        {
            "id": c.id,
            "name": c.name,
            "color": c.color,
        }
        for c in crews_qs
    ]

    return JsonResponse({"users": users_list, "crews": crews_list})

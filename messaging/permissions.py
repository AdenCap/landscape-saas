from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


def can_message_user(sender, recipient):
    """Check if sender can start/send a DM to recipient.

    Rules:
    - Must be same business
    - Owner/manager can message anyone in their business
    - Crew can only message crew members/leaders of crews they belong to
    """
    if sender.business_id != recipient.business_id:
        return False
    if sender.role in ('owner', 'manager'):
        return True
    # Crew role: can message members/leaders of their own crews
    from jobs.models import Crew
    sender_crews = Crew.objects.filter(
        models.Q(members=sender) | models.Q(crew_leader=sender)
    )
    # Check if recipient is a member or leader of any of sender's crews
    return sender_crews.filter(
        models.Q(members=recipient) | models.Q(crew_leader=recipient)
    ).exists()


def can_access_conversation(user, conversation):
    """Check if user can view/send in a conversation.

    Rules:
    - User must be a ConversationMember of this conversation
    - OR user is owner/manager in the same business (they can see all)
    """
    from .models import ConversationMember
    if user.role in ('owner', 'manager') and user.business_id == conversation.business_id:
        return True
    return ConversationMember.objects.filter(
        conversation=conversation, user=user
    ).exists()


def can_create_broadcast(user):
    """Only owner/manager can broadcast."""
    return user.role in ('owner', 'manager')


def can_delete_message(user, message):
    """Owner can delete any message in their business.
    Others can only delete their own messages."""
    if user.role == 'owner' and user.business_id == message.conversation.business_id:
        return True
    return message.sender_id == user.id


def get_messageable_users(user):
    """Return queryset of users this user can start DMs with.

    Owner/manager: all active users in their business (excluding self)
    Crew: crew members and leaders of their crews (excluding self)
    """
    if user.role in ('owner', 'manager'):
        return User.objects.filter(
            business=user.business, is_active=True
        ).exclude(id=user.id)

    # Crew role: members + leaders of their crews
    from jobs.models import Crew
    user_crews = Crew.objects.filter(
        models.Q(members=user) | models.Q(crew_leader=user)
    )
    member_ids = set()
    for crew in user_crews.prefetch_related('members'):
        for member in crew.members.all():
            if member.id != user.id:
                member_ids.add(member.id)
        if crew.crew_leader_id and crew.crew_leader_id != user.id:
            member_ids.add(crew.crew_leader_id)

    return User.objects.filter(id__in=member_ids, is_active=True)

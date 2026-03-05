from django.conf import settings
from django.db import models
from django.utils import timezone
from businesses.models import Business


class Conversation(models.Model):
    """A messaging conversation: direct (1:1), crew chat, or broadcast."""
    CONVERSATION_TYPE_CHOICES = [
        ('direct', 'Direct'),
        ('crew', 'Crew'),
        ('broadcast', 'Broadcast'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    conversation_type = models.CharField(
        max_length=20,
        choices=CONVERSATION_TYPE_CHOICES,
    )
    crew = models.ForeignKey(
        'jobs.Crew',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chat_conversations',
    )
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"{self.get_conversation_type_display()} conversation #{self.pk}"

    def unread_count_for(self, user):
        """Count messages in this conversation after the user's last_read_at."""
        membership = self.members.filter(user=user).first()
        if not membership:
            return 0
        qs = self.messages.filter(is_deleted=False).exclude(sender=user)
        if membership.last_read_at:
            qs = qs.filter(created_at__gt=membership.last_read_at)
        return qs.count()


class ConversationMember(models.Model):
    """Tracks which users belong to a conversation and their read state.

    Dual read-tracking strategy:
    - ``last_read_at`` is the "high water mark" used for fast unread-count
      queries (badge counts).  Only a single timestamp comparison is needed.
    - ``MessageReadReceipt`` provides per-message "Seen by X, Y" display
      in group chats.
    - Both are updated together when a user marks a conversation as read:
      the mark-read API endpoint updates ``last_read_at`` AND creates
      ``MessageReadReceipt`` records for every newly-read message.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        unique_together = [('conversation', 'user')]
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user} in {self.conversation}"


class Message(models.Model):
    """A single message within a conversation."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'is_deleted', 'created_at']),
        ]

    def __str__(self):
        preview = (self.content[:50] + '...') if len(self.content) > 50 else self.content
        return f"{self.sender}: {preview}"


class MessageReadReceipt(models.Model):
    """Tracks when a user has read a specific message."""
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='read_receipts',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_read_receipts',
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('message', 'user')]
        ordering = ['read_at']

    def __str__(self):
        return f"{self.user} read message #{self.message_id} at {self.read_at}"


class MessageAttachment(models.Model):
    """A file attached to a message."""
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='message_attachments/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.filename

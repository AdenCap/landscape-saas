from django.contrib import admin
from .models import (
    Conversation,
    ConversationMember,
    Message,
    MessageReadReceipt,
    MessageAttachment,
)


class ConversationMemberInline(admin.TabularInline):
    model = ConversationMember
    extra = 0
    readonly_fields = ('joined_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'business', 'conversation_type', 'crew', 'created_at', 'updated_at')
    list_filter = ('business', 'conversation_type')
    search_fields = ('title', 'business__name')
    readonly_fields = ('created_at',)
    inlines = [ConversationMemberInline]


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'user', 'joined_at', 'last_read_at', 'is_muted')
    list_filter = ('is_muted', 'conversation__business')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'conversation__title')
    readonly_fields = ('joined_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'content_preview', 'created_at', 'is_deleted')
    list_filter = ('is_deleted', 'conversation__business', 'conversation__conversation_type')
    search_fields = ('content', 'sender__username', 'conversation__title')
    readonly_fields = ('created_at',)

    def content_preview(self, obj):
        return (obj.content[:60] + '...') if len(obj.content) > 60 else obj.content
    content_preview.short_description = 'Content'


@admin.register(MessageReadReceipt)
class MessageReadReceiptAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'read_at')
    list_filter = ('message__conversation__business',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('read_at',)


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'message', 'content_type', 'file_size', 'created_at')
    list_filter = ('content_type', 'message__conversation__business')
    search_fields = ('filename',)
    readonly_fields = ('created_at',)

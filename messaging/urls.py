from django.urls import path

from . import views

urlpatterns = [
    path("conversations/", views.conversation_list_or_create, name="messaging_conversations"),
    path("conversations/<int:conversation_id>/", views.conversation_messages, name="messaging_messages"),
    path("conversations/<int:conversation_id>/send/", views.send_message, name="messaging_send"),
    path("conversations/<int:conversation_id>/read/", views.mark_read, name="messaging_mark_read"),
    path("conversations/<int:conversation_id>/receipts/", views.read_receipts, name="messaging_receipts"),
    path("messages/<int:message_id>/delete/", views.delete_message, name="messaging_delete"),
    path("broadcast/", views.broadcast, name="messaging_broadcast"),
    path("unread-count/", views.unread_count, name="messaging_unread_count"),
    path("messageable-users/", views.messageable_users, name="messaging_users"),
]

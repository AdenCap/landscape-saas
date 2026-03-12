# In-App Messaging Feature Design

**Date:** 2026-03-05
**Status:** Approved

## Overview

Add real-time in-app messaging to FieldLgx so employees within a business can communicate. Messaging is role-based: owner/managers can message anyone and broadcast; crew members can message within their own crews.

## Architecture

**Approach:** Django API + Supabase Realtime Listener

- Django handles all message reads, writes, and permission checks via JSON API endpoints
- Supabase Realtime pushes instant notifications to connected frontends (subscribe to Postgres Changes on the messages table)
- On reconnect, the client fetches missed messages via Django API (hybrid reliability pattern)
- No ASGI migration required — the app stays on WSGI/Gunicorn
- Supabase anon key used for read-only Realtime subscriptions; all writes go through Django with session auth

## Data Models

### Conversation

| Field | Type | Notes |
|-------|------|-------|
| business | FK → Business | Tenant scoping |
| conversation_type | CharField | `direct`, `crew`, `broadcast` |
| crew | FK → Crew (nullable) | Set for crew-type conversations |
| title | CharField (blank) | Display name for crew/broadcast chats |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now, used for sort order |

### ConversationMember

| Field | Type | Notes |
|-------|------|-------|
| conversation | FK → Conversation | |
| user | FK → User | |
| joined_at | DateTimeField | auto_now_add |
| last_read_at | DateTimeField (nullable) | Read watermark for fast unread counts |
| is_muted | BooleanField | Default False |

Unique together: (conversation, user)

### Message

| Field | Type | Notes |
|-------|------|-------|
| conversation | FK → Conversation | |
| sender | FK → User | |
| content | TextField (blank) | Can be empty if attachment-only |
| created_at | DateTimeField | auto_now_add |
| edited_at | DateTimeField (nullable) | |
| is_deleted | BooleanField | Soft delete, shows "message was deleted" |

### MessageReadReceipt

| Field | Type | Notes |
|-------|------|-------|
| message | FK → Message | |
| user | FK → User | |
| read_at | DateTimeField | auto_now_add |

Unique together: (message, user)

Read receipts are per-message ("Seen by John, Sarah"). The `ConversationMember.last_read_at` watermark is also updated for efficient unread count queries.

### MessageAttachment

| Field | Type | Notes |
|-------|------|-------|
| message | FK → Message | |
| file | FileField | Upload to `media/message_attachments/` |
| filename | CharField | Original filename |
| file_size | IntegerField | Bytes |
| content_type | CharField | MIME type for inline preview vs download |
| created_at | DateTimeField | auto_now_add |

## Permission Rules

| Action | Owner | Manager | Crew |
|--------|-------|---------|------|
| Start DM with anyone in business | Yes | Yes | No |
| Start DM with own crew members/leader | Yes | Yes | Yes |
| Send in crew group chat | Yes | Yes | Yes (own crews only) |
| Send broadcast to all employees | Yes | Yes | No |
| See all conversations in business | Yes | Yes | No |
| Delete any message | Yes | No | No |
| Delete own message | Yes | Yes | Yes |

Crew members can only access conversations they are a member of. Owner/managers are auto-added to all crew chats.

## API Endpoints

All return JSON. All scoped to `request.user.business`. CSRF protected.

```
POST   /api/messages/conversations/              — create or get conversation
GET    /api/messages/conversations/              — list user's conversations
GET    /api/messages/conversations/<id>/          — get messages (paginated)
POST   /api/messages/conversations/<id>/send/     — send message (+ attachments)
POST   /api/messages/conversations/<id>/read/     — mark read (watermark + receipts)
GET    /api/messages/conversations/<id>/receipts/ — read receipts for recent messages
DELETE /api/messages/messages/<id>/               — soft delete message
POST   /api/messages/broadcast/                  — owner/manager broadcast
GET    /api/messages/unread-count/               — total unread across all convos
```

## Supabase Realtime Integration

Frontend subscribes to Postgres Changes on the `messaging_message` table filtered by the user's conversation IDs:

```javascript
supabase
  .channel('messages')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'messaging_message',
    filter: `conversation_id=in.(${myConversationIds.join(',')})`
  }, (payload) => {
    // Append message to open chat or update unread badge
  })
  .subscribe()
```

On reconnect, client fetches `/api/messages/conversations/<id>/?since=<last_timestamp>` for missed messages.

## UI Design

### Slide-Out Chat Panel

A right-side drawer in `base.html`, accessible from every page via a floating chat button (bottom-right corner).

**Desktop (>= 768px):** 360px-wide panel slides in from the right, overlaying page content.

**Mobile (< 768px):** Panel goes full-screen. Floating button positioned above the mobile bottom nav bar.

### Panel Views

**Conversation List:**
- Sorted by `updated_at` (most recent first)
- Each row: avatar/icon, name, last message preview, timestamp, unread badge
- "New Message" button opens recipient picker (filtered by role permissions)
- Crew chats show crew color dot
- Broadcast chats show megaphone icon

**Chat View:**
- Back arrow + conversation name header
- Messages: own messages right-aligned (blue), others left-aligned (gray)
- Read receipt indicators: checkmark for sent, double-check for read
- Group chats: "Seen by..." tooltip on hover/tap
- Inline image previews for image attachments, download link for other files
- Input bar: text field + attachment button (paperclip icon) + send button
- Auto-scroll to bottom on new messages

**New Message Picker:**
- Search/filter employees
- Sections: "Direct Messages", "Crews" (crew members only see their crews), "All Employees" (owner/manager only)

### Floating Chat Button

- Fixed position bottom-right (above mobile nav on small screens)
- Chat bubble icon with total unread count badge
- Animated entrance, subtle pulse on new message

## Existing System Integration

- The current `Notification` model and UI stay unchanged (serves as system notifications)
- The sidebar "Notifications" link continues pointing to the notification inbox
- The new chat button is a separate, always-visible floating element
- The `notification_unread_count` context processor remains for system notification badges

## New Django App

Create a new `messaging` app:

```
messaging/
  __init__.py
  models.py          — Conversation, ConversationMember, Message, MessageReadReceipt, MessageAttachment
  views.py           — API endpoints (JSON responses)
  urls.py            — URL routing under /api/messages/
  permissions.py     — Role-based permission checks
  serializers.py     — Model → JSON serialization helpers
  admin.py           — Admin registration
  migrations/
  templates/
    messaging/
      _chat_panel.html  — slide-out panel (included in base.html)
  static/
    js/
      messaging.js      — Chat panel JS + Supabase Realtime subscription
    css/
      messaging.css     — Chat panel styles
```

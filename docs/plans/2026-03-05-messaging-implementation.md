# In-App Messaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time in-app messaging with a slide-out chat panel, role-based permissions, read receipts, file attachments, and Supabase Realtime for instant delivery.

**Architecture:** Django JSON API endpoints handle all reads/writes/permissions. Supabase Realtime pushes new messages to connected frontends via Postgres Changes subscription. A slide-out chat panel in base.html provides the UI on every page.

**Tech Stack:** Django 5.2, Supabase Postgres + Realtime, vanilla JavaScript, CSS design system variables.

**Design doc:** `docs/plans/2026-03-05-messaging-design.md`

---

## Task 1: Create Messaging Django App + Models

**Files:**
- Create: `messaging/__init__.py`
- Create: `messaging/apps.py`
- Create: `messaging/models.py`
- Create: `messaging/admin.py`
- Modify: `config/settings.py:102` (add to INSTALLED_APPS)

**Step 1: Scaffold the messaging app**

Run: `cd /Users/adencappelletti/landscape-saas && python3 manage.py startapp messaging`

**Step 2: Write models.py**

Create all 5 models in `messaging/models.py`:
- `Conversation` — business FK, conversation_type (direct/crew/broadcast), crew FK (nullable), title, created_at, updated_at
- `ConversationMember` — conversation FK, user FK, joined_at, last_read_at (nullable), is_muted. Unique together (conversation, user)
- `Message` — conversation FK, sender FK, content (blank OK), created_at, edited_at (nullable), is_deleted
- `MessageReadReceipt` — message FK, user FK, read_at. Unique together (message, user)
- `MessageAttachment` — message FK, file (FileField to `message_attachments/`), filename, file_size, content_type, created_at

Reference the existing model patterns in `accounts/models.py` (lines 116-141) for FK conventions. Use `settings.AUTH_USER_MODEL` for user FKs. Use `businesses.Business` for business FK. Use `jobs.Crew` for crew FK.

Set `updated_at` on Conversation as a plain DateTimeField (NOT auto_now) so we can manually update it when new messages arrive. Default to `timezone.now`.

Add `__str__` methods. Add `class Meta: ordering` on each model.

Add a helper method on `Conversation`: `def unread_count_for(self, user)` that counts messages created after that user's `ConversationMember.last_read_at`.

**Step 3: Register in INSTALLED_APPS**

Modify `config/settings.py` line 102 — add `'messaging',` before the closing `]` of INSTALLED_APPS (after `'quickbooks'`).

**Step 4: Register models in admin.py**

Register all 5 models in `messaging/admin.py` with basic ModelAdmin classes. Include `list_display`, `list_filter`, and `search_fields` for each.

**Step 5: Run makemigrations and migrate**

Run: `python3 manage.py makemigrations messaging`
Run: `python3 manage.py migrate`

Verify: No errors. The 5 tables are created in Supabase Postgres.

**Step 6: Commit**

```bash
git add messaging/ config/settings.py
git commit -m "feat(messaging): create messaging app with Conversation, Message, ReadReceipt, Attachment models"
```

---

## Task 2: Permission Helpers

**Files:**
- Create: `messaging/permissions.py`

**Step 1: Write permission checker functions**

Create `messaging/permissions.py` with these functions:

```python
def can_message_user(sender, recipient):
    """Check if sender can start/send a DM to recipient.

    Rules:
    - Must be same business
    - Owner/manager can message anyone in their business
    - Crew can only message crew members/leaders of crews they belong to
    """

def can_access_conversation(user, conversation):
    """Check if user can view/send in a conversation.

    Rules:
    - User must be a ConversationMember of this conversation
    - OR user is owner/manager in the same business (they can see all)
    """

def can_create_broadcast(user):
    """Only owner/manager can broadcast."""

def can_delete_message(user, message):
    """Owner can delete any message in their business.
    Others can only delete their own messages."""

def get_messageable_users(user):
    """Return queryset of users this user can start DMs with.

    Owner/manager: all users in their business (excluding self)
    Crew: crew members and leaders of their crews (excluding self)
    """
```

Import `User` via `get_user_model()`. Import `Crew` from `jobs.models`. Use `accounts.utils.get_business` pattern (the request-based one checks session for superusers, but these permission checks work on User objects directly, so use `user.business`).

For `get_messageable_users` for crew role: query `Crew.objects.filter(members=user)` to get their crews, then collect all members + crew_leaders from those crews, exclude self.

**Step 2: Commit**

```bash
git add messaging/permissions.py
git commit -m "feat(messaging): add role-based permission helpers"
```

---

## Task 3: Serialization Helpers

**Files:**
- Create: `messaging/serializers.py`

**Step 1: Write JSON serialization helpers**

These are plain functions (not DRF serializers — the project doesn't use DRF). They convert model instances to dicts for `JsonResponse`.

```python
def serialize_conversation(conversation, for_user):
    """Return dict with id, type, title, crew info, last_message preview, unread_count, updated_at.

    For direct conversations, title = the other person's name.
    For crew conversations, title = crew name.
    For broadcast, title = 'All Employees'.
    """

def serialize_message(message, include_attachments=True):
    """Return dict with id, sender (id, name), content, created_at, is_deleted, edited_at, attachments[]."""

def serialize_attachment(attachment):
    """Return dict with id, filename, file_size, content_type, url."""

def serialize_read_receipt(receipt):
    """Return dict with user (id, name), read_at."""
```

Format timestamps as ISO 8601 strings. Use `user.get_full_name() or user.username` for display names.

For `serialize_conversation`, compute `unread_count` using the `Conversation.unread_count_for(user)` method from Task 1. Include `last_message` as a serialized message dict (or null if no messages).

**Step 2: Commit**

```bash
git add messaging/serializers.py
git commit -m "feat(messaging): add JSON serialization helpers"
```

---

## Task 4: Conversation API Views

**Files:**
- Create: `messaging/views.py`
- Create: `messaging/urls.py`
- Modify: `config/urls.py:79` (add URL include)

**Step 1: Write conversation list view**

`GET /api/messages/conversations/` — Returns all conversations the user is a member of (or all in business for owner/manager), sorted by `updated_at` descending.

Use `@login_required` and `@require_http_methods(["GET"])`. Get business via `accounts.utils.get_business(request)`. Return `JsonResponse` with `{"conversations": [...]}`.

For owner/manager: show all conversations in business.
For crew: show only conversations where they're a ConversationMember.

Use `select_related('crew')` and `prefetch_related('members__user')` for performance.

**Step 2: Write create/get conversation view**

`POST /api/messages/conversations/` — Create or retrieve a conversation.

Request body (JSON):
- For direct: `{"type": "direct", "user_id": 123}`
- For crew: `{"type": "crew", "crew_id": 456}`
- For broadcast: `{"type": "broadcast"}`

Parse JSON body with `json.loads(request.body)`. Validate permissions using `messaging/permissions.py`.

For direct conversations: check if one already exists between these two users (query ConversationMember). If exists, return it. If not, create Conversation + two ConversationMember records.

For crew conversations: check if one already exists for this crew. If exists, return it. If not, create Conversation + ConversationMember for all crew members + owner/managers.

For broadcast: check if one already exists. If exists, return it. If not, create Conversation + ConversationMember for all business users.

Return `JsonResponse` with the serialized conversation.

**Step 3: Write get conversation messages view**

`GET /api/messages/conversations/<id>/` — Returns paginated messages for a conversation.

Query params: `?before=<message_id>` for pagination (load older), `?since=<timestamp>` for catch-up after reconnect.

Default: return last 50 messages. Use `select_related('sender')` and `prefetch_related('attachments')`.

Check permission: `can_access_conversation(request.user, conversation)`.

Return `JsonResponse` with `{"messages": [...], "has_more": bool}`.

**Step 4: Write URL configuration**

Create `messaging/urls.py`:
```python
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
```

**Step 5: Add URL include to config/urls.py**

Add this line after line 79 in `config/urls.py` (after the quickbooks line, before the closing `]`):
```python
path("api/messages/", include("messaging.urls")),
```

**Step 6: Commit**

```bash
git add messaging/views.py messaging/urls.py config/urls.py
git commit -m "feat(messaging): add conversation list, create, and messages API views"
```

---

## Task 5: Message Send, Read, Delete, and Broadcast Views

**Files:**
- Modify: `messaging/views.py` (add remaining views)

**Step 1: Write send message view**

`POST /api/messages/conversations/<id>/send/` — Send a message (with optional attachments).

Accept `multipart/form-data` (for file uploads) or `application/json` (text-only).

For multipart: `request.POST.get("content")` for text, `request.FILES.getlist("attachments")` for files.
For JSON: `json.loads(request.body)` for `{"content": "text"}`.

Validate: user must be ConversationMember (or owner/manager of the business). Content must not be empty unless attachments are present.

Create `Message` record. Create `MessageAttachment` records for each file. Update `Conversation.updated_at` to `timezone.now()`.

Return serialized message with attachments.

**Step 2: Write mark read view**

`POST /api/messages/conversations/<id>/read/` — Mark conversation as read.

Update `ConversationMember.last_read_at` to `timezone.now()`. Create `MessageReadReceipt` records for all unread messages in this conversation (messages after previous `last_read_at` where no receipt exists for this user).

Use `bulk_create` with `ignore_conflicts=True` for receipts.

Return `JsonResponse({"ok": True})`.

**Step 3: Write read receipts view**

`GET /api/messages/conversations/<id>/receipts/` — Get read receipts for recent messages.

Return receipts for the last 20 messages. Group by message_id. Useful for displaying "Seen by..." in group chats.

Return `JsonResponse({"receipts": {message_id: [receipt, ...], ...}})`.

**Step 4: Write delete message view**

`DELETE /api/messages/messages/<id>/delete/` — Soft delete a message.

Check `can_delete_message(request.user, message)`. Set `message.is_deleted = True`, `message.content = ""`, save. Delete associated attachments (both files and records).

Return `JsonResponse({"ok": True})`.

**Step 5: Write broadcast view**

`POST /api/messages/broadcast/` — Owner/manager sends to all employees.

Check `can_create_broadcast(request.user)`. Find or create the broadcast conversation. Add any new employees as ConversationMembers. Send the message in that conversation.

Accept same format as send_message (multipart or JSON).

Return serialized message.

**Step 6: Write unread count view**

`GET /api/messages/unread-count/` — Total unread count across all conversations.

For the current user, sum up unread messages across all their ConversationMember records. Use a single aggregation query:

```python
from django.db.models import Count, Q, F
unread = Message.objects.filter(
    conversation__members__user=request.user
).exclude(sender=request.user).filter(
    Q(conversation__conversationmember__user=request.user),
    Q(created_at__gt=F('conversation__conversationmember__last_read_at')) | Q(conversation__conversationmember__last_read_at__isnull=True)
).count()
```

Return `JsonResponse({"unread_count": count})`.

**Step 7: Write messageable users view**

`GET /api/messages/messageable-users/` — List users the current user can message.

Use `get_messageable_users(request.user)`. Return `JsonResponse({"users": [{"id": ..., "name": ..., "role": ...}, ...]})`.

Also return `{"crews": [{"id": ..., "name": ..., "color": ...}, ...]}` for crews the user belongs to (or all crews for owner/manager).

**Step 8: Commit**

```bash
git add messaging/views.py
git commit -m "feat(messaging): add send, read, delete, broadcast, unread-count API views"
```

---

## Task 6: Context Processor for Messaging Unread Count

**Files:**
- Create: `messaging/context_processors.py`
- Modify: `config/settings.py:146` (add context processor)

**Step 1: Write messaging context processor**

Create `messaging/context_processors.py`:

```python
def messaging_unread_count(request):
    """Add messaging_unread_count for authenticated users (for floating chat badge)."""
    if request.user.is_authenticated:
        from messaging.models import Message, ConversationMember
        from django.db.models import Q, F
        # Count messages in user's conversations that are newer than their last_read_at
        memberships = ConversationMember.objects.filter(user=request.user)
        count = 0
        for m in memberships:
            q = Message.objects.filter(conversation=m.conversation).exclude(sender=request.user)
            if m.last_read_at:
                q = q.filter(created_at__gt=m.last_read_at)
            count += q.count()
        return {"messaging_unread_count": count}
    return {"messaging_unread_count": 0}
```

Note: This is the simple version. Optimize later with a single query if performance becomes an issue. The per-page DB hit is acceptable for now since the notification context processor already does a similar query.

**Step 2: Register in settings**

Add `'messaging.context_processors.messaging_unread_count'` after line 146 in `config/settings.py` (after the notification processor).

**Step 3: Commit**

```bash
git add messaging/context_processors.py config/settings.py
git commit -m "feat(messaging): add messaging_unread_count context processor"
```

---

## Task 7: Chat Panel CSS

**Files:**
- Create: `messaging/static/css/messaging.css`

**Step 1: Write chat panel styles**

Use the CSS variable conventions from `static/css/design-system.css`:
- Colors: `var(--bg)`, `var(--bg-elevated)`, `var(--bg-surface)`, `var(--border)`, `var(--text)`, `var(--text-muted)`, `var(--primary)`, `var(--primary-hover)`
- Spacing: `var(--space-1)` through `var(--space-32)`
- Glass: `var(--glass)`, `var(--glass-border)`

Key classes to create:

- `.chat-fab` — floating action button (fixed bottom-right, 56px circle, primary color, z-index 1000)
- `.chat-fab-badge` — unread count badge on the FAB
- `.chat-panel` — slide-out panel (fixed right, 380px wide desktop, 100% mobile, z-index 1001, transform translateX(100%) when hidden)
- `.chat-panel.open` — transform translateX(0) with transition
- `.chat-panel-header` — panel header with title and close button
- `.chat-overlay` — semi-transparent backdrop for mobile
- `.conversation-list` — scrollable list of conversations
- `.conversation-item` — individual conversation row (avatar, name, preview, time, badge)
- `.conversation-item.unread` — bold styling for unread conversations
- `.chat-messages` — scrollable message area (flex-grow, overflow-y auto)
- `.chat-bubble` — message bubble base
- `.chat-bubble.own` — right-aligned, primary color background
- `.chat-bubble.other` — left-aligned, surface color background
- `.chat-bubble .sender-name` — small text above bubble in group chats
- `.chat-bubble .time` — timestamp below bubble
- `.chat-bubble .read-receipt` — checkmark icons
- `.chat-input-bar` — bottom input area (flex row: attachment btn, textarea, send btn)
- `.chat-attachment-preview` — pending attachment thumbnails above input
- `.new-message-picker` — recipient selection view (search + user list)
- `.typing-indicator` — "..." animation (for future use)

Mobile overrides at `@media (max-width: 767px)`: panel goes full-width/full-height. FAB positioned above the mobile bottom nav (bottom: 80px instead of 24px).

Use smooth transitions: `transition: transform 0.3s ease`. Match the app's existing dark theme aesthetic.

**Step 2: Commit**

```bash
git add messaging/static/css/messaging.css
git commit -m "feat(messaging): add chat panel CSS with dark theme"
```

---

## Task 8: Chat Panel HTML Template

**Files:**
- Create: `messaging/templates/messaging/_chat_panel.html`

**Step 1: Write the chat panel partial template**

This is an `{% include %}` partial for `base.html`. It contains:

1. **Floating chat button** with `{{ messaging_unread_count }}` badge
2. **Panel container** with three internal views (show/hide with JS):
   - **Conversation list view**: header ("Messages"), new message button, scrollable conversation list (empty initially, populated by JS)
   - **Chat view**: back button + conversation name header, scrollable messages area, input bar with attachment button + textarea + send button
   - **New message picker**: search input, user/crew list (populated by JS from `/api/messages/messageable-users/`)
3. **Mobile overlay** backdrop

Use Lucide icon names: `message-circle` (FAB), `arrow-left` (back), `paperclip` (attach), `send` (send), `x` (close panel), `plus` (new message), `users` (crew icon), `megaphone` (broadcast icon), `check` and `check-check` (read receipts).

The HTML uses `data-view="list|chat|new"` attributes for view switching. All data loading happens in JavaScript.

Include the CSRF token in a hidden input for JS to read: `{% csrf_token %}`.

Pass the current user ID to JS via a data attribute: `data-user-id="{{ request.user.id }}"`.

**Step 2: Commit**

```bash
git add messaging/templates/messaging/_chat_panel.html
git commit -m "feat(messaging): add chat panel HTML template"
```

---

## Task 9: Chat Panel JavaScript (Core)

**Files:**
- Create: `messaging/static/js/messaging.js`

**Step 1: Write the core chat panel JavaScript**

Structure as an IIFE `(function() { ... })()` that initializes on DOMContentLoaded.

Key state variables:
```javascript
let currentView = 'list';      // 'list' | 'chat' | 'new'
let conversations = [];         // cached conversation list
let currentConversation = null; // active conversation object
let currentMessages = [];       // messages in active conversation
let pollInterval = null;        // fallback polling timer
```

Core functions:

**Panel control:**
- `openPanel()` — add `.open` class, load conversations if stale, show overlay on mobile
- `closePanel()` — remove `.open` class, hide overlay
- `showView(name)` — switch between list/chat/new views

**API helpers:**
- `apiFetch(url, options)` — wrapper around `fetch()` that adds CSRF token header, handles JSON parsing, and shows toast on error. Read CSRF token from the hidden input.

**Conversation list:**
- `loadConversations()` — `GET /api/messages/conversations/`, render the list, update FAB badge
- `renderConversationList()` — build HTML for each conversation (avatar/icon, name, preview, time, unread badge)

**Chat view:**
- `openConversation(id)` — switch to chat view, `GET /api/messages/conversations/<id>/`, render messages, mark as read
- `renderMessages(messages)` — build message bubbles (own = right/blue, other = left/gray), show sender name in group chats, show timestamps, show read receipts, show attachments
- `scrollToBottom()` — scroll message area to latest message
- `sendMessage()` — collect text + pending attachments, `POST /api/messages/conversations/<id>/send/` as FormData, append the returned message to the view, clear input
- `markRead(conversationId)` — `POST /api/messages/conversations/<id>/read/`
- `loadOlderMessages()` — triggered by scrolling to top, `GET ...?before=<oldest_message_id>`

**New message:**
- `loadMessageableUsers()` — `GET /api/messages/messageable-users/`, render user/crew list
- `startConversation(type, targetId)` — `POST /api/messages/conversations/`, then open that conversation
- `filterUsers(query)` — client-side filter of the user list by name

**Attachments:**
- `handleAttachmentSelect(event)` — from file input, show preview thumbnails above input bar
- `removeAttachment(index)` — remove a pending attachment

**Read receipts:**
- After rendering messages, `GET .../receipts/` for the conversation and overlay checkmarks on messages

**Utilities:**
- `timeAgo(isoString)` — "2m ago", "1h ago", "Yesterday", etc.
- `escapeHtml(text)` — prevent XSS in message content

**Event listeners:**
- FAB click → `openPanel()`
- Close button → `closePanel()`
- Escape key → `closePanel()`
- Overlay click → `closePanel()`
- Conversation item click → `openConversation(id)`
- Back button → `showView('list')`
- New message button → `showView('new')`, `loadMessageableUsers()`
- Send button click + Enter key → `sendMessage()`
- Attachment button → trigger hidden file input
- Message area scroll to top → `loadOlderMessages()`

**Step 2: Commit**

```bash
git add messaging/static/js/messaging.js
git commit -m "feat(messaging): add core chat panel JavaScript"
```

---

## Task 10: Supabase Realtime Integration

**Files:**
- Modify: `messaging/static/js/messaging.js` (add Realtime section at bottom)
- Modify: `messaging/templates/messaging/_chat_panel.html` (add supabase-js script tag)
- Modify: `.env.example` (add SUPABASE_ANON_KEY, SUPABASE_PROJECT_URL)
- Modify: `config/settings.py` (expose Supabase URL/key to templates)
- Modify: `messaging/context_processors.py` (pass Supabase config to frontend)

**Step 1: Add supabase-js CDN to the chat panel template**

In `_chat_panel.html`, before the messaging.js script tag, add:
```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>
```

**Step 2: Add Supabase config to settings and context processor**

In `config/settings.py`, add after the media config section:
```python
# Supabase Realtime (for in-app messaging)
SUPABASE_PROJECT_URL = os.environ.get("SUPABASE_PROJECT_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
```

In `messaging/context_processors.py`, add these to the returned dict:
```python
from django.conf import settings as django_settings
return {
    "messaging_unread_count": count,
    "supabase_project_url": django_settings.SUPABASE_PROJECT_URL,
    "supabase_anon_key": django_settings.SUPABASE_ANON_KEY,
}
```

Pass these as data attributes on the chat panel container:
```html
<div id="chat-panel" data-supabase-url="{{ supabase_project_url }}" data-supabase-key="{{ supabase_anon_key }}">
```

**Step 3: Add Realtime subscription code to messaging.js**

At the bottom of the IIFE, after all core functions:

```javascript
// --- Supabase Realtime ---
function initRealtime() {
    const panel = document.getElementById('chat-panel');
    const url = panel?.dataset.supabaseUrl;
    const key = panel?.dataset.supabaseKey;
    if (!url || !key) {
        // Fallback to polling if Supabase not configured
        startPolling();
        return;
    }

    const supabase = window.supabase.createClient(url, key);

    // Subscribe to new messages in user's conversations
    function subscribe(conversationIds) {
        if (!conversationIds.length) return;
        supabase
            .channel('messages-' + userId)
            .on('postgres_changes', {
                event: 'INSERT',
                schema: 'public',
                table: 'messaging_message',
                filter: 'conversation_id=in.(' + conversationIds.join(',') + ')'
            }, handleRealtimeMessage)
            .subscribe();
    }

    function handleRealtimeMessage(payload) {
        const msg = payload.new;
        // If this conversation is currently open, append the message
        if (currentConversation && msg.conversation_id === currentConversation.id) {
            // Fetch the full serialized message from API (payload.new is raw DB row)
            apiFetch('/api/messages/conversations/' + msg.conversation_id + '/?since=' + encodeURIComponent(lastMessageTimestamp))
                .then(data => {
                    if (data.messages) {
                        data.messages.forEach(appendMessage);
                        scrollToBottom();
                        markRead(currentConversation.id);
                    }
                });
        }
        // Always refresh conversation list to update previews and unread counts
        loadConversations();
        updateFabBadge();
    }

    // Initial subscription with current conversation IDs
    loadConversations().then(() => {
        subscribe(conversations.map(c => c.id));
    });

    // Re-subscribe when conversations change
    // (called after creating new conversations)
}

function startPolling() {
    // Fallback: poll every 5 seconds
    pollInterval = setInterval(() => {
        loadConversations();
        if (currentConversation) {
            // Fetch new messages since last one
        }
    }, 5000);
}
```

**Step 4: Update .env.example**

Add after the Supabase database section:
```
# Supabase Realtime (for in-app messaging push notifications)
# Get from Supabase Dashboard → Settings → API
SUPABASE_PROJECT_URL=
SUPABASE_ANON_KEY=
```

**Step 5: Commit**

```bash
git add messaging/static/js/messaging.js messaging/templates/messaging/_chat_panel.html messaging/context_processors.py config/settings.py .env.example
git commit -m "feat(messaging): add Supabase Realtime integration with polling fallback"
```

---

## Task 11: Wire Chat Panel into base.html

**Files:**
- Modify: `templates/base.html:18` (add CSS link)
- Modify: `templates/base.html:895` (include chat panel before closing script/body)

**Step 1: Add CSS link in head**

After line 18 in `base.html` (`design-system.css` link), add:
```html
<link rel="stylesheet" href="{% static 'css/messaging.css' %}">
```

**Step 2: Include chat panel partial**

Before line 895 (before the closing `</script>` of the main inline script block), add the include. Actually, add it after the toast container and before the final script — around line 737 (after the toast container div):

```html
{% if user.is_authenticated %}
{% include "messaging/_chat_panel.html" %}
{% endif %}
```

The chat panel template itself includes the `<script>` tags for supabase-js and messaging.js at its bottom.

**Step 3: Verify the Lucide icons reinitialize**

The existing `base.html` calls `lucide.createIcons()` at line 777. Since the chat panel HTML is rendered before this call, the Lucide icons in the panel will be picked up automatically. No changes needed.

**Step 4: Commit**

```bash
git add templates/base.html
git commit -m "feat(messaging): wire chat panel into base.html"
```

---

## Task 12: Enable Supabase Realtime on the Messages Table

**Files:** None (this is a Supabase dashboard/SQL operation)

**Step 1: Enable Realtime replication**

Run this SQL against the Supabase database (via Supabase dashboard SQL editor or Django manage.py dbshell):

```sql
-- Enable realtime for the messaging_message table
ALTER PUBLICATION supabase_realtime ADD TABLE messaging_message;
```

This tells Supabase's Realtime server to watch for changes on the `messaging_message` table and broadcast them to subscribers.

**Step 2: Verify**

Check that the publication includes the table:
```sql
SELECT * FROM pg_publication_tables WHERE pubname = 'supabase_realtime';
```

You should see `messaging_message` in the results.

**Step 3: Document**

Add a note to `docs/plans/2026-03-05-messaging-design.md` about this required Supabase configuration step.

---

## Task 13: Integration Testing and Polish

**Files:**
- Modify: various files for bug fixes found during testing

**Step 1: Test conversation creation**

Using the Django shell or a test script:
1. Create a test business with an owner and 2 crew members
2. Create a crew with both crew members
3. Test creating a direct conversation (owner → crew1)
4. Test creating a crew conversation
5. Test creating a broadcast conversation
6. Verify ConversationMember records are correct

**Step 2: Test messaging flow**

1. Send a message in a direct conversation
2. Verify it appears in the conversation messages API
3. Mark as read, verify read receipts are created
4. Send a message with an attachment
5. Verify the file is saved and the attachment URL works

**Step 3: Test permissions**

1. Verify crew member CANNOT start DM with user outside their crews
2. Verify crew member CAN start DM with crew mate
3. Verify crew member CANNOT broadcast
4. Verify owner CAN see all conversations
5. Verify crew member can only see their own conversations

**Step 4: Test the chat panel UI**

1. Load any page, verify the floating chat button appears with correct unread count
2. Click the button, verify the panel slides open
3. Click a conversation, verify messages load
4. Send a message, verify it appears
5. Test on mobile viewport (< 768px), verify full-screen panel
6. Test the new message picker, verify role-based filtering

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat(messaging): integration testing fixes and polish"
```

---

## Summary of Files Created/Modified

### New files (messaging app):
- `messaging/__init__.py`
- `messaging/apps.py`
- `messaging/models.py`
- `messaging/admin.py`
- `messaging/permissions.py`
- `messaging/serializers.py`
- `messaging/views.py`
- `messaging/urls.py`
- `messaging/context_processors.py`
- `messaging/templates/messaging/_chat_panel.html`
- `messaging/static/css/messaging.css`
- `messaging/static/js/messaging.js`
- `messaging/migrations/0001_initial.py` (auto-generated)

### Modified files:
- `config/settings.py` — INSTALLED_APPS + context processor + Supabase config
- `config/urls.py` — add `api/messages/` URL include
- `templates/base.html` — add CSS link + include chat panel partial
- `.env.example` — add SUPABASE_PROJECT_URL and SUPABASE_ANON_KEY

### Database:
- Supabase SQL: `ALTER PUBLICATION supabase_realtime ADD TABLE messaging_message;`

/**
 * Chat Panel JavaScript - Core messaging functionality with Supabase Realtime.
 *
 * Drives the floating chat panel: conversation list, chat view, new-message
 * picker, file attachments, and real-time message delivery (with polling
 * fallback when Supabase is not configured).
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // ------------------------------------------------------------------ DOM
    const panel = document.getElementById("chat-panel");
    if (!panel) return;

    const userId = panel.dataset.userId;
    const fab = document.getElementById("chat-fab");
    const fabBadge = document.getElementById("chat-fab-badge");
    const overlay = document.getElementById("chat-overlay");
    const conversationListEl = document.getElementById("conversation-list");
    const convEmpty = document.getElementById("conv-empty");
    const chatMessages = document.getElementById("chat-messages");
    const chatLoading = document.getElementById("chat-loading");
    const attachmentPreview = document.getElementById("attachment-preview");
    const messageInput = document.getElementById("message-input");
    const btnSend = document.getElementById("btn-send");
    const chatTitle = document.getElementById("chat-title");
    const newMessageList = document.getElementById("new-message-list");
    const userSearch = document.getElementById("user-search");
    const fileInput = document.getElementById("file-input");

    // --------------------------------------------------------------- State
    var currentView = "list";
    var conversations = [];
    var currentConversation = null;
    var currentMessages = [];
    var pendingAttachments = [];
    var lastMessageTimestamp = null;
    var isLoadingOlder = false;
    var hasMoreMessages = false;
    var pollInterval = null;
    var realtimeChannel = null;

    // ----------------------------------------------------------- Utilities
    function timeAgo(isoString) {
      var date = new Date(isoString);
      var now = new Date();
      var seconds = Math.floor((now - date) / 1000);
      if (seconds < 60) return "now";
      var minutes = Math.floor(seconds / 60);
      if (minutes < 60) return minutes + "m";
      var hours = Math.floor(minutes / 60);
      if (hours < 24) return hours + "h";
      var days = Math.floor(hours / 24);
      if (days < 7) return days + "d";
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    }

    function escapeHtml(text) {
      var div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }

    function formatFileSize(bytes) {
      if (bytes < 1024) return bytes + " B";
      if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
      return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    function refreshIcons() {
      if (window.lucide) lucide.createIcons();
    }

    /**
     * Build a DOM element from an HTML string. This is used instead of
     * innerHTML on live containers so that we always go through the
     * browser's HTML parser without directly assigning to innerHTML of
     * user-visible containers (all interpolated values are escaped via
     * escapeHtml before reaching this helper).
     */
    function htmlToFragment(htmlString) {
      var template = document.createElement("template");
      template.innerHTML = htmlString;
      return template.content;
    }

    // --------------------------------------------------------- API Helper
    function apiFetch(url, options) {
      options = options || {};
      var csrfToken = document.querySelector(
        "#chat-panel input[name=csrfmiddlewaretoken]"
      ).value;
      var defaults = {
        headers: {
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
      };
      // If body is FormData, don't set Content-Type (browser sets boundary)
      // If body is string/object, set Content-Type to application/json
      if (options.body && !(options.body instanceof FormData)) {
        defaults.headers["Content-Type"] = "application/json";
        if (typeof options.body === "object") {
          options.body = JSON.stringify(options.body);
        }
      }
      var mergedHeaders = Object.assign(
        {},
        defaults.headers,
        options.headers || {}
      );
      var merged = Object.assign({}, defaults, options, {
        headers: mergedHeaders,
      });
      return fetch(url, merged).then(function (r) {
        if (!r.ok) throw r;
        return r.json();
      });
    }

    // ------------------------------------------------------- Panel Control
    function openPanel() {
      panel.classList.add("open");
      fab.classList.add("hidden");
      overlay.classList.add("active");
      if (!conversations.length) {
        loadConversations();
      }
    }

    function closePanel() {
      panel.classList.remove("open");
      fab.classList.remove("hidden");
      overlay.classList.remove("active");
    }

    function showView(name) {
      var views = document.querySelectorAll(".chat-view");
      views.forEach(function (v) {
        v.classList.remove("active");
      });
      var target = document.getElementById("chat-view-" + name);
      if (target) target.classList.add("active");
      currentView = name;

      // If returning to list, reload conversations
      if (name === "list") {
        loadConversations();
        currentConversation = null;
      }
    }

    // -------------------------------------------------- Conversation List
    function loadConversations() {
      return apiFetch("/api/messages/conversations/").then(function (data) {
        conversations = data.conversations || [];
        renderConversationList();
        updateFabBadgeFromList();
        return conversations;
      });
    }

    function renderConversationList() {
      if (!conversations.length) {
        convEmpty.style.display = "";
        // Clear any existing conversation items
        var items = conversationListEl.querySelectorAll(".conversation-item");
        items.forEach(function (item) {
          item.remove();
        });
        refreshIcons();
        return;
      }
      convEmpty.style.display = "none";

      var html = "";
      conversations.forEach(function (conv) {
        var avatarContent = "";
        var avatarClass = "conv-avatar";
        var colorDot = "";

        if (conv.type === "broadcast") {
          avatarContent = '<i data-lucide="megaphone"></i>';
        } else if (conv.type === "crew") {
          avatarContent = '<i data-lucide="users"></i>';
          if (conv.crew_color) {
            colorDot =
              '<span class="crew-dot" style="background:' +
              escapeHtml(conv.crew_color) +
              '"></span>';
          }
        } else {
          var initial = (conv.title || "?").charAt(0).toUpperCase();
          avatarContent = "<span>" + escapeHtml(initial) + "</span>";
        }

        var lastMsg = conv.last_message
          ? escapeHtml(
              conv.last_message.length > 40
                ? conv.last_message.substring(0, 40) + "..."
                : conv.last_message
            )
          : '<span style="opacity:0.5">No messages yet</span>';

        var timeTxt = conv.updated_at ? timeAgo(conv.updated_at) : "";

        var unreadBadge =
          conv.unread_count > 0
            ? '<span class="unread-badge">' + conv.unread_count + "</span>"
            : "";

        html +=
          '<div class="conversation-item" data-conv-id="' +
          conv.id +
          '">' +
          '<div class="' +
          avatarClass +
          '">' +
          avatarContent +
          colorDot +
          "</div>" +
          '<div class="conv-info">' +
          '<div class="conv-header-row">' +
          '<span class="conv-name">' +
          escapeHtml(conv.title || "Conversation") +
          "</span>" +
          '<span class="conv-time">' +
          timeTxt +
          "</span>" +
          "</div>" +
          '<div class="conv-preview-row">' +
          '<span class="conv-preview">' +
          lastMsg +
          "</span>" +
          unreadBadge +
          "</div>" +
          "</div>" +
          "</div>";
      });

      // Preserve the empty element and replace the rest
      var items = conversationListEl.querySelectorAll(".conversation-item");
      items.forEach(function (item) {
        item.remove();
      });
      conversationListEl.appendChild(htmlToFragment(html));
      refreshIcons();

      // Click handlers
      conversationListEl
        .querySelectorAll(".conversation-item")
        .forEach(function (el) {
          el.addEventListener("click", function () {
            var convId = this.getAttribute("data-conv-id");
            openConversation(parseInt(convId, 10));
          });
        });
    }

    function updateFabBadge() {
      return apiFetch("/api/messages/unread-count/").then(function (data) {
        var count = data.unread_count || 0;
        if (count > 0) {
          fabBadge.textContent = count > 99 ? "99+" : count;
          fabBadge.style.display = "";
        } else {
          fabBadge.style.display = "none";
        }
      });
    }

    function updateFabBadgeFromList() {
      var total = 0;
      conversations.forEach(function (c) {
        total += c.unread_count || 0;
      });
      if (total > 0) {
        fabBadge.textContent = total > 99 ? "99+" : total;
        fabBadge.style.display = "";
      } else {
        fabBadge.style.display = "none";
      }
    }

    // --------------------------------------------------------- Chat View
    function openConversation(id) {
      showView("chat");
      currentMessages = [];
      lastMessageTimestamp = null;
      hasMoreMessages = false;
      // Clear message area
      while (chatMessages.firstChild) {
        chatMessages.removeChild(chatMessages.firstChild);
      }
      chatLoading.style.display = "";
      chatMessages.appendChild(chatLoading);

      // Clear input state
      messageInput.value = "";
      messageInput.style.height = "auto";
      pendingAttachments = [];
      attachmentPreview.style.display = "none";
      while (attachmentPreview.firstChild) {
        attachmentPreview.removeChild(attachmentPreview.firstChild);
      }
      btnSend.disabled = true;

      return apiFetch("/api/messages/conversations/" + id + "/").then(
        function (data) {
          currentConversation = data.conversation || { id: id };
          chatTitle.textContent =
            currentConversation.title || "Conversation";
          currentMessages = data.messages || [];
          hasMoreMessages = data.has_more || false;

          chatLoading.style.display = "none";
          renderMessages(currentMessages);
          scrollToBottom();
          markRead(id);

          // Track last message timestamp
          if (currentMessages.length) {
            lastMessageTimestamp =
              currentMessages[currentMessages.length - 1].created_at;
          }
        }
      );
    }

    function buildMessageHtml(msg, prevSenderId) {
      var isOwn = msg.sender && msg.sender.id == userId;
      var sideClass = isOwn ? "own" : "other";
      var showName =
        !isOwn &&
        currentConversation &&
        (currentConversation.type === "crew" ||
          currentConversation.type === "broadcast") &&
        msg.sender &&
        msg.sender.id !== prevSenderId;

      var nameHtml = showName
        ? '<div class="msg-sender-name">' +
          escapeHtml(msg.sender.name || "Unknown") +
          "</div>"
        : "";

      var contentHtml = "";
      if (msg.is_deleted) {
        contentHtml =
          '<div class="msg-deleted"><i data-lucide="trash-2" style="width:14px;height:14px"></i> This message was deleted</div>';
      } else {
        contentHtml =
          '<div class="msg-text">' + escapeHtml(msg.content || "") + "</div>";

        // Attachments
        if (msg.attachments && msg.attachments.length) {
          msg.attachments.forEach(function (att) {
            var isImage =
              att.content_type && att.content_type.startsWith("image/");
            if (isImage) {
              contentHtml +=
                '<div class="msg-attachment-img">' +
                '<a href="' +
                escapeHtml(att.url) +
                '" target="_blank" rel="noopener">' +
                '<img src="' +
                escapeHtml(att.url) +
                '" alt="' +
                escapeHtml(att.filename) +
                '" loading="lazy">' +
                "</a></div>";
            } else {
              contentHtml +=
                '<div class="msg-attachment-file">' +
                '<a href="' +
                escapeHtml(att.url) +
                '" target="_blank" rel="noopener" download>' +
                '<i data-lucide="file" style="width:16px;height:16px"></i> ' +
                escapeHtml(att.filename) +
                " (" +
                formatFileSize(att.file_size || 0) +
                ")" +
                "</a></div>";
            }
          });
        }
      }

      var timeHtml =
        '<div class="msg-time">' + timeAgo(msg.created_at) + "</div>";

      return (
        '<div class="msg-bubble ' +
        sideClass +
        '" data-msg-id="' +
        msg.id +
        '">' +
        nameHtml +
        contentHtml +
        timeHtml +
        "</div>"
      );
    }

    function renderMessages(messages) {
      var html = "";
      var prevSenderId = null;

      messages.forEach(function (msg) {
        html += buildMessageHtml(msg, prevSenderId);
        prevSenderId = msg.sender ? msg.sender.id : null;
      });

      // Clear existing content and rebuild
      chatLoading.style.display = "none";
      while (chatMessages.firstChild) {
        chatMessages.removeChild(chatMessages.firstChild);
      }
      chatMessages.appendChild(htmlToFragment(html));
      chatMessages.appendChild(chatLoading);
      refreshIcons();
    }

    function appendMessage(message) {
      var isOwn = message.sender && message.sender.id == userId;
      var sideClass = isOwn ? "own" : "other";
      var showName =
        !isOwn &&
        currentConversation &&
        (currentConversation.type === "crew" ||
          currentConversation.type === "broadcast");

      var nameHtml =
        showName && message.sender
          ? '<div class="msg-sender-name">' +
            escapeHtml(message.sender.name || "Unknown") +
            "</div>"
          : "";

      var contentHtml = "";
      if (message.is_deleted) {
        contentHtml =
          '<div class="msg-deleted"><i data-lucide="trash-2" style="width:14px;height:14px"></i> This message was deleted</div>';
      } else {
        contentHtml =
          '<div class="msg-text">' +
          escapeHtml(message.content || "") +
          "</div>";

        if (message.attachments && message.attachments.length) {
          message.attachments.forEach(function (att) {
            var isImage =
              att.content_type && att.content_type.startsWith("image/");
            if (isImage) {
              contentHtml +=
                '<div class="msg-attachment-img">' +
                '<a href="' +
                escapeHtml(att.url) +
                '" target="_blank" rel="noopener">' +
                '<img src="' +
                escapeHtml(att.url) +
                '" alt="' +
                escapeHtml(att.filename) +
                '" loading="lazy">' +
                "</a></div>";
            } else {
              contentHtml +=
                '<div class="msg-attachment-file">' +
                '<a href="' +
                escapeHtml(att.url) +
                '" target="_blank" rel="noopener" download>' +
                '<i data-lucide="file" style="width:16px;height:16px"></i> ' +
                escapeHtml(att.filename) +
                " (" +
                formatFileSize(att.file_size || 0) +
                ")" +
                "</a></div>";
            }
          });
        }
      }

      var timeHtml =
        '<div class="msg-time">' + timeAgo(message.created_at) + "</div>";

      var bubbleHtml =
        '<div class="msg-bubble ' +
        sideClass +
        '" data-msg-id="' +
        message.id +
        '">' +
        nameHtml +
        contentHtml +
        timeHtml +
        "</div>";

      // Insert before the loading indicator
      chatMessages.insertBefore(htmlToFragment(bubbleHtml), chatLoading);
      refreshIcons();

      // Update last timestamp
      if (message.created_at) {
        lastMessageTimestamp = message.created_at;
      }
    }

    function scrollToBottom() {
      requestAnimationFrame(function () {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      });
    }

    function sendMessage() {
      var text = messageInput.value.trim();
      if (!text && !pendingAttachments.length) return;
      if (!currentConversation) return;

      var url =
        "/api/messages/conversations/" + currentConversation.id + "/send/";

      var body;
      if (pendingAttachments.length) {
        body = new FormData();
        body.append("content", text);
        pendingAttachments.forEach(function (file) {
          body.append("attachments", file);
        });
      } else {
        body = { content: text };
      }

      // Clear input immediately for responsiveness
      messageInput.value = "";
      messageInput.style.height = "auto";
      btnSend.disabled = true;
      var clearedAttachments = pendingAttachments.length > 0;
      pendingAttachments = [];
      if (clearedAttachments) {
        attachmentPreview.style.display = "none";
        while (attachmentPreview.firstChild) {
          attachmentPreview.removeChild(attachmentPreview.firstChild);
        }
      }

      apiFetch(url, { method: "POST", body: body })
        .then(function (data) {
          // data is the serialized message
          if (data && data.id) {
            if (!currentMessages.find(function (m) { return m.id === data.id; })) {
              appendMessage(data);
              currentMessages.push(data);
              scrollToBottom();
            }
          }
          // Refresh conversation list to update last_message preview
          loadConversations();
        })
        .catch(function (err) {
          console.error("[Messaging] Send failed:", err);
        });
    }

    function markRead(conversationId) {
      apiFetch("/api/messages/conversations/" + conversationId + "/read/", {
        method: "POST",
      }).catch(function () {
        // silent
      });
    }

    function loadOlderMessages() {
      if (isLoadingOlder || !hasMoreMessages || !currentConversation) return;
      if (!currentMessages.length) return;

      isLoadingOlder = true;
      var oldestId = currentMessages[0].id;
      var prevScrollHeight = chatMessages.scrollHeight;

      chatLoading.style.display = "";

      apiFetch(
        "/api/messages/conversations/" +
          currentConversation.id +
          "/?before=" +
          oldestId
      )
        .then(function (data) {
          var olderMsgs = data.messages || [];
          hasMoreMessages = data.has_more || false;

          if (olderMsgs.length) {
            // Prepend messages
            currentMessages = olderMsgs.concat(currentMessages);
            renderMessages(currentMessages);

            // Maintain scroll position
            var newScrollHeight = chatMessages.scrollHeight;
            chatMessages.scrollTop = newScrollHeight - prevScrollHeight;
          }

          chatLoading.style.display = "none";
          isLoadingOlder = false;
        })
        .catch(function () {
          chatLoading.style.display = "none";
          isLoadingOlder = false;
        });
    }

    // -------------------------------------------------------- New Message
    function loadMessageableUsers() {
      // Show loading state
      while (newMessageList.firstChild) {
        newMessageList.removeChild(newMessageList.firstChild);
      }
      var loadingEl = document.createElement("div");
      loadingEl.className = "chat-loading";
      var loadingSpan = document.createElement("span");
      loadingSpan.className = "loading-dots";
      loadingSpan.textContent = "Loading...";
      loadingEl.appendChild(loadingSpan);
      newMessageList.appendChild(loadingEl);

      apiFetch("/api/messages/messageable-users/").then(function (data) {
        var html = "";
        var crews = data.crews || [];
        var users = data.users || [];

        if (crews.length) {
          html += '<div class="nm-section-title">Crews</div>';
          crews.forEach(function (crew) {
            var dot = crew.color
              ? '<span class="crew-dot" style="background:' +
                escapeHtml(crew.color) +
                '"></span>'
              : "";
            html +=
              '<div class="nm-item" data-type="crew" data-id="' +
              crew.id +
              '" data-name="' +
              escapeHtml(crew.name) +
              '">' +
              '<div class="nm-avatar">' +
              '<i data-lucide="users"></i>' +
              dot +
              "</div>" +
              '<div class="nm-info">' +
              '<span class="nm-name">' +
              escapeHtml(crew.name) +
              "</span>" +
              "</div>" +
              "</div>";
          });
        }

        if (users.length) {
          html += '<div class="nm-section-title">People</div>';
          users.forEach(function (user) {
            var initial = (user.name || "?").charAt(0).toUpperCase();
            var roleLabel = user.role
              ? '<span class="nm-role">' + escapeHtml(user.role) + "</span>"
              : "";
            html +=
              '<div class="nm-item" data-type="direct" data-id="' +
              user.id +
              '" data-name="' +
              escapeHtml(user.name) +
              '">' +
              '<div class="nm-avatar"><span>' +
              escapeHtml(initial) +
              "</span></div>" +
              '<div class="nm-info">' +
              '<span class="nm-name">' +
              escapeHtml(user.name) +
              "</span>" +
              roleLabel +
              "</div>" +
              "</div>";
          });
        }

        if (!crews.length && !users.length) {
          html =
            '<div class="chat-empty"><p>No users available</p></div>';
        }

        while (newMessageList.firstChild) {
          newMessageList.removeChild(newMessageList.firstChild);
        }
        newMessageList.appendChild(htmlToFragment(html));
        refreshIcons();

        // Click handlers
        newMessageList.querySelectorAll(".nm-item").forEach(function (el) {
          el.addEventListener("click", function () {
            var type = this.getAttribute("data-type");
            var targetId = this.getAttribute("data-id");
            startConversation(type, parseInt(targetId, 10));
          });
        });
      });
    }

    function startConversation(type, targetId) {
      var body = {};
      if (type === "crew") {
        body.type = "crew";
        body.crew_id = targetId;
      } else {
        body.type = "direct";
        body.user_id = targetId;
      }

      apiFetch("/api/messages/conversations/", {
        method: "POST",
        body: body,
      }).then(function (data) {
        var convId = data.id || (data.conversation && data.conversation.id);
        if (convId) {
          // Reload conversations so the list includes the new one
          loadConversations().then(function () {
            openConversation(convId);
            // Resubscribe realtime if available
            if (window._messagingResubscribe) {
              window._messagingResubscribe();
            }
          });
        }
      });
    }

    function filterUsers(query) {
      var items = newMessageList.querySelectorAll(".nm-item");
      var q = (query || "").toLowerCase();
      items.forEach(function (el) {
        var name = (el.getAttribute("data-name") || "").toLowerCase();
        el.style.display = name.indexOf(q) !== -1 ? "" : "none";
      });
      // Also toggle section titles visibility
      var sections = newMessageList.querySelectorAll(".nm-section-title");
      sections.forEach(function (section) {
        var next = section.nextElementSibling;
        var hasVisible = false;
        while (next && !next.classList.contains("nm-section-title")) {
          if (next.style.display !== "none") hasVisible = true;
          next = next.nextElementSibling;
        }
        section.style.display = hasVisible ? "" : "none";
      });
    }

    // ------------------------------------------------------- Attachments
    function handleAttachmentSelect(event) {
      var files = event.target.files;
      if (!files || !files.length) return;

      for (var i = 0; i < files.length; i++) {
        pendingAttachments.push(files[i]);
      }
      renderAttachmentPreviews();
      btnSend.disabled = false;

      // Reset file input so the same file can be selected again
      fileInput.value = "";
    }

    function renderAttachmentPreviews() {
      if (!pendingAttachments.length) {
        attachmentPreview.style.display = "none";
        while (attachmentPreview.firstChild) {
          attachmentPreview.removeChild(attachmentPreview.firstChild);
        }
        return;
      }
      attachmentPreview.style.display = "";
      var html = "";
      pendingAttachments.forEach(function (file, idx) {
        var isImage = file.type && file.type.startsWith("image/");
        if (isImage) {
          html +=
            '<div class="att-preview-item" data-idx="' +
            idx +
            '">' +
            '<img src="' +
            URL.createObjectURL(file) +
            '" alt="' +
            escapeHtml(file.name) +
            '">' +
            '<button type="button" class="att-remove" data-idx="' +
            idx +
            '" title="Remove">&times;</button>' +
            "</div>";
        } else {
          html +=
            '<div class="att-preview-item att-file" data-idx="' +
            idx +
            '">' +
            '<i data-lucide="file" style="width:24px;height:24px"></i>' +
            '<span class="att-name">' +
            escapeHtml(
              file.name.length > 15
                ? file.name.substring(0, 12) + "..."
                : file.name
            ) +
            "</span>" +
            '<button type="button" class="att-remove" data-idx="' +
            idx +
            '" title="Remove">&times;</button>' +
            "</div>";
        }
      });

      while (attachmentPreview.firstChild) {
        attachmentPreview.removeChild(attachmentPreview.firstChild);
      }
      attachmentPreview.appendChild(htmlToFragment(html));
      refreshIcons();

      // Remove handlers
      attachmentPreview
        .querySelectorAll(".att-remove")
        .forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            removeAttachment(parseInt(this.getAttribute("data-idx"), 10));
          });
        });
    }

    function removeAttachment(index) {
      pendingAttachments.splice(index, 1);
      renderAttachmentPreviews();
      if (!pendingAttachments.length && !messageInput.value.trim()) {
        btnSend.disabled = true;
      }
    }

    // ------------------------------------------------- Supabase Realtime
    function initRealtime() {
      var url = panel.dataset.supabaseUrl;
      var key = panel.dataset.supabaseKey;

      if (!url || !key || !window.supabase) {
        console.log(
          "[Messaging] Supabase not configured, falling back to polling"
        );
        startPolling();
        return;
      }

      var client = window.supabase.createClient(url, key);

      function subscribe(conversationIds) {
        if (realtimeChannel) {
          client.removeChannel(realtimeChannel);
        }
        if (!conversationIds.length) return;

        realtimeChannel = client
          .channel("messages-" + userId)
          .on(
            "postgres_changes",
            {
              event: "INSERT",
              schema: "public",
              table: "messaging_message",
              filter:
                "conversation_id=in.(" + conversationIds.join(",") + ")",
            },
            handleRealtimeMessage
          )
          .subscribe();
      }

      function handleRealtimeMessage(payload) {
        var msg = payload.new;
        // If sender is current user (we already have the message), skip
        if (msg.sender_id == userId) return;

        if (
          currentConversation &&
          currentView === "chat" &&
          msg.conversation_id == currentConversation.id
        ) {
          // Fetch the full serialized message
          apiFetch(
            "/api/messages/conversations/" +
              msg.conversation_id +
              "/?since=" +
              encodeURIComponent(lastMessageTimestamp || "")
          ).then(function (data) {
            if (data.messages && data.messages.length) {
              data.messages.forEach(function (m) {
                if (
                  !currentMessages.find(function (existing) {
                    return existing.id === m.id;
                  })
                ) {
                  appendMessage(m);
                  currentMessages.push(m);
                }
              });
              scrollToBottom();
              markRead(currentConversation.id);
            }
          });
        }
        // Refresh conversation list and badge
        loadConversations();
        updateFabBadge();
      }

      // Subscribe after loading conversations
      loadConversations().then(function () {
        subscribe(
          conversations.map(function (c) {
            return c.id;
          })
        );
      });

      // Expose resubscribe for when new conversations are created
      window._messagingResubscribe = function () {
        subscribe(
          conversations.map(function (c) {
            return c.id;
          })
        );
      };
    }

    function startPolling() {
      pollInterval = setInterval(function () {
        if (document.hidden) return; // Don't poll when tab is hidden

        loadConversations();
        updateFabBadge();

        // If in chat view, fetch new messages
        if (
          currentView === "chat" &&
          currentConversation &&
          lastMessageTimestamp
        ) {
          apiFetch(
            "/api/messages/conversations/" +
              currentConversation.id +
              "/?since=" +
              encodeURIComponent(lastMessageTimestamp)
          ).then(function (data) {
            if (data.messages && data.messages.length) {
              data.messages.forEach(function (m) {
                if (
                  !currentMessages.find(function (existing) {
                    return existing.id === m.id;
                  })
                ) {
                  appendMessage(m);
                  currentMessages.push(m);
                }
              });
              scrollToBottom();
              markRead(currentConversation.id);
            }
          });
        }
      }, 5000);
    }

    // --------------------------------------------------- Event Listeners

    // FAB
    fab.addEventListener("click", openPanel);

    // Close buttons
    ["btn-close-list", "btn-close-chat", "btn-close-new"].forEach(
      function (id) {
        document.getElementById(id).addEventListener("click", closePanel);
      }
    );

    // Overlay click
    overlay.addEventListener("click", closePanel);

    // Escape key
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePanel();
    });

    // Back buttons
    document
      .getElementById("btn-back-chat")
      .addEventListener("click", function () {
        showView("list");
      });
    document
      .getElementById("btn-back-new")
      .addEventListener("click", function () {
        showView("list");
      });

    // New message
    document
      .getElementById("btn-new-message")
      .addEventListener("click", function () {
        showView("new");
        loadMessageableUsers();
      });

    // Send
    btnSend.addEventListener("click", sendMessage);

    // Enter to send (Shift+Enter for newline)
    messageInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Auto-resize textarea
    messageInput.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
      // Enable/disable send button
      btnSend.disabled = !this.value.trim() && !pendingAttachments.length;
    });

    // Attachments
    document
      .getElementById("btn-attach")
      .addEventListener("click", function () {
        fileInput.click();
      });
    fileInput.addEventListener("change", handleAttachmentSelect);

    // Load older messages on scroll to top
    chatMessages.addEventListener("scroll", function () {
      if (this.scrollTop < 50 && !isLoadingOlder && hasMoreMessages) {
        loadOlderMessages();
      }
    });

    // Search filter in new message
    userSearch.addEventListener("input", function (e) {
      filterUsers(e.target.value);
    });

    // -------------------------------------------------------- Initialize
    // Initial badge update
    updateFabBadge();
    // Start realtime or polling
    initRealtime();
  });
})();

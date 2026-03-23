// Service Worker for FieldLgx push notifications

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(clients.claim());
});

self.addEventListener('push', function(event) {
  var data = { title: 'FieldLgx', body: 'New notification', url: '/notifications/inbox/' };
  try {
    if (event.data) data = event.data.json();
  } catch (e) {
    if (event.data) data.body = event.data.text();
  }

  var options = {
    body: data.body || 'New notification',
    icon: '/static/img/icon-192.png',
    badge: '/static/img/icon-192.png',
    tag: data.tag || 'fieldlgx-notification',
    data: { url: data.url || '/notifications/inbox/' },
    vibrate: [200, 100, 200],
    actions: [{ action: 'open', title: 'View' }],
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'FieldLgx', options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/notifications/inbox/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(windowClients) {
      // Focus existing tab if possible
      for (var i = 0; i < windowClients.length; i++) {
        var client = windowClients[i];
        if (client.url.indexOf(url) >= 0 && 'focus' in client) {
          return client.focus();
        }
      }
      // Open new tab
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

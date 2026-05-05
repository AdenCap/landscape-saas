/* ==========================================================================
   FieldLgx Calendar — Premium JS
   FullCalendar 6, touch drag, rain push, modal transitions
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
  // ── Global refs from inline template vars ──
  // Read CSRF fresh every time (cookie can change after session refresh)
  function getCSRF() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }
  var csrf = (typeof CSRF_TOKEN !== 'undefined' && CSRF_TOKEN) ? CSRF_TOKEN : getCSRF();
  var isOwner = typeof IS_OWNER !== 'undefined' ? IS_OWNER : false;
  var weatherData = typeof WEATHER_DATA !== 'undefined' ? WEATHER_DATA : {};

  // ── Device-aware view persistence ──
  var isMobile = window.matchMedia('(max-width: 768px)').matches;
  var isTablet = window.matchMedia('(min-width: 769px) and (max-width: 1024px)').matches;
  var STORAGE_VIEW = isMobile ? 'fieldlgx_calendar_view_mobile' : (isTablet ? 'fieldlgx_calendar_view_tablet' : 'fieldlgx_calendar_view');
  var STORAGE_DATE = 'fieldlgx_calendar_date';

  // Wave 4: mobile default is now Day view (was listMonth) — matches Jobber/Housecall Pro patterns.
  // Users who already have a saved view preference keep it (savedView wins over defaultView).
  var defaultView = isMobile ? 'timeGridDay' : (isTablet ? 'timeGridWeek' : 'timeGridWeek');
  var savedView = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_VIEW)) || null;
  var initialView = savedView || defaultView;

  // Always start on today — don't restore saved date
  var initialDate = null;

  // ── Color mode (must be before calendar init so eventDidMount can read it) ──
  var STORAGE_COLOR_MODE = 'fieldlgx_calendar_color_mode';
  var colorMode = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_COLOR_MODE)) || 'status';

  // ── Split by crew (side-by-side lanes for overlapping jobs at same time) ──
  // Raises eventMaxStack from 3 → 12 so all overlapping crews are visible in a single time slot
  // rather than being collapsed into a "+N more" indicator. Also auto-switches colorMode to
  // 'assignee' so each crew has a distinct color. No multi-calendar instances — uses
  // FullCalendar's native side-by-side overlap layout.
  var STORAGE_CREW_LANES = 'fieldlgx_calendar_crew_lanes';
  var crewLanesMode = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_CREW_LANES) === '1');

  // ── Helper functions ──
  function pad2(n) { return String(n).padStart(2, '0'); }

  var BUSINESS_TZ = document.body.getAttribute('data-tz') || 'America/New_York';

  function formatDateStr(d) {
    if (!d || !d.getFullYear) return '';
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function formatDateTimeStr(d) {
    return formatDateStr(d) + 'T' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }

  function formatTimeShort(d) {
    try {
      return d.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        timeZone: BUSINESS_TZ
      }).replace(' ', '').toLowerCase();
    } catch (e) {
      // Fallback if timezone not supported
      var h = d.getHours();
      var m = d.getMinutes();
      var ampm = h >= 12 ? 'p' : 'a';
      if (h === 0) h = 12; else if (h > 12) h -= 12;
      return m === 0 ? h + ampm : h + ':' + pad2(m) + ampm;
    }
  }

  function nextWeekday(dateStr) {
    var d = new Date(dateStr + 'T12:00:00');
    d.setDate(d.getDate() + 1);
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
    return formatDateStr(d);
  }

  function nextDay(dateStr) {
    var d = new Date(dateStr + 'T12:00:00');
    d.setDate(d.getDate() + 1);
    return formatDateStr(d);
  }

  function showToast(message, type) {
    type = type || 'success';
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function() { toast.classList.add('toast-exit'); }, 3500);
    setTimeout(function() { toast.remove(); }, 4000);
  }

  // ── Recurring event dialog ──
  function showRecurringDialog(onThisOnly, onAllFuture, onCancel) {
    // Remove any existing dialog
    var existing = document.getElementById('recurring-dialog-overlay');
    if (existing) existing.remove();

    var overlay = document.createElement('div');
    overlay.id = 'recurring-dialog-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;';

    var card = document.createElement('div');
    card.style.cssText = 'background:var(--surface,#1a1a1a);border:1px solid var(--border,#333);border-radius:12px;padding:24px;max-width:340px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);';

    var title = document.createElement('div');
    title.style.cssText = 'font-size:16px;font-weight:700;margin-bottom:6px;color:var(--text,#fff);';
    title.textContent = 'Recurring Job';
    card.appendChild(title);

    var desc = document.createElement('div');
    desc.style.cssText = 'font-size:13px;color:var(--text-muted,#999);margin-bottom:20px;';
    desc.textContent = 'This is a recurring job. How do you want to apply this change?';
    card.appendChild(desc);

    var btnWrap = document.createElement('div');
    btnWrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;';

    var btnThis = document.createElement('button');
    btnThis.className = 'btn btn-secondary';
    btnThis.style.cssText = 'width:100%;text-align:left;padding:12px 16px;font-size:13px;';
    btnThis.textContent = 'Just this one';
    btnThis.addEventListener('click', function() { overlay.remove(); onThisOnly(); });

    var btnFuture = document.createElement('button');
    btnFuture.className = 'btn btn-primary';
    btnFuture.style.cssText = 'width:100%;text-align:left;padding:12px 16px;font-size:13px;';
    btnFuture.textContent = 'This and all future jobs';
    btnFuture.addEventListener('click', function() { overlay.remove(); onAllFuture(); });

    var btnCancel = document.createElement('button');
    btnCancel.style.cssText = 'width:100%;text-align:center;padding:10px;font-size:12px;color:var(--text-muted,#999);background:none;border:none;cursor:pointer;margin-top:4px;';
    btnCancel.textContent = 'Cancel';
    btnCancel.addEventListener('click', function() { overlay.remove(); onCancel(); });

    btnWrap.appendChild(btnThis);
    btnWrap.appendChild(btnFuture);
    btnWrap.appendChild(btnCancel);
    card.appendChild(btnWrap);
    overlay.appendChild(card);

    // Close on backdrop click
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) { overlay.remove(); onCancel(); }
    });

    document.body.appendChild(overlay);
  }

  // ══════════════════════════════════════════════════════════════
  // FullCalendar Initialization
  // ══════════════════════════════════════════════════════════════

  var calEl = document.getElementById('calendar');

  var calendar = new FullCalendar.Calendar(calEl, {
    // Expose globally for custom header controls
    __postInit: true,
    headerToolbar: isMobile
      ? { left: 'prev,next', center: '', right: 'timeGridDay,timeGridWeek,dayGridMonth,listMonth' }
      : { left: 'prev,next', center: 'title', right: 'timeGridDay,timeGridWeek,dayGridMonth,listWeek' },
    initialView: initialView,
    initialDate: initialDate || undefined,
    views: {
      dayGridMonth: { buttonText: 'Month' },
      timeGridWeek: { buttonText: 'Week' },
      timeGridDay: { buttonText: 'Day' },
      listWeek: { buttonText: 'List' },
      listMonth: { buttonText: 'Schedule', duration: { months: 1 } }
    },
    slotMinTime: '06:00:00',
    slotMaxTime: '21:00:00',
    slotDuration: '00:30:00',
    snapDuration: '00:05:00',
    scrollTime: '07:00:00',
    scrollTimeReset: false,
    stickyHeaderDates: true,
    allDaySlot: true,
    expandRows: true,
    nowIndicator: true,
    eventDisplay: 'block',
    editable: isOwner,
    eventDurationEditable: isOwner,
    // Wave 4: faster long-press on mobile for quicker drag engagement (500ms felt sluggish)
    longPressDelay: isMobile ? 300 : 500,
    selectable: isOwner,
    selectMirror: true,
    navLinks: true,
    navLinkDayClick: 'timeGridDay',
    height: isMobile ? 'calc(100vh - 130px)' : 'calc(100vh - 120px)',
    dayMaxEvents: isMobile ? 3 : 5,
    slotEventOverlap: false,
    // When crew-lanes mode is ON, raise the cap so all overlapping crews render side-by-side.
    // On mobile, lanes mode is ignored (screen too narrow for useful side-by-side layout).
    eventMaxStack: isMobile ? 2 : (crewLanesMode ? 12 : 3),

    // ── Event source (date-range filtered + AbortController) ──
    events: function(info, successCallback, failureCallback) {
      if (window._calFetchCtrl) window._calFetchCtrl.abort();
      window._calFetchCtrl = new AbortController();
      // Pass visible date range so backend only returns jobs in view
      var params = [
        'start=' + formatDateStr(info.start),
        'end=' + formatDateStr(info.end)
      ];
      var svc = document.getElementById('filter-services');
      var crew = document.getElementById('filter-crews');
      var emp = document.getElementById('filter-employees');
      var searchEl = document.getElementById('calendar-search');
      var payFilter = document.getElementById('filter-payment');
      if (svc && svc.value) params.push('services=' + encodeURIComponent(svc.value));
      if (crew && crew.value) params.push('crews=' + encodeURIComponent(crew.value));
      if (emp && emp.value) params.push('employees=' + encodeURIComponent(emp.value));
      if (payFilter && payFilter.value) params.push('payment=' + encodeURIComponent(payFilter.value));
      if (searchEl && searchEl.value.trim()) params.push('search=' + encodeURIComponent(searchEl.value.trim()));
      var qs = '?' + params.join('&');
      fetch('/jobs/calendar/events/' + qs, { signal: window._calFetchCtrl.signal })
        .then(function(r) { return r.json(); })
        .then(successCallback)
        .catch(function(err) { if (err.name !== 'AbortError') failureCallback(err); });
    },

    // ── Persist view/date + update month label ──
    datesSet: function(info) {
      // Update custom month label in mobile header
      var label = document.getElementById('cal-month-label');
      if (label) {
        var d = info.view.currentStart || info.start;
        var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
        var monthName = months[d.getMonth()];
        var yr = d.getFullYear();
        var now = new Date();
        label.textContent = (yr === now.getFullYear()) ? monthName : monthName + ' ' + yr;
      }
      // Persist to localStorage
      if (typeof localStorage !== 'undefined') {
        try {
          localStorage.setItem(STORAGE_VIEW, info.view.type);
          var start = info.view.currentStart;
          if (start && start.getFullYear) {
            localStorage.setItem(STORAGE_DATE, formatDateStr(start));
          }
        } catch (e) {}
      }
      // Update date input
      var inp = document.getElementById('calendar-goto-date');
      if (inp) inp.value = formatDateStr(calendar.getDate());
    },

    // ── Lightweight event card rendering (performance-optimized) ──
    eventContent: function(arg) {
      var container = document.createElement('div');
      container.className = 'cal-event-card';

      var props = arg.event.extendedProps || {};
      var isCompleted = props.status === 'completed';
      if (isCompleted) container.classList.add('cal-event--completed');
      if (props.type === 'meeting') container.classList.add('cal-event--meeting');
      if (arg.view.type.indexOf('list') === 0) container.classList.add('cal-event-card--list');

      // Customer name (primary text)
      var name = document.createElement('span');
      name.className = 'cal-event-name';
      name.textContent = props.customer || arg.event.title;
      container.appendChild(name);

      // Address (secondary — only in list/time views, not month)
      if (arg.view.type !== 'dayGridMonth' && arg.event.title) {
        var addr = document.createElement('span');
        addr.className = 'cal-event-addr';
        addr.textContent = arg.event.title.replace(/^✓\s*/, '');
        container.appendChild(addr);
      }

      // Completed checkmark + duration
      if (isCompleted) {
        var check = document.createElement('span');
        check.className = 'cal-event-check';
        check.textContent = props.duration ? '\u2713 ' + props.duration : '\u2713';
        container.appendChild(check);
      }

      return { domNodes: [container] };
    },

    // ── Click date → navigate (month) or create (day/week) ──
    dateClick: function(info) {
      if (info.view.type === 'dayGridMonth') {
        // Month view: navigate to that day
        calendar.changeView('timeGridDay', info.dateStr);
      } else if (isOwner) {
        // Day/Week view: open quick-create at the clicked time
        openQuickCreate(info.date, info.dateStr, info.jsEvent, info.view.type);
      }
    },

    // ── Drag-select time range → quick-create with time pre-filled ──
    select: function(info) {
      if (!isOwner) return;
      if (info.view.type === 'dayGridMonth') return;
      openQuickCreate(info.start, info.startStr, info.jsEvent, info.view.type, info.end);
      calendar.unselect();
    },

    // ── Drag event to reschedule ──
    eventDrop: function(info) {
      var jobId = info.event.extendedProps?.jobId;
      if (!jobId) return;
      // Guard against rapid double-fires (debounce at 120ms)
      if (window._calDropBusy) { info.revert(); return; }
      window._calDropBusy = true;
      setTimeout(function() { window._calDropBusy = false; }, 120);

      var props = info.event.extendedProps || {};
      var start = info.event.start;
      var end = info.event.end;
      var payload = { scheduled_date: info.event.allDay ? formatDateStr(start) : formatDateTimeStr(start) };
      if (info.event.allDay) payload.all_day = true;
      if (end && !info.event.allDay) {
        payload.scheduled_end = formatDateTimeStr(end);
        payload.scheduled_end_date = formatDateStr(end) > formatDateStr(start) ? formatDateStr(end) : null;
      }
      // Multi-day: send end date for all-day spanning events
      if (end && info.event.allDay) {
        // FullCalendar exclusive end — subtract 1 day to get the actual last day
        var lastDay = new Date(end.getTime() - 86400000);
        if (lastDay > start) {
          payload.scheduled_end_date = formatDateStr(lastDay);
        } else {
          payload.scheduled_end_date = null;
        }
      }

      function doReschedule(applyFuture) {
        payload.apply_to_future = !!applyFuture;
        fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
          body: JSON.stringify(payload)
        }).then(function(r) {
          if (!r.ok) {
            info.revert();
            showToast('Could not move job (status ' + r.status + ')', 'error');
            return;
          }
          return r.json();
        }).then(function(data) {
          if (!data) return; // Already handled above
          // Optimistic update: the event already moved locally from the drag.
          // Only refetch when multiple events changed (bulk future-shift) or when
          // the recurring parent was shifted (so next generate_jobs() is correct).
          if (data.future_moved > 0 || data.parent_shifted) {
            calendar.refetchEvents();
            showToast('Moved this + ' + (data.future_moved || 0) + ' future jobs');
          } else {
            showToast('Job rescheduled');
          }
        }).catch(function(err) {
          info.revert();
          showToast('Error: ' + (err.message || 'could not move job'), 'error');
        });
      }

      // If recurring, ask user whether to move just this one or all future
      if (props.recurring) {
        showRecurringDialog(
          function() { doReschedule(false); },
          function() { doReschedule(true); },
          function() { info.revert(); }
        );
      } else {
        doReschedule(false);
      }
    },

    // ── Resize event (change duration) ──
    eventResize: function(info) {
      var jobId = info.event.extendedProps?.jobId;
      if (!jobId) return;
      var props = info.event.extendedProps || {};
      var start = info.event.start;
      var end = info.event.end;
      var payload = {};
      if (info.event.allDay) {
        // Multi-day resize in month view
        payload.scheduled_date = formatDateStr(start);
        payload.all_day = true;
        if (end) {
          var lastDay = new Date(end.getTime() - 86400000);
          if (lastDay > start) {
            payload.scheduled_end_date = formatDateStr(lastDay);
          } else {
            payload.scheduled_end_date = null;
          }
        }
      } else {
        payload.scheduled_date = formatDateTimeStr(start);
        if (end) {
          payload.scheduled_end = formatDateTimeStr(end);
          payload.scheduled_end_date = formatDateStr(end) > formatDateStr(start) ? formatDateStr(end) : null;
        }
      }
      function doResize(applyFuture) {
        payload.apply_to_future = !!applyFuture;
        fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
          body: JSON.stringify(payload)
        }).then(function(r) {
          if (!r.ok) {
            info.revert();
            showToast('Could not update duration (status ' + r.status + ')', 'error');
            return null;
          }
          return r.json();
        }).then(function(data) {
          if (!data) return;
          if (Object.prototype.hasOwnProperty.call(payload, 'scheduled_end_date') || data.future_moved > 0) {
            calendar.refetchEvents();
          }
          if (data.future_moved > 0) {
            showToast('Updated this + ' + data.future_moved + ' future jobs');
          } else {
            showToast('Duration updated');
          }
        }).catch(function() {
          info.revert();
          showToast('Could not update duration', 'error');
        });
      }

      if (props.recurring) {
        showRecurringDialog(
          function() { doResize(false); },
          function() { doResize(true); },
          function() { info.revert(); }
        );
      } else {
        doResize(false);
      }
    },

    // ── Click event → open modal ──
    eventClick: function(info) {
      info.jsEvent.preventDefault();
      var props = info.event.extendedProps || {};
      if (props.type === 'meeting' && props.meetingId) {
        openMeetingModal(props.meetingId);
        return;
      }
      if (props.jobId) openJobModal(props.jobId);
    },

    // ── Mount hooks ──
    eventDidMount: function(info) {
      var p = info.event.extendedProps || {};
      // Apply color mode directly on mount (avoids expensive setProp calls)
      if (p.type !== 'meeting') {
        var color;
        if (colorMode === 'payment') {
          // Payment mode: show paid/invoiced/draft/not_invoiced
          color = p.paymentColor || '#6b7280';
        } else if (colorMode === 'assignee') {
          // Crew/employee mode: use custom override > assignee color > fallback
          color = p.jobColorOverride || p.assigneeColor || p.crewColor || '#94a3b8';
        } else {
          // Status mode: ALWAYS use status color — ignore custom overrides
          color = p.statusColor || '#3b82f6';
        }
        if (color) {
          info.el.style.backgroundColor = color;
          info.el.style.borderColor = color;
        }
      } else {
        var bg = info.event.backgroundColor;
        if (bg) {
          info.el.style.backgroundColor = bg;
          info.el.style.borderColor = bg;
        }
      }
      // Rich tooltip with all job details for quick glance
      if (p.type === 'meeting') {
        info.el.title = (p.customer ? p.customer + ' — ' : '') + (info.event.title || 'Meeting');
      } else {
        var parts = [];
        if (p.services) parts.push(p.services);
        if (p.customer) parts.push(p.customer);
        if (info.event.title) parts.push(info.event.title.replace(/^✓\s*/, ''));
        if (p.crew && p.crew !== 'Unassigned') parts.push('Crew: ' + p.crew);
        if (p.status) parts.push('Status: ' + p.status);
        if (p.recurring && p.frequency) parts.push('Recurring: ' + p.frequency);
        if (p.duration) parts.push('Duration: ' + p.duration);
        if (p.paymentStatus) {
          var payLabels = { paid: 'Paid', invoiced: 'Invoice Sent', draft: 'Invoice Draft', not_invoiced: 'Not Invoiced' };
          parts.push('Payment: ' + (payLabels[p.paymentStatus] || p.paymentStatus));
        }
        info.el.title = parts.join('\n');
      }
    },

    // ── Weather badges, rain push, job count badges ──
    dayCellDidMount: function(info) {
      if (!info.date) return;
      var key = formatDateStr(info.date);
      var dayFrame = info.el.querySelector('.fc-daygrid-day-top');
      if (!dayFrame) return;

      dayFrame.style.display = 'flex';
      dayFrame.style.justifyContent = 'space-between';
      dayFrame.style.alignItems = 'center';

      // Weather badge (only if forecast data exists for this date)
      var w = weatherData ? weatherData[key] : null;
      if (w && w.high != null && !info.el.querySelector('.weather-badge')) {
        var badge = document.createElement('div');
        badge.className = 'weather-badge';
        badge.title = w.label + ' · Precip: ' + w.precip + '"';

        // Build weather badge content with DOM methods
        var icon = document.createElement('i');
        icon.setAttribute('data-lucide', w.icon);
        badge.appendChild(icon);
        var tempSpan = document.createElement('span');
        tempSpan.textContent = w.high + '\u00B0';
        badge.appendChild(tempSpan);
        if (w.precip > 0) {
          var rain = document.createElement('span');
          rain.className = 'weather-rain';
          badge.appendChild(rain);
        }
        dayFrame.appendChild(badge);

        // Rain day push button (owner only, precip > 0.1")
        if (isOwner && w.precip > 0.1) {
          info.el.classList.add('rain-day-cell');
          var pushBtn = document.createElement('button');
          pushBtn.className = 'rain-push-btn';
          pushBtn.textContent = 'Push \u2192';
          pushBtn.title = 'Push jobs to another day';
          pushBtn.setAttribute('data-date', key);
          pushBtn.setAttribute('data-weather-label', w.label);
          pushBtn.setAttribute('data-weather-precip', w.precip);
          pushBtn.setAttribute('data-weather-icon', w.icon);
          pushBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            openRainModal(this.getAttribute('data-date'), {
              label: this.getAttribute('data-weather-label'),
              precip: this.getAttribute('data-weather-precip'),
              icon: this.getAttribute('data-weather-icon')
            });
          });
          dayFrame.appendChild(pushBtn);
        }

        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [badge] });
      }

      // ── Job count badge (month view only, all days) ──
      if (info.view.type === 'dayGridMonth' && !info.el.querySelector('.day-job-count')) {
        var countBadge = document.createElement('span');
        countBadge.className = 'day-job-count';
        countBadge.setAttribute('data-date', key);
        dayFrame.appendChild(countBadge);
      }
    },

    // ── Update job count badges + apply color mode when events change ──
    eventsSet: function(events) {
      // Job count badges
      var counts = {};
      events.forEach(function(evt) {
        if (!evt.start) return;
        var d = formatDateStr(evt.start);
        counts[d] = (counts[d] || 0) + 1;
      });
      document.querySelectorAll('.day-job-count').forEach(function(el) {
        var d = el.getAttribute('data-date');
        var c = counts[d] || 0;
        el.textContent = c > 0 ? c : '';
        el.style.display = c > 0 ? '' : 'none';
      });
      // Colors are applied in eventDidMount — no need to call _applyColorMode here
    }
  });
  calendar.render();
  window._fc = calendar;  // expose for custom header buttons

  // Hide skeleton loader once calendar renders
  var skeleton = document.getElementById('calendar-skeleton');
  if (skeleton) skeleton.style.display = 'none';

  // ── Mobile: horizontal swipe to navigate all views ──
  if (isMobile) {
    var touchStartX = 0;
    var touchStartY = 0;
    calEl.addEventListener('touchstart', function(e) {
      if (e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
      }
    }, { passive: true });
    calEl.addEventListener('touchend', function(e) {
      var touch = e.changedTouches[0];
      var dx = touch.clientX - touchStartX;
      var dy = touch.clientY - touchStartY;
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        if (dx < 0) calendar.next(); else calendar.prev();
      }
    }, { passive: true });
  }

  // ══════════════════════════════════════════════════════════════
  // Toolbar Controls
  // ══════════════════════════════════════════════════════════════

  var gotoInp = document.getElementById('calendar-goto-date');
  if (gotoInp) gotoInp.value = initialDate || formatDateStr(calendar.getDate());

  var gotoBtn = document.getElementById('calendar-goto-btn');
  if (gotoBtn) gotoBtn.addEventListener('click', function() {
    var val = gotoInp ? gotoInp.value.trim() : '';
    if (val) calendar.gotoDate(val);
    else calendar.today();
  });

  var todayBtn = document.getElementById('calendar-today-btn');
  if (todayBtn) todayBtn.addEventListener('click', function() {
    calendar.today();
    if (gotoInp) gotoInp.value = formatDateStr(calendar.getDate());
  });

  // ── Refresh button + auto-refresh ──
  var refreshBtn = document.getElementById('cal-refresh-btn');
  var refreshLabel = refreshBtn ? refreshBtn.querySelector('.cal-refresh-label') : null;
  function doRefresh() {
    calendar.refetchEvents();
    if (isOwner && typeof loadUnscheduled === 'function') loadUnscheduled();
    // Spin animation on icon
    if (refreshBtn) {
      var icon = refreshBtn.querySelector('.material-symbols-outlined');
      if (icon) { icon.style.animation = 'spin 0.5s ease'; setTimeout(function() { icon.style.animation = ''; }, 600); }
    }
  }
  if (refreshBtn) refreshBtn.addEventListener('click', doRefresh);

  // Auto-refresh every 60 seconds when tab is visible
  var autoRefreshInterval = setInterval(function() {
    if (!document.hidden) doRefresh();
  }, 60000);
  // Clean up on page unload
  window.addEventListener('beforeunload', function() { clearInterval(autoRefreshInterval); });

  // Search (debounced)
  var searchInput = document.getElementById('calendar-search');
  var searchTimer = null;
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function() { calendar.refetchEvents(); }, 300);
    });
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); clearTimeout(searchTimer); calendar.refetchEvents(); }
    });
  }

  // Auto-apply filters on change & highlight active selections
  ['filter-crews', 'filter-employees', 'filter-services', 'filter-payment'].forEach(function(id) {
    var sel = document.getElementById(id);
    if (sel) {
      sel.addEventListener('change', function() {
        sel.classList.toggle('active-filter', !!sel.value);
        calendar.refetchEvents();
      });
    }
  });

  // ══════════════════════════════════════════════════════════════
  // Modals (CSS transition based)
  // ══════════════════════════════════════════════════════════════

  function openModal(id) {
    var overlay = document.getElementById(id);
    if (overlay) overlay.classList.add('active');
    document.body.classList.add('modal-open');
  }
  function closeModal(id) {
    var overlay = document.getElementById(id);
    if (overlay) overlay.classList.remove('active');
    // Only remove scroll lock if no other modals are active
    var anyActive = document.querySelectorAll('.modal-overlay.active');
    if (!anyActive || anyActive.length === 0) {
      document.body.classList.remove('modal-open');
    }
  }

  // Close on backdrop click
  ['job-modal', 'meeting-modal', 'rain-modal'].forEach(function(id) {
    var overlay = document.getElementById(id);
    if (overlay) {
      overlay.addEventListener('click', function(e) { if (e.target === this) closeModal(id); });
    }
  });

  // Close buttons
  document.querySelectorAll('.modal-close').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var overlay = btn.closest('.modal-overlay');
      if (overlay) overlay.classList.remove('active');
    });
  });

  // Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      ['rain-modal', 'job-modal', 'meeting-modal'].forEach(function(id) {
        var o = document.getElementById(id);
        if (o && o.classList.contains('active')) closeModal(id);
      });
    }
  });

  // Swipe-to-dismiss on mobile
  function addSwipeDismiss(overlayId) {
    var overlay = document.getElementById(overlayId);
    if (!overlay) return;
    var card = overlay.querySelector('.modal-card');
    if (!card) return;
    var startY = 0;
    card.addEventListener('touchstart', function(e) { startY = e.touches[0].clientY; }, { passive: true });
    card.addEventListener('touchmove', function(e) {
      var dy = e.touches[0].clientY - startY;
      if (dy > 0) card.style.transform = 'translateY(' + dy + 'px)';
    }, { passive: true });
    card.addEventListener('touchend', function(e) {
      var dy = e.changedTouches[0].clientY - startY;
      card.style.transform = '';
      if (dy > 80) closeModal(overlayId);
    });
  }
  addSwipeDismiss('job-modal');
  addSwipeDismiss('meeting-modal');
  addSwipeDismiss('rain-modal');

  // ── Job Modal ──
  function openJobModal(jobId) {
    openModal('job-modal');
    fetch('/jobs/calendar/job/' + jobId + '/')
      .then(function(r) { if (!r.ok) throw new Error('Failed'); return r.json(); })
      .then(function(data) {
        var job = data.job;
        var userRole = data.user_role || 'owner';
        var ownerMode = userRole === 'owner' || userRole === 'manager';

        document.getElementById('modal-address').textContent = job.address;
        document.getElementById('modal-date').textContent = job.scheduled_date || 'Unscheduled';
        var dateInput = document.getElementById('modal-date-input');
        if (dateInput) {
          dateInput.value = job.scheduled_date || '';
          dateInput.disabled = !ownerMode;
        }
        document.getElementById('modal-time').value = job.scheduled_time || '';
        document.getElementById('modal-notes').value = job.notes || '';
        document.getElementById('modal-notes').readOnly = !ownerMode;
        document.getElementById('modal-time').readOnly = !ownerMode;
        document.getElementById('modal-view-job').href = '/jobs/' + jobId + '/';
        renderJobSummary(job, data);
        loadModalNotes(jobId);

        // Owner-only sections
        var ownerOnly = document.getElementById('modal-owner-only');
        ownerOnly.style.display = ownerMode ? 'block' : 'none';
        if (ownerMode) {
          var customer = data.customer || {};
          document.getElementById('modal-customer-email').value = customer.email || '';
          document.getElementById('modal-customer-phone').value = customer.phone || '';

          // Crew select
          var crewSel = document.getElementById('modal-crew');
          crewSel.innerHTML = '<option value="">— Unassigned —</option>';
          (data.crews || []).forEach(function(c) {
            var opt = document.createElement('option');
            opt.value = c.id; opt.textContent = c.name;
            if (job.assigned_crew_id === c.id) opt.selected = true;
            crewSel.appendChild(opt);
          });

          // Employee multi-select checkboxes
          var empList = document.getElementById('modal-employee-list');
          var empSel = document.getElementById('modal-employee');
          var assignedEmpIds = job.assigned_employee_ids || [];
          empSel.innerHTML = '<option value="">— Unassigned —</option>';
          empList.innerHTML = '';
          (data.employees || []).forEach(function(e) {
            // Legacy hidden select
            var opt = document.createElement('option');
            opt.value = e.id; opt.textContent = e.name;
            if (job.assigned_to_id === e.id) opt.selected = true;
            empSel.appendChild(opt);
            // Checkbox UI
            var label = document.createElement('label');
            label.style.cssText = 'display:flex;align-items:center;gap:8px;padding:5px 4px;cursor:pointer;font-size:13px;';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = e.id;
            cb.name = 'modal_emp_cb';
            cb.checked = assignedEmpIds.indexOf(e.id) !== -1;
            cb.style.cssText = 'width:16px;height:16px;accent-color:var(--primary,#22c55e);cursor:pointer;';
            label.appendChild(cb);
            label.appendChild(document.createTextNode(e.name));
            empList.appendChild(label);
          });

          // Color picker + swatches
          var colorVal = (job.color || '').trim();
          var colorPicker = document.getElementById('modal-color-picker');
          var colorInput = document.getElementById('modal-color');
          // Reset all swatches
          document.querySelectorAll('.color-swatch').forEach(function(s) { s.classList.remove('active'); });
          if (colorVal) {
            colorInput.value = colorVal;
            var hex = colorVal.length === 4 ? '#' + colorVal[1]+colorVal[1]+colorVal[2]+colorVal[2]+colorVal[3]+colorVal[3] : colorVal;
            colorPicker.value = hex;
            // Highlight matching swatch
            var matchSwatch = document.querySelector('.color-swatch[data-color="' + colorVal.toLowerCase() + '"]');
            if (matchSwatch) matchSwatch.classList.add('active');
          } else {
            colorInput.value = '';
            colorInput.placeholder = 'Auto (status color)';
            colorPicker.value = '#94a3b8';
          }

          // Contact links
          var email = customer.email || '';
          var phone = (customer.phone || '').replace(/\D/g, '');
          document.getElementById('modal-email-link').href = email ? 'mailto:' + email : '#';
          document.getElementById('modal-email-link').style.display = email ? '' : 'none';
          document.getElementById('modal-text-link').href = phone ? 'sms:' + phone : '#';
          document.getElementById('modal-text-link').style.display = phone ? '' : 'none';
        }

        // Services
        var svcSection = document.getElementById('modal-services-section');
        var svcList = document.getElementById('modal-services-list');
        if (job.services && job.services.length) {
          svcSection.style.display = 'block';
          svcList.innerHTML = job.services.map(function(s) {
            var detail = s.detail_description ? '<small>' + escapeHtml(s.detail_description) + '</small>' : '';
            return '<li><div><strong>' + escapeHtml(s.name || 'Service') + '</strong>' + detail + '</div><span>' +
              escapeHtml(s.quantity || 1) + ' ' + escapeHtml(s.unit || 'visit') + '</span></li>';
          }).join('');
        } else { svcSection.style.display = 'none'; }

        // Images
        var imgSection = document.getElementById('modal-images-section');
        var imgGrid = document.getElementById('modal-images-grid');
        if (job.images && job.images.length) {
          imgSection.style.display = 'block';
          imgGrid.innerHTML = job.images.map(function(img) {
            return '<a href="' + img.url + '" target="_blank" rel="noopener"><img src="' + img.url + '" alt="Property" class="modal-img-thumb"></a>';
          }).join('');
        } else { imgSection.style.display = 'none'; }

        // Quick actions
        var jobActions = document.getElementById('modal-job-actions');
        var ownerActions = document.getElementById('modal-owner-actions');
        jobActions.style.display = ownerMode ? 'block' : 'none';
        ownerActions.style.display = ownerMode ? 'flex' : 'none';
        if (ownerMode) {
          var enRouteBtn = document.getElementById('modal-en-route');
          if (enRouteBtn) enRouteBtn.style.display = job.status === 'scheduled' ? '' : 'none';
          document.getElementById('modal-complete').style.display = job.status !== 'completed' ? '' : 'none';
          var uncompleteBtn = document.getElementById('modal-uncomplete');
          if (uncompleteBtn) uncompleteBtn.style.display = (job.status === 'completed' || job.status === 'in_progress') ? '' : 'none';
          var skipBtn = document.getElementById('modal-skip');
          if (skipBtn) skipBtn.style.display = (job.status === 'scheduled' || job.status === 'en_route') ? '' : 'none';
          var canInvoice = job.has_unbilled_items && job.has_services;
          var canCompleteBill = job.status === 'completed' && canInvoice;
          var billNowBtn = document.getElementById('modal-bill-now');
          if (billNowBtn) {
            billNowBtn.style.display = canInvoice ? '' : 'none';
            billNowBtn.textContent = 'Create draft invoice';
          }
          document.getElementById('modal-add-monthly').style.display = canCompleteBill ? '' : 'none';
          var markPaidWrap = document.getElementById('modal-mark-paid-wrap');
          if (markPaidWrap) markPaidWrap.style.display = canCompleteBill ? 'flex' : 'none';
        }

        document.getElementById('modal-save').style.display = ownerMode ? '' : 'none';
        var modal = document.getElementById('job-modal');
        modal.dataset.jobId = jobId;
        modal.dataset.isRecurring = job.is_recurring ? '1' : '0';
        modal.dataset.originalCrewId = job.assigned_crew_id ? String(job.assigned_crew_id) : '';
        modal.dataset.originalAssignedToId = job.assigned_to_id ? String(job.assigned_to_id) : '';
        modal.dataset.originalScheduledDate = job.scheduled_date || '';
        modal.dataset.originalScheduledTime = job.scheduled_time || '';
        modal.dataset.originalEmployeeIds = (job.assigned_employee_ids || []).map(function(id) {
          return String(id);
        }).sort().join(',');
        var delForm = document.getElementById('modal-delete-form');
        if (delForm) delForm.action = '/jobs/' + jobId + '/delete/';
      })
      .catch(function(e) {
        closeModal('job-modal');
        showToast(e.message || 'Failed to load job', 'error');
      });
  }

  function titleCaseStatus(status) {
    return (status || 'scheduled').replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
  }

  function escapeHtml(value) {
    var el = document.createElement('div');
    el.textContent = value == null ? '' : String(value);
    return el.innerHTML;
  }

  function formatJobTimeLabel(value) {
    if (!value) return '';
    var parts = value.split(':');
    var h = parseInt(parts[0], 10);
    var m = parts[1] || '00';
    var suffix = h >= 12 ? 'PM' : 'AM';
    var hour = h % 12 || 12;
    return hour + ':' + m + ' ' + suffix;
  }

  function renderJobSummary(job, data) {
    var statusPill = document.getElementById('modal-status-pill');
    var customerEl = document.getElementById('modal-customer-name');
    var addressLink = document.getElementById('modal-address-link');
    var scheduleEl = document.getElementById('modal-schedule-summary');
    var assignmentEl = document.getElementById('modal-assignment-summary');
    var servicesEl = document.getElementById('modal-services-summary');
    var notesWrap = document.getElementById('modal-notes-summary-wrap');
    var notesEl = document.getElementById('modal-notes-summary');
    if (!statusPill || !customerEl || !addressLink || !scheduleEl || !assignmentEl || !servicesEl) return;

    statusPill.textContent = titleCaseStatus(job.status);
    statusPill.className = 'job-status-pill job-status-pill--' + (job.status || 'scheduled').replace(/[^a-z0-9_-]/gi, '');

    customerEl.textContent = job.customer_name || (data.customer && data.customer.name) || 'Client';
    addressLink.textContent = job.address || 'No address';
    addressLink.href = job.address ? 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(job.address) : '#';

    var scheduleParts = [];
    if (job.scheduled_date) {
      scheduleParts.push(job.scheduled_date + (job.scheduled_end_date ? ' to ' + job.scheduled_end_date : ''));
    } else {
      scheduleParts.push('Unscheduled');
    }
    if (job.scheduled_time) {
      scheduleParts.push(formatJobTimeLabel(job.scheduled_time) + (job.scheduled_end_time ? ' - ' + formatJobTimeLabel(job.scheduled_end_time) : ''));
    }
    scheduleEl.textContent = scheduleParts.join(' · ');

    var assignment = job.assigned_crew_name || '';
    if (!assignment && job.assigned_employee_names && job.assigned_employee_names.length) {
      assignment = job.assigned_employee_names.join(', ');
    }
    if (!assignment && job.assigned_to_name) {
      assignment = job.assigned_to_name;
    }
    if (!assignment && data.crews && job.assigned_crew_id) {
      var crewMatch = data.crews.find(function(c) { return c.id === job.assigned_crew_id; });
      assignment = crewMatch ? crewMatch.name : '';
    }
    if (!assignment && data.employees && job.assigned_employee_ids && job.assigned_employee_ids.length) {
      assignment = data.employees.filter(function(e) {
        return job.assigned_employee_ids.indexOf(e.id) !== -1;
      }).map(function(e) { return e.name; }).join(', ');
    }
    assignmentEl.textContent = assignment || 'Unassigned';

    if (job.services && job.services.length) {
      servicesEl.textContent = job.services.map(function(s) { return s.name || 'Service'; }).join(', ');
    } else {
      servicesEl.textContent = 'No services';
    }

    if (job.notes && job.notes.trim()) {
      notesWrap.style.display = '';
      notesEl.textContent = job.notes.trim();
    } else {
      notesWrap.style.display = 'none';
      notesEl.textContent = '';
    }
  }

  function noteBadgeClass(type) {
    return 'note-badge note-badge--' + (type || 'job');
  }

  function noteTypeLabel(type) {
    if (type === 'property') return 'property';
    if (type === 'recurring') return 'recurring';
    return 'job';
  }

  function renderModalNotes(notes) {
    var list = document.getElementById('modal-notes-list');
    if (!list) return;
    if (!notes || !notes.length) {
      list.innerHTML = '<p class="job-notes-empty">No notes yet.</p>';
      return;
    }
    list.innerHTML = notes.map(function(n) {
      var type = n.note_type || n.type || 'job';
      var created = n.created_at ? new Date(n.created_at) : null;
      var time = created && !isNaN(created.getTime()) ? created.toLocaleDateString() + ' ' + created.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
      return '<div class="job-note-item">' +
        '<div class="job-note-meta"><span class="' + noteBadgeClass(type) + '">' + noteTypeLabel(type) + '</span>' +
        escapeHtml(n.author || '') + (time ? ' · ' + escapeHtml(time) : '') + '</div>' +
        '<p>' + escapeHtml(n.text || '') + '</p>' +
      '</div>';
    }).join('');
  }

  function loadModalNotes(jobId) {
    var list = document.getElementById('modal-notes-list');
    if (list) list.innerHTML = '<p class="job-notes-empty">Loading notes...</p>';
    fetch('/jobs/' + jobId + '/notes/', { credentials: 'same-origin' })
      .then(function(r) { return r.json(); })
      .then(function(data) { renderModalNotes(data.notes || []); })
      .catch(function() {
        if (list) list.innerHTML = '<p class="job-notes-empty">Could not load notes.</p>';
      });
  }

  // ── Meeting Modal ──
  function openMeetingModal(meetingId) {
    openModal('meeting-modal');
    fetch('/jobs/calendar/meeting/' + meetingId + '/')
      .then(function(r) { if (!r.ok) throw new Error('Failed'); return r.json(); })
      .then(function(data) {
        document.getElementById('meeting-modal-title').textContent = data.title || 'Meeting';
        var dt = data.scheduled_at ? new Date(data.scheduled_at) : null;
        document.getElementById('meeting-modal-datetime').textContent = dt ? dt.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
        document.getElementById('meeting-modal-customer').textContent = data.customer || '—';
        document.getElementById('meeting-modal-location').textContent = data.location || '—';
        document.getElementById('meeting-modal-notes').textContent = data.notes || '—';
        var editLink = document.getElementById('meeting-modal-edit');
        if (editLink) editLink.href = '/jobs/meetings/' + meetingId + '/edit/';
        var delForm = document.getElementById('meeting-modal-delete-form');
        if (delForm) delForm.action = '/jobs/meetings/' + meetingId + '/delete/';
      })
      .catch(function(e) {
        closeModal('meeting-modal');
        showToast('Failed to load meeting', 'error');
      });
  }

  // ── Modal field handlers ──
  var crewSel = document.getElementById('modal-crew');
  var empSel = document.getElementById('modal-employee');
  if (crewSel) crewSel.addEventListener('change', function() {
    if (this.value) {
      if (empSel) empSel.value = '';
      // Uncheck all employee checkboxes when crew is selected
      document.querySelectorAll('input[name="modal_emp_cb"]').forEach(function(cb) { cb.checked = false; });
    }
  });
  // When employee checkbox is checked, clear crew selection
  document.addEventListener('change', function(e) {
    if (e.target && e.target.name === 'modal_emp_cb' && e.target.checked && crewSel) {
      crewSel.value = '';
    }
  });

  var colorPicker = document.getElementById('modal-color-picker');
  var colorInput = document.getElementById('modal-color');
  if (colorPicker) colorPicker.addEventListener('input', function() { if (colorInput) colorInput.value = this.value; });
  if (colorInput) colorInput.addEventListener('input', function() {
    var v = this.value.trim();
    if (v && v.startsWith('#') && colorPicker) {
      var hex = v.length === 4 ? '#' + v[1]+v[1]+v[2]+v[2]+v[3]+v[3] : v;
      if (hex.length === 7) colorPicker.value = hex;
    }
  });
  var colorClear = document.getElementById('modal-color-clear');
  if (colorClear) colorClear.addEventListener('click', function() {
    if (colorInput) { colorInput.value = ''; colorInput.placeholder = 'Auto (status color)'; }
    if (colorPicker) colorPicker.value = '#94a3b8';
    // Clear active swatch
    document.querySelectorAll('.color-swatch').forEach(function(s) { s.classList.remove('active'); });
  });

  // Color swatches
  document.querySelectorAll('.color-swatch').forEach(function(swatch) {
    swatch.addEventListener('click', function() {
      var color = this.getAttribute('data-color');
      if (colorInput) colorInput.value = color;
      if (colorPicker) colorPicker.value = color;
      document.querySelectorAll('.color-swatch').forEach(function(s) { s.classList.remove('active'); });
      this.classList.add('active');
    });
  });

  // ── Quick actions ──
  function ajaxPost(url) {
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({})
    }).then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'Failed'); });
      return r.json();
    });
  }

  var enRouteBtn = document.getElementById('modal-en-route');
  if (enRouteBtn) enRouteBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    ajaxPost('/jobs/' + jobId + '/en-route/').then(function(d) {
      calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
      showToast(d && d.message ? d.message : 'Crew dispatched');
    }).catch(function(e) { showToast(e.message, 'error'); });
  });

  var completeBtn = document.getElementById('modal-complete');
  if (completeBtn) completeBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    ajaxPost('/jobs/' + jobId + '/complete/').then(function() {
      calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
      showToast('Job marked complete');
    }).catch(function(e) { showToast(e.message, 'error'); });
  });

  var uncompleteBtn = document.getElementById('modal-uncomplete');
  if (uncompleteBtn) uncompleteBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    if (!confirm('Revert this job back to scheduled?')) return;
    ajaxPost('/jobs/' + jobId + '/uncomplete/').then(function() {
      calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
      showToast('Job reverted to scheduled');
    }).catch(function(e) { showToast(e.message, 'error'); });
  });

  var billBtn = document.getElementById('modal-bill-now');
  if (billBtn) billBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    ajaxPost('/jobs/' + jobId + '/bill-now/').then(function(d) {
      calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
      showToast('Draft invoice created');
      if (d && d.invoice_id) {
        window.location.href = '/billing/' + d.invoice_id + '/';
      }
    }).catch(function(e) { showToast(e.message, 'error'); });
  });

  var skipModalBtn = document.getElementById('modal-skip');
  if (skipModalBtn) skipModalBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    var reason = prompt('Reason for skipping (required):');
    if (!reason || !reason.trim()) { showToast('A reason is required', 'error'); return; }
    var action = prompt('What should happen?\n1 = Skip only\n2 = Push to tomorrow\n3 = Push to next week\n\nEnter 1, 2, or 3:', '1');
    var actionMap = { '1': 'skip', '2': 'push_tomorrow', '3': 'push_next_week' };
    var actionVal = actionMap[action] || 'skip';
    fetch('/jobs/' + jobId + '/skip/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ reason: reason.trim(), action: actionVal })
    }).then(function(r) { return r.json(); }).then(function(data) {
      if (data.status === 'ok') {
        calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
        var msg = 'Job skipped';
        if (data.action === 'push_tomorrow') msg += ' — pushed to tomorrow';
        else if (data.action === 'push_next_week') msg += ' — pushed to next week';
        showToast(msg);
      } else { showToast(data.error || 'Failed', 'error'); }
    }).catch(function() { showToast('Network error', 'error'); });
  });

  var monthlyBtn = document.getElementById('modal-add-monthly');
  if (monthlyBtn) monthlyBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    ajaxPost('/jobs/' + jobId + '/add-to-monthly/').then(function(d) {
      calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
      if (d && d.invoice_id) window.location.href = '/billing/' + d.invoice_id + '/';
    }).catch(function(e) { showToast(e.message, 'error'); });
  });

  var markPaidBtn = document.getElementById('modal-mark-paid');
  if (markPaidBtn) markPaidBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    var method = document.getElementById('modal-pay-method').value;
    // Submit as a form POST to the mark_job_paid endpoint
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = '/jobs/' + jobId + '/mark-paid/';
    var csrfInp = document.createElement('input');
    csrfInp.type = 'hidden'; csrfInp.name = 'csrfmiddlewaretoken'; csrfInp.value = csrf;
    var methodInp = document.createElement('input');
    methodInp.type = 'hidden'; methodInp.name = 'payment_method'; methodInp.value = method;
    form.appendChild(csrfInp);
    form.appendChild(methodInp);
    document.body.appendChild(form);
    form.submit();
  });

  var deleteForm = document.getElementById('modal-delete-form');
  if (deleteForm) deleteForm.addEventListener('submit', function(e) {
    if (!confirm('Delete this job? This cannot be undone.')) e.preventDefault();
  });

  var modalNoteAdd = document.getElementById('modal-note-add');
  if (modalNoteAdd) modalNoteAdd.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    var textEl = document.getElementById('modal-note-text');
    var scopeEl = document.getElementById('modal-note-scope');
    var text = textEl ? textEl.value.trim() : '';
    if (!jobId || !text) return;
    fetch('/jobs/' + jobId + '/notes/add/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ text: text, scope: scopeEl ? scopeEl.value : 'job' })
    }).then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'Failed to save note'); });
      return r.json();
    }).then(function() {
      textEl.value = '';
      loadModalNotes(jobId);
      calendar.refetchEvents();
      showToast('Note saved');
    }).catch(function(e) {
      showToast(e.message || 'Failed to save note', 'error');
    });
  });

  // ── Save job modal ──
  var saveBtn = document.getElementById('modal-save');
  if (saveBtn) saveBtn.addEventListener('click', function() {
    var modal = document.getElementById('job-modal');
    var jobId = modal.dataset.jobId;
    if (!jobId) return;
    // Collect multi-employee checkboxes
    var empCheckboxes = document.querySelectorAll('input[name="modal_emp_cb"]:checked');
    var selectedEmpIds = [];
    empCheckboxes.forEach(function(cb) { selectedEmpIds.push(parseInt(cb.value, 10)); });
    selectedEmpIds.sort(function(a, b) { return a - b; });
    var dateInput = document.getElementById('modal-date-input');
    var selectedDate = dateInput && dateInput.value ? dateInput.value : '';
    var selectedTime = document.getElementById('modal-time').value || '';
    var payload = {
      assigned_crew_id: crewSel && crewSel.value ? parseInt(crewSel.value, 10) : null,
      assigned_to_id: selectedEmpIds.length ? selectedEmpIds[0] : (empSel && empSel.value ? parseInt(empSel.value, 10) : null),
      assigned_employee_ids: selectedEmpIds.length ? selectedEmpIds : undefined,
      notes: document.getElementById('modal-notes').value,
      scheduled_time: selectedTime || null,
      customer_email: document.getElementById('modal-customer-email').value,
      customer_phone: document.getElementById('modal-customer-phone').value,
      color: (colorInput ? colorInput.value.trim() : '') || null
    };
    if (selectedDate) payload.scheduled_date = selectedDate;
    var currentCrewId = payload.assigned_crew_id ? String(payload.assigned_crew_id) : '';
    var currentAssignedToId = payload.assigned_to_id ? String(payload.assigned_to_id) : '';
    var currentEmployeeIds = selectedEmpIds.map(function(id) { return String(id); }).join(',');
    var assignmentChanged = (
      currentCrewId !== (modal.dataset.originalCrewId || '') ||
      currentAssignedToId !== (modal.dataset.originalAssignedToId || '') ||
      currentEmployeeIds !== (modal.dataset.originalEmployeeIds || '')
    );
    var scheduleChanged = (
      selectedDate !== (modal.dataset.originalScheduledDate || '') ||
      selectedTime !== (modal.dataset.originalScheduledTime || '')
    );
    if (scheduleChanged && !selectedDate) {
      showToast('Choose a date before saving', 'error');
      return;
    }

    function postJson(url, body) {
      return fetch(url, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify(body || {})
      }).then(function(r) {
        if (!r.ok) {
          return r.json().then(function(d) { throw new Error((d && d.error) || 'Update failed'); });
        }
        return r.json();
      });
    }

    function buildSchedulePayload(applyScheduleToFuture) {
      var scheduleValue = selectedDate;
      if (selectedDate && selectedTime) scheduleValue = selectedDate + 'T' + selectedTime + ':00';
      return {
        scheduled_date: scheduleValue,
        all_day: selectedDate && !selectedTime,
        apply_to_future: !!applyScheduleToFuture
      };
    }

    function submitUpdate(applyAssignmentToFuture, applyScheduleToFuture) {
      if (applyAssignmentToFuture) payload.apply_assignment_to_future = true;
      var updatePayload = Object.assign({}, payload);
      if (scheduleChanged) delete updatePayload.scheduled_time;
      var request = Promise.resolve({ status: 'ok' });
      if (scheduleChanged && selectedDate) {
        request = request.then(function() {
          return postJson('/jobs/calendar/job/' + jobId + '/reschedule/', buildSchedulePayload(applyScheduleToFuture));
        });
      }
      request.then(function() {
        return postJson('/jobs/calendar/job/' + jobId + '/update/', updatePayload);
      }).then(function(data) {
          var event = calendar.getEventById(String(jobId));
          if (event && data.backgroundColor) {
            event.setProp('backgroundColor', data.backgroundColor);
            event.setProp('borderColor', data.borderColor || data.backgroundColor);
            if (data.crew != null) event.setExtendedProp('crew', data.crew);
          }
          calendar.refetchEvents();
          if (isOwner) loadUnscheduled();
          closeModal('job-modal');
          if (data.future_assignment_updated) {
            showToast('Job updated + ' + data.future_assignment_updated + ' future jobs reassigned');
          } else if (scheduleChanged && applyScheduleToFuture) {
            showToast('Job updated + future visits moved');
          } else {
            showToast('Job updated');
          }
        }).catch(function() {
          calendar.refetchEvents();
          showToast('Update failed', 'error');
        });
    }

    if (modal.dataset.isRecurring === '1' && (assignmentChanged || scheduleChanged)) {
      showRecurringDialog(
        function() { submitUpdate(false, false); },
        function() { submitUpdate(assignmentChanged, scheduleChanged); },
        function() {}
      );
      return;
    }

    submitUpdate(false, false);
  });

  // ══════════════════════════════════════════════════════════════
  // Unscheduled Panel
  // ══════════════════════════════════════════════════════════════

  function updateUnscheduledCount(count) {
    var badge = document.getElementById('unscheduled-count');
    var fabCount = document.getElementById('fab-badge');
    if (badge) badge.textContent = count;
    if (fabCount) {
      fabCount.textContent = count;
      fabCount.style.display = count > 0 ? '' : 'none';
    }
  }

  function loadUnscheduled() {
    fetch('/jobs/calendar/unscheduled/')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var list = document.getElementById('unscheduled-list');
        if (!list) return;
        var jobs = data.jobs || [];
        updateUnscheduledCount(jobs.length);

        if (jobs.length === 0) {
          list.innerHTML = '<p style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">No unscheduled jobs</p>';
          return;
        }

        var today = formatDateStr(new Date());
        list.textContent = '';
        jobs.forEach(function(j) {
          var isEstimate = j.type === 'estimate';
          var div = document.createElement('div');
          div.className = 'unscheduled-item';
          div.setAttribute('data-job-id', j.id);
          if (isEstimate) div.setAttribute('data-type', 'estimate');

          var badge = isEstimate ? '<span style="font-size:9px;font-weight:700;text-transform:uppercase;padding:2px 5px;border-radius:3px;background:rgba(34,197,94,0.15);color:#86efac;margin-right:4px;">Estimate</span>' : '';

          var info = document.createElement('div');
          info.className = 'unscheduled-item-info';
          var name = document.createElement('div');
          name.className = 'unscheduled-item-name';
          name.textContent = j.customer || 'Unknown';
          var detail = document.createElement('div');
          detail.className = 'unscheduled-item-detail';
          detail.textContent = (j.services || '') + (j.address ? ' · ' + j.address : '');
          info.appendChild(name);
          info.appendChild(detail);

          var actions = document.createElement('div');
          actions.className = 'unscheduled-item-actions';
          var dateInp = document.createElement('input');
          dateInp.type = 'date';
          dateInp.className = 'unscheduled-date';
          dateInp.value = today;
          actions.appendChild(dateInp);

          var goBtn = document.createElement('button');
          goBtn.type = 'button';
          goBtn.className = 'btn btn-primary btn-sm';
          goBtn.textContent = 'Schedule';

          if (isEstimate) {
            // For estimates, POST to schedule_from_estimate
            goBtn.addEventListener('click', function() {
              var d = dateInp.value;
              if (!d) { showToast('Pick a date', 'warning'); return; }
              var form = document.createElement('form');
              form.method = 'POST';
              form.action = '/jobs/schedule-from-estimate/' + j.id + '/';
              var csrfInp = document.createElement('input');
              csrfInp.type = 'hidden'; csrfInp.name = 'csrfmiddlewaretoken'; csrfInp.value = csrf;
              var dateField = document.createElement('input');
              dateField.type = 'hidden'; dateField.name = 'schedule_date'; dateField.value = d;
              form.appendChild(csrfInp);
              form.appendChild(dateField);
              document.body.appendChild(form);
              form.submit();
            });
          } else {
            // For jobs, use the reschedule API
            goBtn.addEventListener('click', function() {
              var d = dateInp.value;
              if (!d) { showToast('Pick a date', 'warning'); return; }
              fetch('/jobs/calendar/job/' + j.id + '/reschedule/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
                body: JSON.stringify({ scheduled_date: d })
              }).then(function(r) {
                if (r.ok) { calendar.refetchEvents(); loadUnscheduled(); showToast('Job scheduled'); }
              });
            });
          }

          actions.appendChild(goBtn);
          div.appendChild(info);
          div.appendChild(actions);
          list.appendChild(div);
        });
      });
  }
  if (isOwner) loadUnscheduled();

  // ── Unscheduled bottom section toggle ──
  var unschedToggle = document.getElementById('unscheduled-toggle');
  var unschedContent = document.getElementById('unscheduled-content');
  var unschedChevron = document.getElementById('unscheduled-chevron');
  if (unschedToggle && unschedContent) {
    unschedToggle.addEventListener('click', function() {
      var isOpen = unschedContent.style.display !== 'none';
      unschedContent.style.display = isOpen ? 'none' : 'block';
      if (unschedChevron) unschedChevron.classList.toggle('open', !isOpen);
    });
  }

  // Legacy compat — keep swipe-down dismiss wired if elements exist
  var fab = document.getElementById('unscheduled-fab');
  var panel = document.getElementById('unscheduled-panel');
  if (fab && panel) {
    var backdrop = document.getElementById('unscheduled-backdrop') || document.createElement('div');

    // Swipe-down to dismiss
    var sheetStartY = 0;
    panel.addEventListener('touchstart', function(e) { sheetStartY = e.touches[0].clientY; }, { passive: true });
    panel.addEventListener('touchmove', function(e) {
      var dy = e.touches[0].clientY - sheetStartY;
      if (dy > 0) panel.style.transform = 'translateY(' + dy + 'px)';
    }, { passive: true });
    panel.addEventListener('touchend', function(e) {
      var dy = e.changedTouches[0].clientY - sheetStartY;
      panel.style.transform = '';
      if (dy > 80) {
        panel.classList.remove('open');
        backdrop.classList.remove('visible');
      }
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Touch Drag (Pointer Events) for Unscheduled Items
  // ══════════════════════════════════════════════════════════════

  (function() {
    if (!isOwner) return;
    var dragState = null;

    function createGhost(item) {
      var ghost = document.createElement('div');
      ghost.className = 'drag-ghost';
      var info = item.querySelector('.unscheduled-item-info');
      ghost.innerHTML = info ? info.innerHTML : item.textContent;
      ghost.style.cssText = 'position:fixed;z-index:9999;pointer-events:none;padding:10px 14px;' +
        'width:' + Math.min(item.offsetWidth, 260) + 'px;font-size:12px;color:var(--text);';
      document.body.appendChild(ghost);
      return ghost;
    }

    function getDateAtPoint(x, y) {
      var el = document.elementFromPoint(x, y);
      if (!el || !el.closest) return null;
      var withDate = el.closest('[data-date]');
      if (withDate) return withDate.getAttribute('data-date');
      var dayCell = el.closest('.fc-daygrid-day');
      if (dayCell) {
        var inner = dayCell.querySelector('[data-date]');
        if (inner) return inner.getAttribute('data-date');
      }
      var timeCol = el.closest('.fc-timegrid-col');
      if (timeCol) return timeCol.getAttribute('data-date') || null;
      return null;
    }

    var highlightedCell = null;

    function highlightDrop(x, y) {
      // Hide ghost temporarily to get element underneath
      if (dragState && dragState.ghost) dragState.ghost.style.display = 'none';
      var el = document.elementFromPoint(x, y);
      if (dragState && dragState.ghost) dragState.ghost.style.display = '';
      if (!el) return;
      var cell = el.closest('.fc-daygrid-day, .fc-timegrid-col');
      if (highlightedCell && highlightedCell !== cell) highlightedCell.classList.remove('drop-target-hover');
      if (cell) {
        cell.classList.add('drop-target-hover');
        highlightedCell = cell;
      }
    }

    function clearHighlight() {
      if (highlightedCell) { highlightedCell.classList.remove('drop-target-hover'); highlightedCell = null; }
    }

    var unscheduledList = document.getElementById('unscheduled-list');
    if (!unscheduledList) return;

    unscheduledList.addEventListener('pointerdown', function(e) {
      if (e.target.closest('input, button, a, select')) return;
      var item = e.target.closest('.unscheduled-item');
      if (!item) return;
      var jobId = item.getAttribute('data-job-id');
      var itemType = item.getAttribute('data-type') || 'job';
      if (!jobId) return;

      // Capture pointer for reliable tracking
      try { item.setPointerCapture(e.pointerId); } catch(ex) {}

      var startX = e.clientX, startY = e.clientY;
      var moved = false;

      function onMove(ev) {
        var dx = ev.clientX - startX, dy = ev.clientY - startY;
        if (!moved && Math.abs(dx) + Math.abs(dy) < 10) return;
        if (!moved) {
          moved = true;
          var ghost = createGhost(item);
          var rect = item.getBoundingClientRect();
          dragState = { jobId: jobId, itemType: itemType, ghost: ghost, offsetX: startX - rect.left, offsetY: startY - rect.top, sourceEl: item };
          item.classList.add('dragging');
          item.style.animation = 'dragPulse 0.3s ease-out';
          document.body.classList.add('is-dragging');
          var calWrap = document.getElementById('calendar-wrapper');
          if (calWrap) calWrap.classList.add('drop-zone-active');
        }
        if (dragState && dragState.ghost) {
          dragState.ghost.style.left = (ev.clientX - dragState.offsetX) + 'px';
          dragState.ghost.style.top = (ev.clientY - dragState.offsetY) + 'px';
        }
        highlightDrop(ev.clientX, ev.clientY);
        ev.preventDefault();
      }

      function onUp(ev) {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        document.removeEventListener('pointercancel', onUp);
        try { item.releasePointerCapture(ev.pointerId); } catch(ex) {}
        if (dragState) {
          if (dragState.ghost) dragState.ghost.remove();
          dragState.sourceEl.classList.remove('dragging');
          dragState.sourceEl.style.animation = '';
          document.body.classList.remove('is-dragging');
          clearHighlight();
          var calWrap = document.getElementById('calendar-wrapper');
          if (calWrap) calWrap.classList.remove('drop-zone-active');

          // Get date from calendar cell underneath
          var dateStr = getDateAtPoint(ev.clientX, ev.clientY);
          if (dateStr) {
            if (dragState.itemType === 'estimate') {
              // For estimates, use the schedule-from-estimate form POST
              var form = document.createElement('form');
              form.method = 'POST';
              form.action = '/jobs/schedule-from-estimate/' + dragState.jobId + '/';
              var csrfInp = document.createElement('input');
              csrfInp.type = 'hidden'; csrfInp.name = 'csrfmiddlewaretoken'; csrfInp.value = csrf;
              var dateField = document.createElement('input');
              dateField.type = 'hidden'; dateField.name = 'schedule_date'; dateField.value = dateStr;
              form.appendChild(csrfInp);
              form.appendChild(dateField);
              document.body.appendChild(form);
              form.submit();
            } else {
              // For jobs, use the reschedule API
              fetch('/jobs/calendar/job/' + dragState.jobId + '/reschedule/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
                body: JSON.stringify({ scheduled_date: dateStr })
              }).then(function(r) {
                if (r.ok) {
                  calendar.refetchEvents();
                  loadUnscheduled();
                  showToast('Job scheduled');
                } else {
                  showToast('Could not schedule job', 'error');
                }
              }).catch(function() { showToast('Could not schedule job', 'error'); });
            }
          }
          dragState = null;
        }
      }

      document.addEventListener('pointermove', onMove, { passive: false });
      document.addEventListener('pointerup', onUp);
      document.addEventListener('pointercancel', onUp);
    });
  })();

  // ══════════════════════════════════════════════════════════════
  // Rain Day Schedule Push
  // ══════════════════════════════════════════════════════════════

  var rainModalEl = document.getElementById('rain-modal');
  var rainFromDate = '';
  var rainJobsData = [];

  function openRainModal(dateStr, weatherInfo) {
    rainFromDate = dateStr;
    // Populate weather info
    var weatherDiv = document.getElementById('rain-modal-weather');
    if (weatherDiv) {
      weatherDiv.innerHTML =
        '<div class="rain-modal-weather">' +
          '<div class="rain-modal-weather-icon"><i data-lucide="' + (weatherInfo.icon || 'cloud-rain') + '"></i></div>' +
          '<div class="rain-modal-weather-info">' +
            '<div class="rain-modal-weather-label">' + (weatherInfo.label || 'Rain') + '</div>' +
            '<div class="rain-modal-weather-detail">' + dateStr + ' · ' + weatherInfo.precip + '" precipitation</div>' +
          '</div>' +
        '</div>';
      if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [weatherDiv] });
    }

    // Set default push date
    var pushDateInput = document.getElementById('rain-push-date');
    if (pushDateInput) pushDateInput.value = nextWeekday(dateStr);

    // Fetch jobs for that date
    var jobsList = document.getElementById('rain-modal-jobs');
    if (jobsList) jobsList.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">Loading jobs...</p>';

    fetch('/jobs/calendar/events/?search=')
      .then(function(r) { return r.json(); })
      .then(function(events) {
        rainJobsData = events.filter(function(ev) {
          var evDate = (ev.start || '').substring(0, 10);
          return evDate === dateStr && (!ev.extendedProps || ev.extendedProps.type !== 'meeting');
        });
        if (jobsList) {
          if (rainJobsData.length === 0) {
            jobsList.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No jobs on this date.</p>';
          } else {
            jobsList.innerHTML = rainJobsData.map(function(ev, i) {
              var p = ev.extendedProps || {};
              var recurBadge = '';
              if (p.recurring && p.frequency) {
                var freqLabel = p.frequency.charAt(0).toUpperCase() + p.frequency.slice(1);
                recurBadge = '<span class="rain-job-recurring">\u{1F504} ' + freqLabel + '</span>';
              }
              return '<label class="rain-job-item">' +
                '<input type="checkbox" checked data-index="' + i + '" data-job-id="' + (p.jobId || '') + '">' +
                '<span>' + recurBadge + (p.customer || ev.title || 'Job') + (p.services ? ' \u2014 ' + p.services : '') + '</span>' +
              '</label>';
            }).join('');
          }
        }
        updateRainConfirmBtn();
        openModal('rain-modal');
      });
  }

  function updateRainConfirmBtn() {
    var btn = document.getElementById('rain-push-confirm');
    if (!btn) return;
    var checked = document.querySelectorAll('#rain-modal-jobs input[type="checkbox"]:checked');
    btn.textContent = 'Push ' + checked.length + ' job' + (checked.length !== 1 ? 's' : '');
    btn.disabled = checked.length === 0;
  }

  // Checkbox change updates button count
  if (rainModalEl) {
    rainModalEl.addEventListener('change', function(e) {
      if (e.target.type === 'checkbox') updateRainConfirmBtn();
    });
  }

  // Quick date buttons
  var rainNextBtn = document.getElementById('rain-push-next');
  if (rainNextBtn) rainNextBtn.addEventListener('click', function() {
    var inp = document.getElementById('rain-push-date');
    if (inp && rainFromDate) inp.value = nextDay(rainFromDate);
  });

  var rainWeekdayBtn = document.getElementById('rain-push-weekday');
  if (rainWeekdayBtn) rainWeekdayBtn.addEventListener('click', function() {
    var inp = document.getElementById('rain-push-date');
    if (inp && rainFromDate) inp.value = nextWeekday(rainFromDate);
  });

  // Confirm push
  var rainConfirmBtn = document.getElementById('rain-push-confirm');
  if (rainConfirmBtn) rainConfirmBtn.addEventListener('click', function() {
    var toDate = document.getElementById('rain-push-date').value;
    if (!toDate) { showToast('Pick a target date', 'warning'); return; }
    if (toDate === rainFromDate) { showToast('Target date must be different', 'warning'); return; }

    var checked = document.querySelectorAll('#rain-modal-jobs input[type="checkbox"]:checked');
    var jobIds = [];
    checked.forEach(function(cb) { if (cb.dataset.jobId) jobIds.push(parseInt(cb.dataset.jobId)); });

    if (jobIds.length === 0) { showToast('No jobs selected', 'warning'); return; }

    rainConfirmBtn.disabled = true;
    rainConfirmBtn.textContent = 'Pushing...';

    fetch('/jobs/calendar/bulk-reschedule/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
      body: JSON.stringify({ from_date: rainFromDate, to_date: toDate, job_ids: jobIds, skip_weekends: true })
    }).then(function(r) {
      if (!r.ok) throw new Error('Failed');
      return r.json();
    }).then(function(data) {
      closeModal('rain-modal');
      calendar.refetchEvents();
      if (isOwner) loadUnscheduled();
      showToast('Pushed ' + data.moved + ' job' + (data.moved !== 1 ? 's' : '') + ' to ' + data.to_date);
    }).catch(function(e) {
      showToast('Failed to push schedule', 'error');
    }).finally(function() {
      rainConfirmBtn.disabled = false;
      updateRainConfirmBtn();
    });
  });

  // Rain modal close (all buttons with .rain-modal-close class)
  document.querySelectorAll('.rain-modal-close').forEach(function(btn) {
    btn.addEventListener('click', function() { closeModal('rain-modal'); });
  });

  // ══════════════════════════════════════════════════════════════
  // Phase 2: Mobile Optimizations
  // ══════════════════════════════════════════════════════════════

  // ── 2a. Swipe Navigation (mobile only) ──
  if (isMobile && calEl) {
    var touchStartX = 0, touchStartY = 0, touchStartTime = 0;
    calEl.addEventListener('touchstart', function(e) {
      if (e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        touchStartTime = Date.now();
      }
    }, { passive: true });
    calEl.addEventListener('touchend', function(e) {
      if (e.changedTouches.length !== 1) return;
      var dx = e.changedTouches[0].clientX - touchStartX;
      var dy = e.changedTouches[0].clientY - touchStartY;
      var dt = Date.now() - touchStartTime;
      // Only trigger on fast horizontal swipes (not vertical scrolling)
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5 && dt < 400) {
        if (dx > 0) {
          calendar.prev();
        } else {
          calendar.next();
        }
      }
    }, { passive: true });
  }

  // ── 2c. Collapsible Filter Bar (mobile) ──
  if (isMobile) {
    var toolbar = document.querySelector('.calendar-toolbar');
    if (toolbar) {
      var filterGroups = toolbar.querySelectorAll('.calendar-toolbar-filters, .calendar-toolbar-right');
      var hasFilters = filterGroups.length > 0;
      if (hasFilters) {
        // Create toggle button
        var filterToggle = document.createElement('button');
        filterToggle.className = 'btn btn-secondary btn-sm calendar-filter-toggle';
        filterToggle.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg> Filters';
        filterToggle.style.cssText = 'margin: 0 auto; display: flex; align-items: center; gap: 6px;';

        // Hide filter groups initially
        filterGroups.forEach(function(fg) {
          fg.style.display = 'none';
          fg.classList.add('mobile-filter-collapsible');
        });

        // Insert toggle before first filter group
        toolbar.insertBefore(filterToggle, filterGroups[0]);

        filterToggle.addEventListener('click', function() {
          var expanded = filterToggle.classList.toggle('active');
          filterGroups.forEach(function(fg) {
            fg.style.display = expanded ? '' : 'none';
          });
        });
      }
    }
  }

  // ── 2e. Sticky Date Header ──
  if (isMobile) {
    var dateNav = document.querySelector('.calendar-date-nav');
    if (dateNav) {
      dateNav.style.position = 'sticky';
      dateNav.style.top = '0';
      dateNav.style.zIndex = '100';
      dateNav.style.background = 'var(--bg)';
      dateNav.style.paddingTop = '8px';
      dateNav.style.paddingBottom = '8px';
    }
  }

  // ── Legend crew filter ──
  var legendCrewFilter = document.getElementById('legend-crew-filter');
  if (legendCrewFilter) {
    legendCrewFilter.addEventListener('change', function() {
      var crewName = this.value;
      // Use the existing crew filter select to trigger a refetch
      var crewSelect = document.getElementById('filter-crews');
      if (crewSelect) {
        // Find crew option matching the name
        var opts = crewSelect.querySelectorAll('option');
        var found = false;
        opts.forEach(function(opt) {
          if (opt.textContent.trim() === crewName) {
            crewSelect.value = opt.value;
            found = true;
          }
        });
        if (!found) crewSelect.value = '';
        crewSelect.dispatchEvent(new Event('change'));
      } else {
        calendar.refetchEvents();
      }
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Quick-Create Popover (Google Calendar click-to-create)
  // ══════════════════════════════════════════════════════════════

  var qcPopover = document.getElementById('quick-create-popover');
  var qcOpen = false;
  var qcSearchTimer = null;

  // Expose to global scope for mobile FAB
  window.openQuickCreate = openQuickCreate;
  function openQuickCreate(dateObj, dateStr, mouseEvent, viewType, endDate) {
    if (!qcPopover) return;
    var isTimeGrid = viewType && viewType.indexOf('timeGrid') >= 0;
    var dateOnly = formatDateStr(dateObj);

    document.getElementById('qc-date').value = dateOnly;

    var timeInput = document.getElementById('qc-time');
    if (isTimeGrid && dateObj.getHours() > 0) {
      timeInput.value = pad2(dateObj.getHours()) + ':' + pad2(dateObj.getMinutes());
    } else {
      timeInput.value = '08:00';
    }

    // Reset fields
    var searchInput = document.getElementById('qc-customer-search');
    searchInput.value = '';
    searchInput.style.display = '';
    document.getElementById('qc-customer-id').value = '';
    var nameEl = document.getElementById('qc-customer-name');
    nameEl.textContent = '';
    nameEl.style.display = 'none';
    document.getElementById('qc-customer-dropdown').style.display = 'none';
    document.getElementById('qc-property-wrap').style.display = 'none';
    document.getElementById('qc-color').value = '';
    qcPopover.querySelectorAll('.qc-swatch').forEach(function(s) {
      s.classList.toggle('active', s.getAttribute('data-color') === '');
    });

    // Populate line items (multiple services)
    var linesContainer = document.getElementById('qc-lines');
    if (linesContainer) {
      while (linesContainer.firstChild) linesContainer.removeChild(linesContainer.firstChild);
      linesContainer.appendChild(qcCreateLineRow());
    }

    // Populate assignment (crews + employees)
    var assignSelect = document.getElementById('qc-assign');
    while (assignSelect.firstChild) assignSelect.removeChild(assignSelect.firstChild);
    var unOpt = document.createElement('option');
    unOpt.value = '';
    unOpt.textContent = 'Unassigned';
    assignSelect.appendChild(unOpt);
    var crews = typeof QC_CREWS !== 'undefined' ? QC_CREWS : [];
    var employees = typeof QC_EMPLOYEES !== 'undefined' ? QC_EMPLOYEES : [];
    if (crews.length) {
      var g1 = document.createElement('optgroup');
      g1.label = 'Crews';
      crews.forEach(function(c) {
        var o = document.createElement('option');
        o.value = 'crew-' + c.id;
        o.textContent = c.name;
        g1.appendChild(o);
      });
      assignSelect.appendChild(g1);
    }
    if (employees.length) {
      var g2 = document.createElement('optgroup');
      g2.label = 'Employees';
      employees.forEach(function(e) {
        var o = document.createElement('option');
        o.value = 'emp-' + e.id;
        o.textContent = e.name;
        g2.appendChild(o);
      });
      assignSelect.appendChild(g2);
    }

    // "More options" link
    var moreLink = document.getElementById('qc-more-options');
    if (moreLink) {
      moreLink.href = '/jobs/create/?date=' + dateOnly + '&time=' + (timeInput.value || '08:00');
    }

    // Always show as centered modal with backdrop
    qcPopover.style.position = '';
    qcPopover.style.left = '';
    qcPopover.style.right = '';
    qcPopover.style.top = '';
    qcPopover.style.bottom = '';
    qcPopover.style.width = '';
    qcPopover.style.borderRadius = '';
    qcPopover.classList.remove('qc-bottom-sheet');

    // Show backdrop
    var backdrop = document.getElementById('qc-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'qc-backdrop';
      backdrop.style.cssText = 'position:fixed;inset:0;z-index:1199;background:rgba(0,0,0,0.5);';
      backdrop.addEventListener('click', function() {
        qcPopover.style.display = 'none';
        backdrop.style.display = 'none';
        qcOpen = false;
        document.body.classList.remove('modal-open');
      });
      document.body.appendChild(backdrop);
    }
    backdrop.style.display = 'block';
    qcPopover.style.display = 'flex';
    qcOpen = true;
    document.body.classList.add('modal-open');
    setTimeout(function() { searchInput.focus(); }, 100);
  }

  // Populate service datalist for typeahead
  var svcDatalist = document.getElementById('qc-service-datalist');
  if (svcDatalist) {
    (typeof QC_SERVICES !== 'undefined' ? QC_SERVICES : []).forEach(function(s) {
      var o = document.createElement('option');
      o.value = s.name;
      o.setAttribute('data-id', s.id);
      svcDatalist.appendChild(o);
    });
  }

  // Wire service text input to resolve service ID
  function wireServiceInput(textInput, hiddenInput) {
    textInput.addEventListener('change', function() {
      var val = textInput.value.trim();
      var services = typeof QC_SERVICES !== 'undefined' ? QC_SERVICES : [];
      var match = services.find(function(s) { return s.name.toLowerCase() === val.toLowerCase(); });
      hiddenInput.value = match ? match.id : '';
    });
  }
  // Wire the existing first row
  var _firstText = document.querySelector('.qc-line-service-text');
  var _firstHidden = document.querySelector('input.qc-line-service[type="hidden"]');
  if (_firstText && _firstHidden) wireServiceInput(_firstText, _firstHidden);

  // Create a service line item row for quick-create
  function qcCreateLineRow() {
    var row = document.createElement('div');
    row.className = 'qc-line-row';
    var main = document.createElement('div');
    main.className = 'qc-line-main';
    var textInp = document.createElement('input');
    textInp.type = 'text'; textInp.className = 'qc-line-service-text';
    textInp.setAttribute('list', 'qc-service-datalist');
    textInp.placeholder = 'Type or select service...';
    main.appendChild(textInp);
    var detailInp = document.createElement('textarea');
    detailInp.className = 'qc-line-description';
    detailInp.rows = 2;
    detailInp.placeholder = 'Optional line details for the crew or invoice';
    main.appendChild(detailInp);
    row.appendChild(main);
    var hiddenInp = document.createElement('input');
    hiddenInp.type = 'hidden'; hiddenInp.className = 'qc-line-service'; hiddenInp.value = '';
    row.appendChild(hiddenInp);
    wireServiceInput(textInp, hiddenInp);
    var qty = document.createElement('input');
    qty.type = 'number'; qty.className = 'qc-line-qty'; qty.value = '1';
    qty.min = '0.01'; qty.step = '0.01'; qty.placeholder = 'Qty';
    row.appendChild(qty);
    var price = document.createElement('input');
    price.type = 'number'; price.className = 'qc-line-price';
    price.min = '0'; price.step = '0.01'; price.placeholder = '$';
    row.appendChild(price);
    // Remove button (not on first row)
    var container = document.getElementById('qc-lines');
    if (container && container.children.length > 0) {
      var rmBtn = document.createElement('button');
      rmBtn.type = 'button';
      rmBtn.className = 'qc-line-remove';
      rmBtn.textContent = '\u00D7';
      rmBtn.addEventListener('click', function() { row.remove(); });
      row.appendChild(rmBtn);
    }
    return row;
  }

  // Add line button
  var addLineBtn = document.getElementById('qc-add-line');
  if (addLineBtn) {
    addLineBtn.addEventListener('click', function() {
      var container = document.getElementById('qc-lines');
      if (container) container.appendChild(qcCreateLineRow());
    });
  }

  function closeQuickCreate() {
    if (!qcPopover) return;
    qcPopover.style.display = 'none';
    var backdrop = document.getElementById('qc-backdrop');
    if (backdrop) backdrop.style.display = 'none';
    qcOpen = false;
    document.body.classList.remove('modal-open');
  }

  var qcCloseBtn = document.getElementById('qc-close');
  if (qcCloseBtn) qcCloseBtn.addEventListener('click', closeQuickCreate);

  document.addEventListener('mousedown', function(e) {
    if (qcOpen && qcPopover && !qcPopover.contains(e.target)) {
      if (e.target.closest('.fc-daygrid-day, .fc-timegrid-slot, .fc-timegrid-col')) return;
      closeQuickCreate();
    }
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && qcOpen) closeQuickCreate();
  });

  // ── Customer typeahead ──
  var qcSearchEl = document.getElementById('qc-customer-search');
  var qcDrop = document.getElementById('qc-customer-dropdown');
  var qcSearchAbort = null;

  if (qcSearchEl) {
    qcSearchEl.addEventListener('input', function() {
      clearTimeout(qcSearchTimer);
      var q = this.value.trim();
      if (q.length < 1) { qcDrop.style.display = 'none'; return; }
      qcSearchTimer = setTimeout(function() {
        if (qcSearchAbort) qcSearchAbort.abort();
        qcSearchAbort = new AbortController();
        fetch('/jobs/calendar/customer-search/?q=' + encodeURIComponent(q), { signal: qcSearchAbort.signal })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            while (qcDrop.firstChild) qcDrop.removeChild(qcDrop.firstChild);
            if (!data.customers || !data.customers.length) {
              var empty = document.createElement('div');
              empty.className = 'qc-dropdown-empty';
              empty.textContent = 'No clients found';
              qcDrop.appendChild(empty);
              qcDrop.style.display = 'block';
              return;
            }
            data.customers.forEach(function(c) {
              var item = document.createElement('div');
              item.className = 'qc-dropdown-item';
              item.textContent = c.name;
              item.addEventListener('click', function() {
                qcSelectCustomer(c.id, c.name, c.properties);
              });
              qcDrop.appendChild(item);
            });
            qcDrop.style.display = 'block';
          })
          .catch(function(err) { if (err.name !== 'AbortError') qcDrop.style.display = 'none'; });
      }, 200);
    });
  }

  function qcSelectCustomer(id, name, properties) {
    document.getElementById('qc-customer-id').value = id;
    document.getElementById('qc-customer-search').style.display = 'none';
    var nEl = document.getElementById('qc-customer-name');
    nEl.textContent = name;
    nEl.style.display = 'block';
    nEl.style.cursor = 'pointer';
    // Use a named handler so we can replace it cleanly
    if (nEl._qcHandler) nEl.removeEventListener('click', nEl._qcHandler);
    nEl._qcHandler = function() {
      document.getElementById('qc-customer-search').style.display = '';
      document.getElementById('qc-customer-search').value = '';
      document.getElementById('qc-customer-search').focus();
      nEl.style.display = 'none';
      document.getElementById('qc-customer-id').value = '';
      document.getElementById('qc-property-wrap').style.display = 'none';
    };
    nEl.addEventListener('click', nEl._qcHandler);
    qcDrop.style.display = 'none';

    var propSelect = document.getElementById('qc-property-id');
    while (propSelect.firstChild) propSelect.removeChild(propSelect.firstChild);
    if (properties && properties.length) {
      if (properties.length === 1) {
        var o = document.createElement('option');
        o.value = properties[0].id;
        o.textContent = properties[0].address;
        propSelect.appendChild(o);
      } else {
        var d = document.createElement('option');
        d.value = '';
        d.textContent = 'Select property';
        propSelect.appendChild(d);
        properties.forEach(function(p) {
          var o = document.createElement('option');
          o.value = p.id;
          o.textContent = p.address;
          propSelect.appendChild(o);
        });
      }
      document.getElementById('qc-property-wrap').style.display = '';
    }
  }

  window.addEventListener('quickClientCreated', function(e) {
    var data = e.detail || {};
    if (!data.customer) return;
    qcSelectCustomer(data.customer.id, data.customer.name, data.properties || []);
  });

  window.addEventListener('quickPropertyCreated', function(e) {
    var data = e.detail || {};
    var property = data.property;
    if (!property) return;
    var currentCustomerId = document.getElementById('qc-customer-id').value;
    if (data.customer && currentCustomerId && String(data.customer.id) !== String(currentCustomerId)) return;
    var propSelect = document.getElementById('qc-property-id');
    if (!propSelect) return;
    var opt = document.createElement('option');
    opt.value = property.id;
    opt.textContent = property.address;
    opt.selected = true;
    propSelect.appendChild(opt);
    document.getElementById('qc-property-wrap').style.display = '';
  });

  // ── Color swatches ──
  if (qcPopover) {
    qcPopover.querySelectorAll('.qc-swatch').forEach(function(swatch) {
      swatch.addEventListener('click', function() {
        document.getElementById('qc-color').value = this.getAttribute('data-color') || '';
        qcPopover.querySelectorAll('.qc-swatch').forEach(function(s) { s.classList.remove('active'); });
        this.classList.add('active');
      });
    });
  }

  // ── Submit: create job via AJAX ──
  // Event type tabs
  var qcTypeBtns = document.querySelectorAll('.qc-type-btn');
  qcTypeBtns.forEach(function(btn) {
    btn.addEventListener('click', function() {
      qcTypeBtns.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var type = btn.dataset.type;
      document.getElementById('qc-event-type').value = type;
      var titleEl = document.getElementById('qc-title-text');
      var customerField = document.getElementById('qc-customer-field');
      var noteTitleWrap = document.getElementById('qc-note-title-wrap');
      var linesField = document.getElementById('qc-lines') ? document.getElementById('qc-lines').parentElement : null;
      var clientOptional = document.getElementById('qc-client-optional');
      var moreOptions = document.getElementById('qc-more-options');

      if (type === 'job') {
        titleEl.textContent = 'New Job';
        if (customerField) customerField.style.display = '';
        if (noteTitleWrap) noteTitleWrap.style.display = 'none';
        if (linesField) linesField.style.display = '';
        if (clientOptional) clientOptional.style.display = 'none';
        if (moreOptions) { moreOptions.style.display = ''; moreOptions.href = '/jobs/create/'; }
      } else if (type === 'meeting') {
        titleEl.textContent = 'New Meeting';
        if (customerField) customerField.style.display = '';
        if (noteTitleWrap) noteTitleWrap.style.display = '';
        if (linesField) linesField.style.display = 'none';
        if (clientOptional) clientOptional.style.display = '';
        if (moreOptions) { moreOptions.style.display = ''; moreOptions.href = '/jobs/meetings/create/'; }
      } else {
        titleEl.textContent = 'New Note';
        if (customerField) customerField.style.display = 'none';
        if (noteTitleWrap) noteTitleWrap.style.display = '';
        if (linesField) linesField.style.display = 'none';
        if (clientOptional) clientOptional.style.display = 'none';
        if (moreOptions) moreOptions.style.display = 'none';
      }
    });
  });

  var qcSubmitBtn = document.getElementById('qc-submit');
  if (qcSubmitBtn) {
    qcSubmitBtn.addEventListener('click', function() {
      var eventType = document.getElementById('qc-event-type').value;
      var customerId = document.getElementById('qc-customer-id').value;
      var propertyId = document.getElementById('qc-property-id').value;
      var dateVal = document.getElementById('qc-date').value;
      var timeVal = document.getElementById('qc-time').value;
      var colorVal = document.getElementById('qc-color').value;
      var assignVal = document.getElementById('qc-assign').value;

      if (eventType === 'meeting') {
        // Create meeting
        var noteTitle = (document.getElementById('qc-note-title').value || '').trim();
        if (!noteTitle) { showToast('Enter a title for the meeting', 'error'); return; }
        var payload = {
          title: noteTitle,
          scheduled_date: dateVal,
          scheduled_time: timeVal || null,
          customer_id: customerId ? parseInt(customerId) : null,
        };
        qcSubmitBtn.disabled = true;
        qcSubmitBtn.textContent = 'Creating\u2026';
        fetch('/jobs/meetings/create/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
          body: JSON.stringify(payload)
        }).then(function(r) { return r.json().then(function(d) { return {ok:r.ok,data:d}; }); })
        .then(function(result) {
          qcSubmitBtn.disabled = false;
          qcSubmitBtn.textContent = 'Create';
          if (result.ok) { closeQuickCreate(); calendar.refetchEvents(); showToast('Meeting created'); }
          else { showToast(result.data.error || 'Failed', 'error'); }
        }).catch(function() { qcSubmitBtn.disabled = false; qcSubmitBtn.textContent = 'Create'; showToast('Network error', 'error'); });
        return;
      }

      if (eventType === 'note') {
        // Create a calendar note (no customer needed — uses meeting model)
        var noteTitle = (document.getElementById('qc-note-title').value || '').trim();
        if (!noteTitle) { showToast('Enter a title', 'error'); return; }
        var payload = {
          title: noteTitle,
          scheduled_date: dateVal,
          scheduled_time: timeVal || null,
          customer_id: null,
        };
        qcSubmitBtn.disabled = true;
        qcSubmitBtn.textContent = 'Creating\u2026';
        fetch('/jobs/meetings/create/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
          body: JSON.stringify(payload)
        }).then(function(r) { return r.json().then(function(d) { return {ok:r.ok,data:d}; }); })
        .then(function(result) {
          qcSubmitBtn.disabled = false;
          qcSubmitBtn.textContent = 'Create';
          if (result.ok) { closeQuickCreate(); calendar.refetchEvents(); showToast('Note added to calendar'); }
          else { showToast(result.data.error || 'Failed', 'error'); }
        }).catch(function() { qcSubmitBtn.disabled = false; qcSubmitBtn.textContent = 'Create'; showToast('Network error', 'error'); });
        return;
      }

      // Default: create job
      var lineRows = document.querySelectorAll('#qc-lines .qc-line-row');
      var services = [];
      lineRows.forEach(function(row) {
        var svcId = row.querySelector('.qc-line-service').value;
        var svcText = row.querySelector('.qc-line-service-text');
        var svcName = svcText ? svcText.value.trim() : '';
        var svcDescriptionEl = row.querySelector('.qc-line-description');
        var svcDescription = svcDescriptionEl ? svcDescriptionEl.value.trim() : '';
        var qty = parseFloat(row.querySelector('.qc-line-qty').value) || 1;
        var price = row.querySelector('.qc-line-price').value;
        if (svcId) {
          var item = { service_id: parseInt(svcId), quantity: qty };
          if (svcDescription) item.detail_description = svcDescription;
          if (price !== '' && price !== null) item.unit_price = parseFloat(price);
          services.push(item);
        } else if (svcName) {
          // Typed service name without matching an existing service
          var item = { service_name: svcName, quantity: qty };
          if (svcDescription) item.detail_description = svcDescription;
          if (price !== '' && price !== null) item.unit_price = parseFloat(price);
          services.push(item);
        }
      });

      if (!customerId) { showToast('Select a client', 'error'); return; }
      if (!propertyId) { showToast('Select a property', 'error'); return; }
      if (services.length === 0) { showToast('Add at least one service', 'error'); return; }

      var payload = {
        customer_id: parseInt(customerId),
        property_id: parseInt(propertyId),
        service_id: services[0].service_id || null,
        services: services,
        scheduled_date: dateVal,
        scheduled_time: timeVal || null,
        color: colorVal || null,
      };

      if (assignVal && assignVal.indexOf('crew-') === 0) {
        payload.assigned_crew_id = parseInt(assignVal.replace('crew-', ''));
      } else if (assignVal && assignVal.indexOf('emp-') === 0) {
        payload.assigned_to_id = parseInt(assignVal.replace('emp-', ''));
      }

      qcSubmitBtn.disabled = true;
      qcSubmitBtn.textContent = 'Creating\u2026';

      fetch('/jobs/calendar/quick-create/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify(payload)
      })
      .then(function(r) { return r.json().then(function(d) { return {ok:r.ok, data:d}; }); })
      .then(function(result) {
        qcSubmitBtn.disabled = false;
        qcSubmitBtn.textContent = 'Create';
        if (result.ok && result.data.status === 'ok') {
          closeQuickCreate();
          calendar.refetchEvents();
          showToast('Job created');
        } else {
          showToast(result.data.error || 'Failed to create job', 'error');
        }
      })
      .catch(function() {
        qcSubmitBtn.disabled = false;
        qcSubmitBtn.textContent = 'Create';
        showToast('Network error', 'error');
      });
    });
  }

  // ══════════════════════════════════════════════════════════════
  // Color Mode Toggle (By Status vs By Crew/Employee)
  // ══════════════════════════════════════════════════════════════

  // Apply color mode by refetching events (eventDidMount applies colors on re-render)
  window._applyColorMode = function() {
    calendar.refetchEvents();
  };

  var toggleContainer = document.getElementById('color-mode-toggle');
  if (toggleContainer) {
    toggleContainer.querySelectorAll('.color-mode-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.mode === colorMode);
    });
    toggleContainer.addEventListener('click', function(e) {
      var btn = e.target.closest('.color-mode-btn');
      if (!btn) return;
      colorMode = btn.dataset.mode;
      try { localStorage.setItem(STORAGE_COLOR_MODE, colorMode); } catch(ex) {}
      toggleContainer.querySelectorAll('.color-mode-btn').forEach(function(b) {
        b.classList.toggle('active', b.dataset.mode === colorMode);
      });
      _applyColorMode();
      updateLegend();
    });
  }

  // New header color toggle (works on both mobile and desktop)
  var calColorToggle = document.getElementById('cal-color-toggle');
  if (calColorToggle) {
    calColorToggle.querySelectorAll('.cal-color-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.mode === colorMode);
    });
    calColorToggle.addEventListener('click', function(e) {
      var btn = e.target.closest('.cal-color-btn');
      if (!btn) return;
      colorMode = btn.dataset.mode;
      try { localStorage.setItem(STORAGE_COLOR_MODE, colorMode); } catch(ex) {}
      calColorToggle.querySelectorAll('.cal-color-btn').forEach(function(b) {
        b.classList.toggle('active', b.dataset.mode === colorMode);
      });
      // Sync desktop toggle too
      if (toggleContainer) {
        toggleContainer.querySelectorAll('.color-mode-btn').forEach(function(b) {
          b.classList.toggle('active', b.dataset.mode === colorMode);
        });
      }
      _applyColorMode();
      updateLegend();
    });
  }

  // ── "Split by crew" toggle — raises eventMaxStack so overlapping crews render side-by-side ──
  var splitCrewsBtn = document.getElementById('cal-split-crews');
  if (splitCrewsBtn) {
    function _applyLanesBtnStyle() {
      if (crewLanesMode) {
        splitCrewsBtn.style.background = 'var(--primary)';
        splitCrewsBtn.style.color = '#0a0a0a';
      } else {
        splitCrewsBtn.style.background = '';
        splitCrewsBtn.style.color = '';
      }
    }
    _applyLanesBtnStyle();

    splitCrewsBtn.addEventListener('click', function() {
      // Mobile: no-op — button is hidden via cal-hide-mobile, but guard anyway
      if (isMobile) return;
      crewLanesMode = !crewLanesMode;
      try { localStorage.setItem(STORAGE_CREW_LANES, crewLanesMode ? '1' : '0'); } catch(ex) {}
      // Apply new stack limit without rebuilding the calendar
      calendar.setOption('eventMaxStack', crewLanesMode ? 12 : 3);
      // Auto-switch to assignee color mode when turning ON, so each crew has a distinct color.
      // Only switch from 'status' → 'assignee' (leave 'payment' alone if the user chose it).
      if (crewLanesMode && colorMode === 'status') {
        colorMode = 'assignee';
        try { localStorage.setItem(STORAGE_COLOR_MODE, colorMode); } catch(ex) {}
        // Sync both color-mode toggle UIs
        if (toggleContainer) {
          toggleContainer.querySelectorAll('.color-mode-btn').forEach(function(b) {
            b.classList.toggle('active', b.dataset.mode === colorMode);
          });
        }
        if (calColorToggle) {
          calColorToggle.querySelectorAll('.cal-color-btn').forEach(function(b) {
            b.classList.toggle('active', b.dataset.mode === colorMode);
          });
        }
        if (typeof _applyColorMode === 'function') _applyColorMode();
        if (typeof updateLegend === 'function') updateLegend();
      }
      _applyLanesBtnStyle();
      showToast(crewLanesMode ? 'Split by crew — ON' : 'Split by crew — OFF');
    });
  }

  function updateLegend() {
    var statusLegend = document.getElementById('cal-legend-status');
    var crewLegend = document.getElementById('cal-legend-crew');
    var paymentLegend = document.getElementById('cal-legend-payment');
    if (statusLegend) statusLegend.style.display = colorMode === 'status' ? 'flex' : 'none';
    if (crewLegend) crewLegend.style.display = colorMode === 'assignee' ? 'flex' : 'none';
    if (paymentLegend) paymentLegend.style.display = colorMode === 'payment' ? 'flex' : 'none';
  }
  updateLegend();

});

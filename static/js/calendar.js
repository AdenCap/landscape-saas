/* ==========================================================================
   FieldLgx Calendar — Premium JS
   FullCalendar 6, touch drag, rain push, modal transitions
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
  // ── Global refs from inline template vars ──
  var csrf = CSRF_TOKEN || (function() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  })();
  var isOwner = typeof IS_OWNER !== 'undefined' ? IS_OWNER : false;
  var weatherData = typeof WEATHER_DATA !== 'undefined' ? WEATHER_DATA : {};

  // ── Device-aware view persistence ──
  var isMobile = window.matchMedia('(max-width: 768px)').matches;
  var isTablet = window.matchMedia('(min-width: 769px) and (max-width: 1024px)').matches;
  var STORAGE_VIEW = isMobile ? 'fieldlgx_calendar_view_mobile' : (isTablet ? 'fieldlgx_calendar_view_tablet' : 'fieldlgx_calendar_view');
  var STORAGE_DATE = 'fieldlgx_calendar_date';

  var defaultView = isMobile ? 'listMonth' : (isTablet ? 'timeGridWeek' : 'timeGridWeek');
  var savedView = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_VIEW)) || null;
  var initialView = savedView || defaultView;

  // Always start on today — don't restore saved date
  var initialDate = null;

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
    scrollTime: '07:00:00',
    scrollTimeReset: false,
    stickyHeaderDates: true,
    allDaySlot: false,
    expandRows: true,
    nowIndicator: true,
    eventDisplay: 'block',
    editable: isOwner,
    eventDurationEditable: isOwner,
    longPressDelay: 500,
    selectable: isOwner,
    selectMirror: true,
    navLinks: true,
    navLinkDayClick: 'timeGridDay',
    height: isMobile ? 'calc(100vh - 130px)' : 'calc(100vh - 140px)',
    dayMaxEvents: isMobile ? 3 : 5,

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
      if (svc && svc.value) params.push('services=' + encodeURIComponent(svc.value));
      if (crew && crew.value) params.push('crews=' + encodeURIComponent(crew.value));
      if (emp && emp.value) params.push('employees=' + encodeURIComponent(emp.value));
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
      var start = info.event.start;
      var end = info.event.end;
      var payload = { scheduled_date: info.event.allDay ? formatDateStr(start) : formatDateTimeStr(start) };
      if (end && !info.event.allDay) payload.scheduled_end = formatDateTimeStr(end);
      fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(payload)
      }).then(function(r) {
        if (!r.ok) { info.revert(); return; }
        showToast('Job rescheduled');
      }).catch(function() { info.revert(); });
    },

    // ── Resize event (change duration) ──
    eventResize: function(info) {
      var jobId = info.event.extendedProps?.jobId;
      if (!jobId) return;
      var start = info.event.start;
      var end = info.event.end;
      var payload = { scheduled_date: formatDateTimeStr(start) };
      if (end) payload.scheduled_end = formatDateTimeStr(end);
      fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(payload)
      }).then(function(r) {
        if (!r.ok) { info.revert(); return; }
        showToast('Duration updated');
      }).catch(function() { info.revert(); });
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
      var bg = info.event.backgroundColor;
      var border = info.event.borderColor;
      if (bg) info.el.style.backgroundColor = bg;
      if (border) info.el.style.borderColor = border;
      var p = info.event.extendedProps || {};
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
      // Color mode applied only on toggle click, not every event load
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
  ['filter-crews', 'filter-employees', 'filter-services'].forEach(function(id) {
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
        var ownerMode = userRole === 'owner';

        document.getElementById('modal-address').textContent = job.address;
        document.getElementById('modal-date').textContent = job.scheduled_date || 'Unscheduled';
        document.getElementById('modal-time').value = job.scheduled_time || '';
        document.getElementById('modal-notes').value = job.notes || '';
        document.getElementById('modal-notes').readOnly = !ownerMode;
        document.getElementById('modal-time').readOnly = !ownerMode;
        document.getElementById('modal-view-job').href = '/jobs/' + jobId + '/';

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
            return '<li>' + (s.name || '—') + ' — ' + s.quantity + ' ' + (s.unit || 'visit') + '</li>';
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
          var canBill = job.status === 'completed' && job.has_unbilled_items && job.has_services;
          document.getElementById('modal-bill-now').style.display = canBill ? '' : 'none';
          document.getElementById('modal-add-monthly').style.display = canBill ? '' : 'none';
        }

        document.getElementById('modal-save').style.display = ownerMode ? '' : 'none';
        document.getElementById('job-modal').dataset.jobId = jobId;
        var delForm = document.getElementById('modal-delete-form');
        if (delForm) delForm.action = '/jobs/' + jobId + '/delete/';
      })
      .catch(function(e) {
        closeModal('job-modal');
        showToast(e.message || 'Failed to load job', 'error');
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
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
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

  var billBtn = document.getElementById('modal-bill-now');
  if (billBtn) billBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    ajaxPost('/jobs/' + jobId + '/bill-now/').then(function() {
      calendar.refetchEvents(); if (isOwner) loadUnscheduled(); closeModal('job-modal');
      showToast('Invoice sent');
    }).catch(function(e) { showToast(e.message, 'error'); });
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

  var deleteForm = document.getElementById('modal-delete-form');
  if (deleteForm) deleteForm.addEventListener('submit', function(e) {
    if (!confirm('Delete this job? This cannot be undone.')) e.preventDefault();
  });

  // ── Save job modal ──
  var saveBtn = document.getElementById('modal-save');
  if (saveBtn) saveBtn.addEventListener('click', function() {
    var jobId = document.getElementById('job-modal').dataset.jobId;
    if (!jobId) return;
    // Collect multi-employee checkboxes
    var empCheckboxes = document.querySelectorAll('input[name="modal_emp_cb"]:checked');
    var selectedEmpIds = [];
    empCheckboxes.forEach(function(cb) { selectedEmpIds.push(parseInt(cb.value, 10)); });
    var payload = {
      assigned_crew_id: crewSel && crewSel.value ? parseInt(crewSel.value, 10) : null,
      assigned_to_id: selectedEmpIds.length ? selectedEmpIds[0] : (empSel && empSel.value ? parseInt(empSel.value, 10) : null),
      assigned_employee_ids: selectedEmpIds.length ? selectedEmpIds : undefined,
      notes: document.getElementById('modal-notes').value,
      scheduled_time: document.getElementById('modal-time').value || null,
      customer_email: document.getElementById('modal-customer-email').value,
      customer_phone: document.getElementById('modal-customer-phone').value,
      color: (colorInput ? colorInput.value.trim() : '') || null
    };
    fetch('/jobs/calendar/job/' + jobId + '/update/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(payload)
    }).then(function(r) { return r.ok ? r.json() : Promise.reject(new Error('Update failed')); })
      .then(function(data) {
        var event = calendar.getEventById(String(jobId));
        if (event && data.backgroundColor) {
          event.setProp('backgroundColor', data.backgroundColor);
          event.setProp('borderColor', data.borderColor || data.backgroundColor);
          if (data.crew != null) event.setExtendedProp('crew', data.crew);
        }
        calendar.refetchEvents();
        if (isOwner) loadUnscheduled();
        closeModal('job-modal');
        showToast('Job updated');
      }).catch(function() {
        calendar.refetchEvents();
        showToast('Update failed', 'error');
      });
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
        list.innerHTML = jobs.map(function(j) {
          return '<div class="unscheduled-item" data-job-id="' + j.id + '">' +
            '<span class="unscheduled-drag-handle" aria-hidden="true">⋮⋮</span>' +
            '<div class="unscheduled-item-info">' +
              '<div class="unscheduled-item-name">' + (j.customer || 'Unknown') + '</div>' +
              '<div class="unscheduled-item-detail">' + (j.address || '') + (j.services ? ' · ' + j.services : '') + '</div>' +
            '</div>' +
            '<div class="unscheduled-item-actions">' +
              '<input type="date" class="unscheduled-date" data-job-id="' + j.id + '" value="' + today + '">' +
              '<button type="button" class="btn btn-primary btn-sm schedule-btn" data-job-id="' + j.id + '">Go</button>' +
            '</div>' +
          '</div>';
        }).join('');

        // Schedule button clicks
        list.querySelectorAll('.schedule-btn').forEach(function(btn) {
          btn.addEventListener('click', function() {
            var jobId = btn.dataset.jobId;
            var row = btn.closest('.unscheduled-item');
            var dateInp = row.querySelector('.unscheduled-date');
            var dateStr = dateInp ? dateInp.value : '';
            if (!dateStr) { showToast('Pick a date first', 'warning'); return; }
            fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
              method: 'POST', credentials: 'same-origin',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
              body: JSON.stringify({ scheduled_date: dateStr })
            }).then(function(r) {
              if (r.ok) {
                calendar.refetchEvents();
                loadUnscheduled();
                showToast('Job scheduled');
              }
            });
          });
        });
      });
  }
  if (isOwner) loadUnscheduled();

  // ── Panel toggle (desktop) ──
  var toggleBtn = document.getElementById('panel-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function() {
      var panel = document.getElementById('unscheduled-panel');
      if (panel) panel.classList.toggle('collapsed');
    });
  }

  // ── Mobile FAB + bottom sheet ──
  var fab = document.getElementById('unscheduled-fab');
  var panel = document.getElementById('unscheduled-panel');
  if (fab && panel) {
    var backdrop = document.getElementById('unscheduled-backdrop') || (function() {
      var el = document.createElement('div');
      el.className = 'unscheduled-backdrop';
      document.body.appendChild(el);
      return el;
    })();

    fab.addEventListener('click', function() {
      panel.classList.add('open');
      backdrop.classList.add('visible');
    });

    backdrop.addEventListener('click', function() {
      panel.classList.remove('open');
      backdrop.classList.remove('visible');
    });

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
      if (!jobId) return;

      var startX = e.clientX, startY = e.clientY;
      var moved = false;

      function onMove(ev) {
        var dx = ev.clientX - startX, dy = ev.clientY - startY;
        if (!moved && Math.abs(dx) + Math.abs(dy) < 10) return;
        if (!moved) {
          moved = true;
          var ghost = createGhost(item);
          var rect = item.getBoundingClientRect();
          dragState = { jobId: jobId, ghost: ghost, offsetX: startX - rect.left, offsetY: startY - rect.top, sourceEl: item };
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
        if (dragState) {
          if (dragState.ghost) dragState.ghost.remove();
          dragState.sourceEl.classList.remove('dragging');
          dragState.sourceEl.style.animation = '';
          document.body.classList.remove('is-dragging');
          clearHighlight();
          var calWrap = document.getElementById('calendar-wrapper');
          if (calWrap) calWrap.classList.remove('drop-zone-active');

          // Hide ghost to get element underneath
          var dateStr = getDateAtPoint(ev.clientX, ev.clientY);
          if (dateStr) {
            fetch('/jobs/calendar/job/' + dragState.jobId + '/reschedule/', {
              method: 'POST', credentials: 'same-origin',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
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
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
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

    // Position near click
    if (mouseEvent && !isMobile) {
      var x = mouseEvent.clientX;
      var y = mouseEvent.clientY;
      var pw = 360, ph = 480;
      var vw = window.innerWidth, vh = window.innerHeight;
      if (x + pw > vw - 20) x = vw - pw - 20;
      if (x < 20) x = 20;
      if (y + ph > vh - 20) y = Math.max(20, vh - ph - 20);
      qcPopover.style.position = 'fixed';
      qcPopover.style.left = x + 'px';
      qcPopover.style.top = y + 'px';
      qcPopover.style.bottom = '';
      qcPopover.style.right = '';
      qcPopover.style.width = '';
      qcPopover.style.borderRadius = '';
      qcPopover.classList.remove('qc-bottom-sheet');
    } else {
      qcPopover.style.position = 'fixed';
      qcPopover.style.left = '0';
      qcPopover.style.right = '0';
      qcPopover.style.bottom = '0';
      qcPopover.style.top = '';
      qcPopover.style.width = '100%';
      qcPopover.style.borderRadius = '20px 20px 0 0';
      qcPopover.classList.add('qc-bottom-sheet');
    }

    qcPopover.style.display = 'block';
    qcOpen = true;
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
    var textInp = document.createElement('input');
    textInp.type = 'text'; textInp.className = 'qc-line-service-text';
    textInp.setAttribute('list', 'qc-service-datalist');
    textInp.placeholder = 'Type or select service...';
    textInp.style.flex = '1';
    row.appendChild(textInp);
    var hiddenInp = document.createElement('input');
    hiddenInp.type = 'hidden'; hiddenInp.className = 'qc-line-service'; hiddenInp.value = '';
    row.appendChild(hiddenInp);
    wireServiceInput(textInp, hiddenInp);
    var qty = document.createElement('input');
    qty.type = 'number'; qty.className = 'qc-line-qty'; qty.value = '1';
    qty.min = '0.01'; qty.step = '0.01'; qty.placeholder = 'Qty';
    qty.style.width = '50px';
    row.appendChild(qty);
    var price = document.createElement('input');
    price.type = 'number'; price.className = 'qc-line-price';
    price.min = '0'; price.step = '0.01'; price.placeholder = '$';
    price.style.width = '60px';
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
    qcOpen = false;
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
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
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
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
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
        var qty = parseFloat(row.querySelector('.qc-line-qty').value) || 1;
        var price = row.querySelector('.qc-line-price').value;
        if (svcId) {
          var item = { service_id: parseInt(svcId), quantity: qty };
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
        service_id: services[0].service_id,
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
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
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

  var STORAGE_COLOR_MODE = 'fieldlgx_calendar_color_mode';
  var colorMode = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_COLOR_MODE)) || 'status';

  // Global reference for eventsSet callback integration (no setOption chaining needed)
  window._applyColorMode = function() {
    calendar.getEvents().forEach(function(event) {
      var props = event.extendedProps || {};
      if (props.type === 'meeting') return;
      var override = props.jobColorOverride;
      var color;
      if (override) {
        color = override;
      } else if (colorMode === 'assignee') {
        color = props.assigneeColor || props.crewColor || '#94a3b8';
      } else {
        color = props.statusColor || '#3b82f6';
      }
      event.setProp('backgroundColor', color);
      event.setProp('borderColor', color);
    });
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

  function updateLegend() {
    var statusLegend = document.getElementById('cal-legend-status');
    var crewLegend = document.getElementById('cal-legend-crew');
    if (statusLegend) statusLegend.style.display = colorMode === 'status' ? 'flex' : 'none';
    if (crewLegend) crewLegend.style.display = colorMode === 'assignee' ? 'flex' : 'none';
  }
  updateLegend();

});

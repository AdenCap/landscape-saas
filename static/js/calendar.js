/* ==========================================================================
   Field Ops Calendar — Premium JS
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

  var STORAGE_VIEW = 'fieldops_calendar_view';
  var STORAGE_DATE = 'fieldops_calendar_date';

  var savedView = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_VIEW)) || 'dayGridMonth';
  var savedDate = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_DATE) : null;
  var initialDate = null;
  if (savedDate && /^\d{4}-\d{2}-\d{2}$/.test(savedDate)) initialDate = savedDate;

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
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,timeGridDay'
    },
    initialView: savedView,
    initialDate: initialDate || undefined,
    views: {
      dayGridMonth: { buttonText: 'Month' },
      timeGridWeek: { buttonText: 'Week' },
      timeGridDay: { buttonText: 'Day' }
    },
    slotMinTime: '06:00:00',
    slotMaxTime: '20:00:00',
    slotDuration: '00:30:00',
    allDaySlot: true,
    nowIndicator: true,
    eventDisplay: 'block',
    editable: isOwner,
    eventDurationEditable: isOwner,
    longPressDelay: 300,
    height: 'auto',

    // ── Event source ──
    events: function(info, successCallback, failureCallback) {
      var params = [];
      var svc = document.getElementById('filter-services');
      var crew = document.getElementById('filter-crews');
      var searchEl = document.getElementById('calendar-search');
      if (svc && svc.value) params.push('services=' + encodeURIComponent(svc.value));
      if (crew && crew.value) params.push('crews=' + encodeURIComponent(crew.value));
      if (searchEl && searchEl.value.trim()) params.push('search=' + encodeURIComponent(searchEl.value.trim()));
      var qs = params.length ? '?' + params.join('&') : '';
      fetch('/jobs/calendar/events/' + qs)
        .then(function(r) { return r.json(); })
        .then(successCallback)
        .catch(failureCallback);
    },

    // ── Persist view/date ──
    datesSet: function(info) {
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

    // ── Premium event card rendering ──
    eventContent: function(arg) {
      var container = document.createElement('div');
      container.className = 'cal-event-card';

      var props = arg.event.extendedProps || {};
      var isCompleted = props.status === 'completed';
      var isMeeting = props.type === 'meeting';

      if (isCompleted) container.classList.add('cal-event--completed');
      if (isMeeting) container.classList.add('cal-event--meeting');

      // Time badge (month view only, timed events)
      if (arg.event.start && !arg.event.allDay && arg.view.type === 'dayGridMonth') {
        var timeBadge = document.createElement('span');
        timeBadge.className = 'cal-event-time';
        timeBadge.textContent = formatTimeShort(arg.event.start);
        container.appendChild(timeBadge);
      }

      // Crew color dot
      var dot = document.createElement('span');
      dot.className = 'cal-event-dot';
      dot.style.backgroundColor = props.crewColor || arg.event.borderColor || '#94a3b8';
      container.appendChild(dot);

      // Content wrapper
      var content = document.createElement('div');
      content.className = 'cal-event-content';

      // Customer name
      var name = document.createElement('span');
      name.className = 'cal-event-name';
      name.textContent = props.customer || arg.event.title;
      content.appendChild(name);

      // Service abbreviation pill
      if (!isMeeting && props.serviceAbbr) {
        var svcBadge = document.createElement('span');
        svcBadge.className = 'cal-event-svc';
        svcBadge.textContent = props.serviceAbbr;
        content.appendChild(svcBadge);
      }

      // Address (secondary)
      if (!isMeeting && arg.event.title) {
        var addr = document.createElement('span');
        addr.className = 'cal-event-addr';
        addr.textContent = arg.event.title.replace(/^✓\s*/, '');
        content.appendChild(addr);
      }

      container.appendChild(content);

      // Completed checkmark
      if (isCompleted) {
        var check = document.createElement('span');
        check.className = 'cal-event-check';
        check.textContent = '\u2713';
        container.appendChild(check);
      }

      return { domNodes: [container] };
    },

    // ── Click date → create job ──
    dateClick: function(info) {
      if (!isOwner) return;
      var date = info.date;
      if (!date) return;
      var dateStr = formatDateStr(date);
      var timeStr = pad2(date.getHours()) + ':' + pad2(date.getMinutes());
      window.location.href = '/jobs/create/?date=' + dateStr + '&time=' + timeStr;
    },

    // ── Drag event to reschedule ──
    eventDrop: function(info) {
      var jobId = info.event.extendedProps?.jobId;
      if (!jobId) return;
      var start = info.event.start;
      var dateStr = info.event.allDay ? formatDateStr(start) : formatDateTimeStr(start);
      fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ scheduled_date: dateStr })
      }).then(function(r) {
        if (!r.ok) { info.revert(); return; }
        showToast('Job rescheduled');
      }).catch(function() { info.revert(); });
    },

    // ── Resize event ──
    eventResize: function(info) {
      var jobId = info.event.extendedProps?.jobId;
      if (!jobId) return;
      var start = info.event.start;
      fetch('/jobs/calendar/job/' + jobId + '/reschedule/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ scheduled_date: formatDateTimeStr(start) })
      }).then(function(r) { if (!r.ok) info.revert(); })
        .catch(function() { info.revert(); });
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
      if (p.type === 'meeting') {
        info.el.title = (p.customer ? p.customer + ' — ' : '') + (info.event.title || 'Meeting');
      } else {
        info.el.title = [p.customer, p.services, p.crew, p.status].filter(Boolean).join(' — ');
      }
    },

    // ── Weather badges + rain day push buttons ──
    dayCellDidMount: function(info) {
      if (!info.date || !weatherData) return;
      var key = formatDateStr(info.date);
      var w = weatherData[key];
      if (!w || w.high == null) return;

      // Skip if already rendered
      if (info.el.querySelector('.weather-badge')) return;

      var dayFrame = info.el.querySelector('.fc-daygrid-day-top');
      if (!dayFrame) return;

      dayFrame.style.display = 'flex';
      dayFrame.style.justifyContent = 'space-between';
      dayFrame.style.alignItems = 'center';

      // Weather badge
      var badge = document.createElement('div');
      badge.className = 'weather-badge';
      badge.title = w.label + ' · Precip: ' + w.precip + '"';
      badge.innerHTML = '<i data-lucide="' + w.icon + '"></i><span>' + w.high + '°</span>' +
        (w.precip > 0 ? '<span class="weather-rain"></span>' : '');
      dayFrame.appendChild(badge);

      // Rain day push button (owner only, precip > 0.1")
      if (isOwner && w.precip > 0.1) {
        info.el.classList.add('rain-day-cell');
        var pushBtn = document.createElement('button');
        pushBtn.className = 'rain-push-btn';
        pushBtn.textContent = 'Push →';
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
  });
  calendar.render();

  // Hide skeleton loader once calendar renders
  var skeleton = document.getElementById('calendar-skeleton');
  if (skeleton) skeleton.style.display = 'none';

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

  // Filter toggle
  var filterToggle = document.getElementById('toolbar-filter-toggle');
  var filterRow = document.getElementById('calendar-filters');
  if (filterToggle && filterRow) {
    filterToggle.addEventListener('click', function() {
      filterRow.classList.toggle('open');
      filterToggle.classList.toggle('active');
    });
  }

  var filterApply = document.getElementById('filter-apply');
  if (filterApply) filterApply.addEventListener('click', function() { calendar.refetchEvents(); });

  var filterClear = document.getElementById('filter-clear');
  if (filterClear) filterClear.addEventListener('click', function() {
    var svc = document.getElementById('filter-services');
    var crew = document.getElementById('filter-crews');
    if (svc) svc.value = '';
    if (crew) crew.value = '';
    calendar.refetchEvents();
  });

  // ══════════════════════════════════════════════════════════════
  // Modals (CSS transition based)
  // ══════════════════════════════════════════════════════════════

  function openModal(id) {
    var overlay = document.getElementById(id);
    if (overlay) overlay.classList.add('active');
  }
  function closeModal(id) {
    var overlay = document.getElementById(id);
    if (overlay) overlay.classList.remove('active');
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

          // Employee select
          var empSel = document.getElementById('modal-employee');
          empSel.innerHTML = '<option value="">— Unassigned —</option>';
          (data.employees || []).forEach(function(e) {
            var opt = document.createElement('option');
            opt.value = e.id; opt.textContent = e.name;
            if (job.assigned_to_id === e.id) opt.selected = true;
            empSel.appendChild(opt);
          });

          // Color picker
          var colorVal = (job.color || '').trim();
          var colorPicker = document.getElementById('modal-color-picker');
          var colorInput = document.getElementById('modal-color');
          if (colorVal) {
            colorInput.value = colorVal;
            var hex = colorVal.length === 4 ? '#' + colorVal[1]+colorVal[1]+colorVal[2]+colorVal[2]+colorVal[3]+colorVal[3] : colorVal;
            colorPicker.value = hex;
          } else {
            colorInput.value = '';
            colorInput.placeholder = 'Use crew/employee default';
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
  if (crewSel) crewSel.addEventListener('change', function() { if (this.value && empSel) empSel.value = ''; });
  if (empSel) empSel.addEventListener('change', function() { if (this.value && crewSel) crewSel.value = ''; });

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
    if (colorInput) { colorInput.value = ''; colorInput.placeholder = 'Use crew/employee default'; }
    if (colorPicker) colorPicker.value = '#94a3b8';
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
    var payload = {
      assigned_crew_id: crewSel && crewSel.value ? parseInt(crewSel.value, 10) : null,
      assigned_to_id: empSel && empSel.value ? parseInt(empSel.value, 10) : null,
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
    if (pushDateInput) pushDateInput.value = nextDay(dateStr);

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
              return '<label class="rain-job-item">' +
                '<input type="checkbox" checked data-index="' + i + '" data-job-id="' + (p.jobId || '') + '">' +
                '<span>' + (p.customer || ev.title || 'Job') + (p.services ? ' — ' + p.services : '') + '</span>' +
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
      body: JSON.stringify({ from_date: rainFromDate, to_date: toDate, job_ids: jobIds })
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

});

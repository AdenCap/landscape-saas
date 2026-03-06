# Business Timezone Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a business-level timezone setting so all times display in the owner's local timezone instead of UTC.

**Architecture:** Add a `timezone` CharField to the `Business` model with 6 US timezone choices (default Eastern). A Django middleware reads the logged-in user's business timezone and activates it via `django.utils.timezone.activate()`, which makes all template date filters and view-level `timezone.localtime()` calls use the correct zone automatically. A `data-tz` attribute on `<body>` passes the timezone to JavaScript for client-side formatting.

**Tech Stack:** Django 5.2, Python `zoneinfo`, JavaScript `Intl.DateTimeFormat`

---

### Task 1: Add timezone field to Business model

**Files:**
- Modify: `businesses/models.py`

**Step 1: Add the timezone field and choices to the Business model**

In `businesses/models.py`, add this after the `growing_season_end_month` field (around line 260) and before the payroll section:

```python
# Timezone — all times in the app display in this timezone
US_TIMEZONE_CHOICES = [
    ("America/New_York", "Eastern"),
    ("America/Chicago", "Central"),
    ("America/Denver", "Mountain"),
    ("America/Los_Angeles", "Pacific"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
]
timezone = models.CharField(
    max_length=50,
    choices=US_TIMEZONE_CHOICES,
    default="America/New_York",
    help_text="All times in the app display in this timezone.",
)
```

**Step 2: Verify the model change**

Run: `cd /Users/adencappelletti/landscape-saas && source venv_mac/bin/activate && python manage.py check`
Expected: System check identified no issues.

**Step 3: Commit**

```bash
git add businesses/models.py
git commit -m "feat(timezone): add timezone field to Business model"
```

---

### Task 2: Create and apply the migration

**Files:**
- Create: `businesses/migrations/0016_business_timezone.py` (auto-generated)

**Step 1: Generate the migration**

Run: `cd /Users/adencappelletti/landscape-saas && source venv_mac/bin/activate && python manage.py makemigrations businesses`
Expected: Creates migration file for adding `timezone` field.

**Step 2: Apply locally**

Run: `python manage.py migrate`
Expected: Applying businesses.0016_business_timezone... OK

**Step 3: Commit**

```bash
git add businesses/migrations/
git commit -m "feat(timezone): add migration for Business.timezone field"
```

---

### Task 3: Add timezone to Business settings form

**Files:**
- Modify: `businesses/forms.py`

**Step 1: Add "timezone" to the form's fields list**

In `businesses/forms.py`, in the `BusinessSettingsForm.Meta.fields` list, add `"timezone"` as the FIRST field (so it appears near the top of settings):

```python
fields = [
    "name",
    "logo",
    "timezone",          # <-- add here
    "email_smtp_user",
    ...
]
```

**Step 2: Add a label and help text**

In the `labels` dict in Meta, add:
```python
"timezone": "Business timezone",
```

In the `help_texts` dict in Meta, add:
```python
"timezone": "All dates and times across the app display in this timezone.",
```

**Step 3: Verify form renders**

Run: `python manage.py check`
Expected: No issues.

**Step 4: Commit**

```bash
git add businesses/forms.py
git commit -m "feat(timezone): add timezone dropdown to business settings form"
```

---

### Task 4: Create the timezone middleware

**Files:**
- Create: `businesses/middleware.py`

**Step 1: Write the middleware**

Create `businesses/middleware.py`:

```python
from zoneinfo import ZoneInfo

from django.utils import timezone


class TimezoneMiddleware:
    """Activate the logged-in user's business timezone for every request.

    Once activated, all Django template date filters (|date, |time) and
    timezone.localtime() / timezone.localdate() calls automatically use
    the business's timezone instead of UTC.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = None
        if hasattr(request, "user") and request.user.is_authenticated:
            try:
                tz_name = request.user.business.timezone
            except Exception:
                pass

        if tz_name:
            timezone.activate(ZoneInfo(tz_name))
        else:
            timezone.deactivate()

        response = self.get_response(request)
        return response
```

**Step 2: Commit**

```bash
git add businesses/middleware.py
git commit -m "feat(timezone): add TimezoneMiddleware to activate business timezone"
```

---

### Task 5: Register the middleware in settings

**Files:**
- Modify: `config/settings.py`

**Step 1: Add TimezoneMiddleware to the middleware list**

In `config/settings.py`, add `'businesses.middleware.TimezoneMiddleware'` to the `_middleware` list AFTER `AuthenticationMiddleware` (it needs the user on the request). Insert it right after the `SubscriptionRequiredMiddleware` line:

Find this block (around line 122-131):
```python
_middleware += [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'subscription.middleware.SubscriptionRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

Add after `SubscriptionRequiredMiddleware`:
```python
_middleware += [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'subscription.middleware.SubscriptionRequiredMiddleware',
    'businesses.middleware.TimezoneMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

**Step 2: Verify the app starts**

Run: `python manage.py check`
Expected: No issues.

**Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat(timezone): register TimezoneMiddleware in settings"
```

---

### Task 6: Add data-tz attribute to base template

**Files:**
- Modify: `templates/base.html`

**Step 1: Add data-tz to the body tag**

In `templates/base.html` at line 542, change:
```html
<body>
```
to:
```html
<body data-tz="{% if user.is_authenticated and user.business %}{{ user.business.timezone }}{% else %}America/New_York{% endif %}">
```

This makes the business timezone available to all JavaScript on every page.

**Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat(timezone): add data-tz attribute to base template body tag"
```

---

### Task 7: Update calendar.js time formatting

**Files:**
- Modify: `static/js/calendar.js`

**Step 1: Add timezone-aware formatting helper**

At the top of the IIFE in `static/js/calendar.js` (after the existing `pad2` function around line 26), add a timezone variable and update `formatTimeShort`:

Add after `function pad2(n) { ... }`:
```javascript
  var BUSINESS_TZ = document.body.getAttribute('data-tz') || 'America/New_York';
```

Replace the existing `formatTimeShort` function:
```javascript
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
```

**Step 2: Commit**

```bash
git add static/js/calendar.js
git commit -m "feat(timezone): update calendar.js to format times in business timezone"
```

---

### Task 8: Final verification and push

**Step 1: Run Django system check**

Run: `python manage.py check`
Expected: No issues.

**Step 2: Verify middleware works with local server**

Run: `python manage.py runserver` (briefly test that the app loads without errors, then Ctrl+C)

**Step 3: Push all commits to main**

```bash
git push origin main
```

**Step 4: Apply migration to production Supabase**

Use the Supabase MCP to verify the migration applied on deploy, or run it manually if needed. The migration adds a VARCHAR(50) column with default 'America/New_York' — safe and non-breaking.

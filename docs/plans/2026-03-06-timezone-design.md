# Business Timezone Support — Design

## Problem

All times in FieldLgx display in UTC. A crew in Dallas clocking in at 7:00 AM Central sees 12:00 PM on screen. This affects clock in/out, calendar events, job schedules, meeting times, timesheets, and payroll cutoffs.

## Decision

Business-level timezone setting. The owner picks their timezone once in Settings; all times across the app display in that timezone for everyone in the company.

**Why not per-user or auto-detect?**
Lawn care companies operate in a single metro area. Everyone on the crew should see the same times. A single business timezone keeps things consistent for payroll, scheduling, and reporting.

## Data Model

One new field on `Business`:

- `timezone` — CharField, max_length=50, default `"America/New_York"`
- Choices (US-only, matches target market):
  - `America/New_York` — Eastern
  - `America/Chicago` — Central
  - `America/Denver` — Mountain
  - `America/Los_Angeles` — Pacific
  - `America/Anchorage` — Alaska
  - `Pacific/Honolulu` — Hawaii

Migration adds the field with default Eastern. All existing businesses get Eastern automatically.

## Server-Side: Timezone Middleware

New middleware: `businesses/middleware.py` → `TimezoneMiddleware`

For authenticated users with a business:
1. Read `request.user.business.timezone`
2. Call `django.utils.timezone.activate(ZoneInfo(tz))`
3. On response, call `django.utils.timezone.deactivate()`

This means all Django template date filters (`{{ dt|date:"g:i A" }}`) and all `timezone.localdate()` / `timezone.localtime()` calls in views automatically use the correct timezone. Zero changes to existing templates.

**Affected areas (automatic):**
- Clock in/out display
- Calendar/job scheduling
- Meeting times
- Time entries and timesheets
- Payroll date calculations
- Invoice timestamps

## Frontend: JavaScript Time Formatting

Pass the business timezone to JS via a data attribute on `<body>` in the base template:

```html
<body data-tz="{{ request.user.business.timezone }}">
```

Update `calendar.js` time formatting functions to use `Intl.DateTimeFormat` with the `timeZone` option. Other JS files that format times get the same treatment.

## Business Settings Form

Add the timezone dropdown to `BusinessForm` alongside existing fields (name, phone, logo). Simple `<select>` with 6 US timezone options.

## Scope

- 1 model field + migration
- 1 middleware (~15 lines)
- 1 form field update
- Base template data attribute
- JS calendar time formatting update
- No changes to existing templates needed (middleware handles it)

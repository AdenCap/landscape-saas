# Google Review Automation — Implementation Notes

## What was implemented

- Business-level settings:
  - `google_review_requests_enabled`
  - `google_review_link`
  - `google_review_request_delay_hours`
  - `google_review_followup_days`
  - `google_review_max_attempts`
- Customer-level review state tracking:
  - `google_review_status` (`never_asked|asked|reviewed|opted_out`)
  - `google_review_attempts`
  - timestamps for requested/completed/last prompt
- Public action links (signed tokens):
  - mark done (stops reminders)
  - opt out (stops reminders)
- Scheduled sender command:
  - `python manage.py send_google_review_requests`
  - respects paid-invoice requirement + delay/follow-up + max attempts
  - now includes quiet-hours and per-run cap:
    - `--start-hour` (default 9)
    - `--end-hour` (default 20)
    - `--max-per-run` (default 200)

## Recommended schedule (DigitalOcean)

Run hourly during business hours (or daily at one fixed time):

```bash
python manage.py send_google_review_requests --start-hour 9 --end-hour 20 --max-per-run 200
```

## Why this approach

- Works without requiring restricted Google Business Profile API access.
- Uses direct Google review link configured by each business.
- Respects anti-spam principles (attempt caps, follow-up spacing, opt-out).

## Optional next upgrades

1. SMS review requests (Twilio) in addition to email.
2. Timezone-aware sending per customer address/timezone.
3. A/B test templates for higher conversion.
4. Reputation dashboard widgets:
   - requests sent
   - confirmations
   - opt-out rate
   - estimated review conversion.

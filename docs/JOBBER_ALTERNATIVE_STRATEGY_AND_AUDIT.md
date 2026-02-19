# Jobber Alternative: Strategy, Roadmap & Security Audit

**Document purpose:** Prioritized product roadmap, quick wins, differentiators, security/compliance plan, risks, and scalability recommendations for a Django-based home service platform positioned to convert Jobber users.

**Audience:** Product, engineering, and leadership.

---

## Executive Summary

The platform already delivers **draft invoicing, monthly batching, route optimization (Google), time tracking, role-based scheduling, invoice PDFs, aging/outstanding dashboards, QuickBooks OAuth and push, and optional 2FA.** Gaps that matter most for Jobber conversion are: **explicit owner approval before sending invoices**, **time-entry approvals and alerts**, **invoice line-item editing in-app**, **invoice/schedule audit logs**, **job issues + completion photos**, **payment reminders**, **Apple Maps and rate limiting.** This document prioritizes those and adds a security/compliance and scalability plan.

---

## 1. Prioritized Roadmap (Jobber Conversion Focus)

Roadmap is ordered by impact on **conversion** (reducing friction, matching expectations, and beating Jobber on control and clarity).

### Phase 1 — Invoice control & trust (Weeks 1–6)

| Priority | Initiative | Rationale |
|----------|------------|-----------|
| **P1** | **Owner approval before send** | Jobber sends automatically; “never auto-send” is a core differentiator. Add explicit **Approve draft → Send** flow; remove or gate any auto-send behind owner choice. |
| **P2** | **Edit invoice line items in-app** | Today line items are admin-only. Add owner-facing add/edit/delete for draft invoices (formset or inline UI in `billing/views.py` + `billing/templates`). |
| **P3** | **Invoice audit log** | New `InvoiceAuditLog` (or extend `AuditLog`) for: created, approved, sent, paid, void, line-item edits. Store actor, timestamp, and summary. |
| **P4** | **Clarify “auto invoice”** | Ensure `Business.auto_invoice` only means “create drafts automatically,” never “send without approval.” Document and enforce in code paths that send. |

**Code touchpoints:** `billing/services.py` (create/send flows), `billing/views.py` (send_invoice, new approve + line-item edit views), `billing/models.py` (optional audit model), `businesses/models.py` (auto_invoice semantics).

### Phase 2 — Time & payroll control (Weeks 4–10)

| Priority | Initiative | Rationale |
|----------|------------|-----------|
| **P1** | **Time entry approval** | Owner approves/rejects `TimeEntry` before it counts for pay. New status: e.g. `pending_approval` → `approved` / `rejected`; timesheets and payroll only use approved entries. |
| **P2** | **Alerts for abnormal hours** | Notify owner when: missing clock-out, overtime threshold exceeded, or duplicate clock-in. Use existing `Notification` or email. |
| **P3** | **Notification on submit** | When crew submits time (e.g. week closed or daily submit), notify owner so approval is timely. |
| **P4** | **Prevent employee edits** | Crew can create entries and request corrections; only owner can edit/delete. Enforce in views and document in UI. |

**Code touchpoints:** `time_tracking/models.py` (TimeEntry status, optional submitted_at), `time_tracking/views.py` (approve/reject, permission checks), `accounts/models.py` or notifications app (alerts).

### Phase 3 — Job execution & proof (Weeks 6–12)

| Priority | Initiative | Rationale |
|----------|------------|-----------|
| **P1** | **Job issues** | New model: e.g. `JobIssue` (job, reported_by, type, description, photo(s), status, resolution_notes, resolved_at). Crew can report from mobile; owner gets real-time alert and can resolve. |
| **P2** | **Completion photos** | New model: e.g. `JobCompletionPhoto` (job, image, uploaded_by, captured_at). Optional `Business.require_completion_photo`; block “complete” until photo uploaded if required. Store in MEDIA with access control. |
| **P3** | **Location at clock-in / job start / complete** | Optional GPS on `TimeEntry` and on job completion (lat/long). Consent flag on `User` or `Employee`; capture only when consent given. |

**Code touchpoints:** `jobs/models.py`, `jobs/views.py`, `jobs/crew_views.py`, new migrations; `time_tracking/models.py` (lat/long, consent); `businesses/models.py` (require_completion_photo).

### Phase 4 — Payments & reminders (Weeks 8–14)

| Priority | Initiative | Rationale |
|----------|------------|-----------|
| **P1** | **Outstanding invoice dashboard** | You already have overdue buckets and AR; add a dedicated “Outstanding invoices” view with filters (paid / unpaid / overdue), aging table, and export. |
| **P2** | **Configurable payment reminders** | `Business` settings: e.g. reminder_days_after_due (list), reminder_channel (email, sms, both). Celery/cron job to send reminders; owner can turn off. |
| **P3** | **SMS for reminders** | Integrate Twilio (or similar); send reminder SMS when configured. |

**Code touchpoints:** `financials/views.py` or `billing/views.py` (outstanding view), `businesses/models.py` (reminder fields), new management command or Celery task, SMS client.

### Phase 5 — Routing & maps (Weeks 10–16)

| Priority | Initiative | Rationale |
|----------|------------|-----------|
| **P1** | **Apple Maps deep links (iOS)** | For “Navigate” on mobile, build `maps.apple.com` URL from job address; open in Apple Maps when on iOS. Keep Google for web/Android. |
| **P2** | **Route optimization transparency** | Document that optimization uses Google Directions API with waypoints; consider caching and cost controls. |
| **P3** | **Future: dynamic routing** | Backlog: real-time traffic, multi-day optimization, or third-party routing engine. |

**Code touchpoints:** `jobs/views.py`, `jobs/templates/jobs/daily_route.html` (or crew mobile template): detect iOS and offer Apple Maps link.

### Phase 6 — QuickBooks & migration (Ongoing)

| Priority | Initiative | Rationale |
|----------|------------|-----------|
| **P1** | **Owner-controlled sync** | Already manual push; add UI: “Sync to QuickBooks” with clear success/error. No background auto-sync unless owner opts in. |
| **P2** | **Stored error log** | New model or log table for QB errors (invoice_id, action, error_message, created_at). Show last N errors in Settings/QuickBooks page. |
| **P3** | **Jobber migration** | CSV/Excel import for customers, properties, and jobs; optional invoice history. Dedicated “Import from Jobber” flow with mapping and validation. |

**Code touchpoints:** `quickbooks/views.py`, `quickbooks/models.py` (error log), new `billing` or `customers` import views and templates.

---

## 2. Immediate Quick Wins

- **Owner approval before send (invoice)**  
  - Add “Approve & send” step; keep drafts invisible to customer until approved.  
  - **Effort:** Small (1–2 weeks). **Impact:** High (core differentiator).

- **Edit invoice line items in-app**  
  - Owner can add/edit/delete lines on draft invoices from billing UI.  
  - **Effort:** Small (1–2 weeks). **Impact:** High (removes need for admin).

- **Time entry approval**  
  - Add pending/approved/rejected; only approved entries in timesheets.  
  - **Effort:** Medium (2–3 weeks). **Impact:** High (payroll control).

- **Schedule change audit**  
  - Log who changed what and when (schedule and job assignment).  
  - **Effort:** Small (1 week). **Impact:** Medium (trust and compliance).

- **Rate limiting (auth and API)**  
  - Throttle login and sensitive endpoints (e.g. password reset, QB callback).  
  - **Effort:** Small (django-ratelimit or middleware). **Impact:** Security baseline.

- **QuickBooks error log in UI**  
  - Store and display last sync errors.  
  - **Effort:** Small. **Impact:** Medium (transparency).

---

## 3. High-Impact Differentiators vs Jobber

| Differentiator | Your position | Implementation note |
|----------------|---------------|---------------------|
| **Invoice control** | Never auto-send; owner approves every send; full line-item edit; audit trail. | Phases 1–2; audit log. |
| **Time & payroll** | Owner approves time; alerts for anomalies; no employee edit of approved data. | Phase 2. |
| **Scheduling** | Only owners edit schedules; backend enforcement; audit trail. | Already enforced; add audit (Phase 1/2). |
| **Routing** | Faster UX; Apple Maps for iOS; same or better optimization than Jobber. | Phase 5. |
| **Job issues & proof** | Crew-reported issues with photos; mandatory completion photos (configurable). | Phase 3. |
| **Reporting** | Revenue, aging, and payroll already; add profit and crew utilization. | Extend financials + timesheets. |
| **Pricing** | Service templates, property-based pricing, seasonal adjustments. | Leverage existing pricing app; expose in UI. |
| **Migration** | “Import from Jobber” to reduce switch friction. | Phase 6. |

---

## 4. Long-Term Platform Vision

- **Owner-first operations**  
  Every money and schedule action (invoices, time, routing, QB sync) is owner-approved and visible. Automation creates drafts and suggestions; owners confirm.

- **Single source of truth**  
  Jobs, invoices, time, and QB stay in sync with clear rules: drafts in-app, sync to QB only when owner chooses, and transparent errors.

- **Mobile that beats Jobber**  
  Fast, focused crew experience: clock in/out, today’s route, Apple Maps navigate, report issue, upload completion photo. Roadmap: offline-first and better performance.

- **Trust and compliance**  
  Audit logs for invoices and schedules; consent-based location; clear data retention; path to SOC 2.

- **Ecosystem**  
  QuickBooks today; later: payroll APIs, more accounting packages, and optional marketplaces.

---

## 5. Security and Compliance Plan

### 5.1 Current state (from audit)

- **Auth:** Django password validators; optional 2FA (django-otp); session HttpOnly, SameSite, 12h expiry, save every request.  
- **Data:** SMTP encrypted (Fernet); QuickBooks tokens in DB **unencrypted**.  
- **API:** CSRF and template escaping; **no** app-level rate limiting.  
- **Multi-tenancy:** Data scoped by `get_business(request)`; platform admin “view as” documented.

### 5.2 Recommendations

**Authentication & authorization**

- Keep strong password validators; consider `MinimumLengthValidator` ≥ 10 for owners.  
- Make 2FA discoverable (e.g. “Security” in Settings) and document MFA roadmap (SMS/backup codes).  
- Ensure session invalidation on password change and optional “Log out all devices.”

**Data protection**

- **Encrypt QuickBooks tokens at rest** (e.g. Fernet with a key derived from SECRET_KEY or a dedicated key in env).  
- Keep secrets in env; never commit `.env`.  
- Use HTTPS only in production; set `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and HSTS in production settings.

**API and backend security**

- **Rate limiting:** Login, password reset, 2FA verify, QuickBooks OAuth callback (e.g. 5–10 req/min per IP or per user).  
- Sanitize/validate any user input used in QuickBooks query strings (customer name, etc.).  
- Continue using ORM (no raw SQL with user input); keep template auto-escape; avoid `mark_safe` on user content.

**Infrastructure**

- **Logging:** Structured logs for auth events (login fail/success, 2FA), invoice send, QB sync, and permission-denied.  
- **Monitoring:** Health check endpoint; alert on 5xx and repeated auth failures.  
- **Backup:** Automated DB and media backups; test restore; retain per retention policy.

**Compliance and privacy**

- **Privacy:** Document what data you collect (including location if added); consent for location; allow export and delete (GDPR-style).  
- **Workforce tracking:** If you add GPS/location, document purpose, consent, and retention; comply with local labor/privacy laws.  
- **Data retention:** Define retention for logs, invoices, time entries, and QB sync logs; implement purge or archive.  
- **SOC 2 roadmap:** Document controls (access, change management, encryption, backup); plan for access reviews and vendor questionnaires.

### 5.3 Production security checklist (concise)

- [ ] `DEBUG=False`, strong `SECRET_KEY`, `ALLOWED_HOSTS` set.  
- [ ] HTTPS; `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, HSTS.  
- [ ] Rate limiting on login, reset, 2FA, QB callback.  
- [ ] Encrypt QB tokens at rest.  
- [ ] No auto-send of invoices; owner approval only.  
- [ ] Audit logging for invoice and schedule changes.  
- [ ] Backups and restore tested; retention policy documented.

---

## 6. Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| **Jobber copies “approval” workflow** | Ship first and brand “Owner-controlled billing”; emphasize audit and flexibility. |
| **QB token breach** | Encrypt at rest; short-lived refresh; monitor for anomalous API use. |
| **Crew disputes over time** | Approval workflow + audit log; optional GPS at clock-in for evidence. |
| **Regulatory (labor/privacy)** | Consent for location; retention policy; legal review for target states/countries. |
| **Scale (DB, media, PDF)** | Move to PostgreSQL; media on S3/object store; queue PDF generation (Celery). |
| **Third-party dependency (Google Maps, QB)** | Document quotas and fallbacks; consider Apple Maps for iOS to diversify. |

---

## 7. Scalability and Architecture Recommendations

- **Database:** Use **PostgreSQL** in production (already in requirements). Connection pooling (e.g. PgBouncer) when needed.  
- **Media:** Store uploads (completion photos, issue photos) on **S3 or compatible object storage**; use `django-storages`; keep MEDIA_URL configurable.  
- **Async tasks:** Use **Celery** (or similar) for: payment reminders, bulk invoice creation, PDF generation, and optional QB sync. Redis as broker.  
- **Caching:** Cache dashboard aggregates and aging reports (e.g. Redis); invalidate on invoice/time changes.  
- **Rate limiting:** Middleware or decorator with Redis backend for global and per-user limits.  
- **Front-end:** Keep server-rendered templates; optimize with fragment caching and minimal JS for critical paths (e.g. crew mobile).  
- **Monitoring:** APM and error tracking (e.g. Sentry); log aggregation; health checks for DB and critical endpoints.

---

## Appendix: Audit Summary vs Requirements

| # | Requirement | Status | Gap / action |
|---|-------------|--------|--------------|
| 1 | Invoice control & owner approval | Partial | Add approve step; no auto-send; in-app line edit; audit log. |
| 2 | Time tracking with approvals & notifications | Partial | Add approval; alerts; submit notification; no employee edit. |
| 3 | Advanced routing & Apple Maps | Partial | Add Apple Maps links for iOS; keep Google. |
| 4 | QuickBooks | Done + partial | Encrypt tokens; store errors; keep owner-controlled sync. |
| 5 | Strict role-based scheduling | Done | Add schedule/job change audit. |
| 6 | Job issue & communication | Missing | Add JobIssue model and crew/owner flows. |
| 7 | Mandatory completion photos | Missing | Add model + optional requirement flag. |
| 8 | Location tracking | Missing | Add consent + optional lat/long on time and job. |
| 9 | Modern invoice design | Done | Already PDF + branding. |
| 10 | Outstanding invoice dashboard | Done | Add dedicated view + filters if needed. |
| 11 | Automated payment reminders | Partial | Config + email/SMS reminders. |
| 12 | Migration tools | Missing | Jobber import (customers, jobs, invoices). |
| 13 | Reporting & BI | Partial | Add profit view; crew utilization; CLV later. |
| 14 | Automation engine | Backlog | Triggers/rules after core flows stable. |
| 15 | Pricing flexibility | Partial | Expose templates and property-based pricing. |
| 16 | Mobile experience | Partial | Optimize; Apple Maps; offline roadmap. |
| Security | Auth, MFA, sessions | Done | Harden production; rate limit. |
| Security | Encryption, tokens | Partial | Encrypt QB tokens; document secrets. |
| Security | Rate limit, injection, XSS | Partial | Add rate limiting; sanitize QB inputs. |
| Security | Monitoring, backup | Partial | Document and implement checklist. |
| Security | Compliance, SOC 2 | Roadmap | Retention; consent; SOC 2 plan. |

---

*This document should be updated as features ship and as new security or compliance requirements emerge.*

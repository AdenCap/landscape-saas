# FIELDLGX Native Full Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the iPhone app into a production-ready native FIELDLGX client that mirrors the mobile web workflows and syncs bidirectionally with the existing database.

**Architecture:** The Django app remains the source of truth. The native app talks to dedicated `/api/mobile/v1/` endpoints for online reads/writes, queues field-safe offline mutations in SwiftData, and syncs those mutations back through API handlers that update the same Django models the web app uses.

**Tech Stack:** Django 6 mobile API, SQLite locally/Supabase-backed Postgres in production, SwiftUI, SwiftData offline queue, Xcode simulator verification.

---

## Phase 1: Native Command Center

**Files:**
- Modify: `mobile_api/tests.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/API/APIClient.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/API/APIModels.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/App/AppShell.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/CommandScreen.swift`

- [x] Add a Django test proving `/api/mobile/v1/command/` returns owner dashboard metrics from jobs, clients, invoices, estimates, and needs-scheduled work.
- [x] Implement the command endpoint using existing Django models only, scoped by `session.business`.
- [x] Add Swift response models and `APIClient.command()`.
- [x] Replace the owner/manager Command placeholder with `CommandScreen`.
- [x] Build and run the iOS simulator.
- [x] Sign in as `testowner / testpass123` and verify the Command screen is populated from the local web database.

## Phase 2: Native Work Pipeline

**Files:**
- Modify: `mobile_api/tests.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/WorkScreen.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/API/APIClient.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/API/APIModels.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/App/AppShell.swift`

- [x] Add mobile API endpoints for upcoming jobs, needs-scheduled jobs, finished jobs, and needs-billing jobs.
- [x] Add filters for service type/status that match the web jobs page.
- [x] Build the native Work tab with the same premium card pattern.
- [x] Verify selecting a job opens native `JobDetailScreen`.

## Phase 3: Native Clients

**Files:**
- Modify: `mobile_api/tests.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/ClientsScreen.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/ClientDetailScreen.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/API/APIClient.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/API/APIModels.swift`

- [x] Add list/detail/create/update endpoints for clients and properties.
- [x] Include client address, map destination, billing preferences, card-on-file status, permanent notes, internal notes, jobs, invoices, and estimates.
- [ ] Add native inline client creation sheet reusable from job, estimate, invoice, mowing, and fertilization flows.
- [ ] Verify new clients created in iOS appear in the web app and vice versa.

Progress note: the shared native client creation sheet is now reusable and wired into the native job, invoice, and estimate creation flows. It still needs to be wired into mowing and fertilization flows before this phase is complete.

## Phase 4: Native Calendar And Job Editing

**Files:**
- Modify: `mobile_api/tests.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/CalendarScreen.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/App/JobDetailScreen.swift`

- [x] Add mobile calendar range endpoint for day/week/month.
- [ ] Add create/update endpoints for jobs, assignments, recurrence scope changes, dates, times, notes, and service items.
- [x] Build native calendar list/timeline views for iPhone.
- [ ] Verify mobile edits update the web calendar and web edits update the native calendar after refresh.

Progress note: standard native job create plus owner/manager job detail edits for date, time, notes, and crew assignment are wired through the shared mobile API and build successfully. Recurrence scope changes, service item editing, and full web/native clickthrough verification remain open.

## Phase 5: Native Billing

**Files:**
- Modify: `mobile_api/tests.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/MoneyScreen.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/EstimateDetailScreen.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/InvoiceDetailScreen.swift`

- [ ] Add mobile endpoints for estimates, invoices, line items, discounts, reminders, follow-ups, monthly invoice batches, and card-on-file flags.
- [x] Build native estimate/invoice lists and detail screens.
- [ ] Add create/edit flows for estimates and invoices.
- [ ] Verify estimates/invoices created on native are visible on web and web-created records are visible on native.

Progress note: native invoice and estimate lists now open detail screens backed by mobile API detail endpoints with totals, line items, invoice card-payment flag, and estimate deposit data. Native create invoice/create estimate flows now save through mobile API, invoice send/reminder plus estimate mark-sent/follow-up actions are wired, monthly invoice queue/batch-send is available on Money, and invoice line items can be marked paid/unpaid from native. Discounts, broader edit mutations, and full web/native verification remain open.

## Phase 6: Offline Sync

**Files:**
- Modify: `mobile_api/tests.py`
- Modify: `mobile_api/views.py`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/Sync/SyncQueue.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/Sync/SyncModels.swift`

- [ ] Implement sync push handlers for job actions, notes, issues, client creates, job creates, estimate drafts, invoice updates, and time entries.
- [ ] Implement sync pull deltas for jobs, clients, estimates, invoices, notes, and service items.
- [ ] Add conflict records when stale mobile edits touch records updated on the server.
- [ ] Verify offline queued actions replay cleanly when the simulator regains connectivity.

Progress note: sync push now accepts queued client creates and job creates, the native queue can replay those plus existing job actions, and Today has a visible Sync now card. Sync pull now returns a current mobile snapshot for clients/jobs/invoices/estimates. Conflict records, time entry sync, estimate/invoice sync mutations, and full offline simulator verification remain open.

Native polish note: the app now restores saved sessions from Keychain refresh tokens, uses a centralized configurable API base URL instead of hardcoded screen-level localhost URLs, has real crew Route/Time/More screens instead of placeholders, and supports direct camera capture for job site and completion photos.

## Phase 7: Full Workflow Verification

- [ ] Create a test client on web and confirm it appears in native.
- [ ] Create a test client on native and confirm it appears in web.
- [ ] Create/edit/schedule a job on native and verify web calendar/jobs page.
- [ ] Edit/complete a job on native and verify billing queue.
- [ ] Create an estimate on native and verify web estimate detail/PDF flow.
- [ ] Create an invoice on native and verify web invoice detail/monthly batch flow.
- [ ] Add notes/photos/issues on native and verify web detail pages.
- [ ] Add notes/photos/issues on web and verify native detail pages.

# FIELDLGX Native iOS App Design

## Goal

Build a true native iPhone app for FIELDLGX that supports owners, managers, and crew members across the full operating workflow: dashboard command, scheduling, jobs, clients, estimates, invoices, monthly billing, promotions, employees, time tracking, location timeline events, photos, notes, and offline work.

The native app will not be a WebView wrapper. It will be a SwiftUI app that communicates with the existing Django backend through a new mobile API and keeps a local offline-first data store on the device.

## Scope

Version 1 is iPhone-only. iPad support is intentionally deferred, but the navigation and data architecture should not block a future iPad layout.

Version 1 includes both office and field roles:

- Owners
- Managers
- Crew / employees

The app must support email/password login, Sign in with Apple, and Sign in with Google from day one.

The app must allow offline creation and editing across the platform. Actions that require the internet, such as charging cards, sending emails/SMS messages, uploading photos to cloud storage, refreshing Stripe state, or pushing notifications, are queued and clearly marked until the phone reconnects.

## Existing Context

The repository currently contains a Capacitor iOS wrapper under `native/ios/App`. That project loads the web app and should remain untouched during the native rebuild.

The new native SwiftUI app should live beside it under a new path, for example:

`native/ios/FieldLGXNative/`

The Django app remains the source of truth. Existing browser workflows, production data, migrations, and web templates continue to operate while the native API is added.

## Product Modes

### Owner / Manager Mode

Owners and managers need a complete command center on the phone.

Primary tabs:

- Command
- Calendar
- Work
- Clients
- Money
- More

Core screens:

- Field Command dashboard
- Calendar day/week/month
- Job pipeline
- Job detail
- Client list
- Client profile
- Property profile
- Estimate list/detail/create/edit
- Invoice list/detail/create/edit
- Monthly invoice queue
- Promotions
- Fertilization
- Agreements
- Employee management
- Time/location timelines
- Financial snapshots
- Business/settings
- Sync center and conflict resolution

### Crew / Employee Mode

Crew users need a field-first experience optimized for one-handed use and weak signal.

Primary tabs:

- Today
- Route
- Time
- Messages
- More

Core screens:

- Clock in/out
- Today route summary
- Next job
- Job detail
- Client/property context
- Crew-visible property notes
- Job notes
- Service items
- Photos
- Issues
- Costs where permitted
- Skip/complete job
- Directions handoff
- Offline sync state

Crew users do not get full billing or sensitive management controls unless their role explicitly permits it.

## Native App Architecture

The iOS app should use SwiftUI with small, focused feature modules.

Recommended structure:

- `FieldLGXNativeApp`: app entry point and dependency setup
- `AppShell`: role-aware tab shell
- `Auth`: email/password, Apple, Google, token refresh, logout
- `API`: typed mobile API client
- `Sync`: pull, push, mutation queue, conflict detection, retry
- `Persistence`: local offline database
- `Dashboard`: owner/manager command center
- `Calendar`: calendar views and rescheduling
- `Jobs`: job list, detail, edits, status changes, notes, photos, issues
- `Clients`: clients, properties, notes, billing settings
- `Billing`: estimates, invoices, promotions, monthly invoice queue
- `TimeTracking`: clock events, breaks, location timeline
- `Media`: camera, photo picker, upload queue
- `Location`: permission, while-clocked-in tracking, timeline events
- `Settings`: profile, business settings, permissions, app diagnostics

State should be owned narrowly. Use SwiftUI state for local UI state, observable app services for shared dependencies, and explicit feature-level models for complex flows. Avoid giant views and global state where a feature-specific dependency is clearer.

## Mobile API Architecture

The native app needs a dedicated JSON API under:

`/api/mobile/v1/`

Core API groups:

- `auth`: login, Apple login, Google login, refresh, logout, revoke device
- `bootstrap`: current user, business, roles, permissions, modules, sync cursors
- `dashboard`: owner command metrics and crew today summary
- `jobs`: list, detail, create, edit, status, assign, notes, service items, costs, issues
- `calendar`: date ranges, drag/reschedule, recurring future updates
- `clients`: clients, properties, notes, billing settings, card-on-file status
- `billing`: estimates, invoices, line items, promotions, monthly queue
- `media`: upload sessions, upload retry, photo/logo URLs
- `time`: clock in/out, breaks, time entries, approvals where permitted
- `location`: clock/job timeline events and periodic pings
- `sync`: pull changes, push queued mutations, list conflicts, resolve conflicts

The API must be role-aware and business-scoped on every endpoint. The app should never rely on client-side filtering for security.

## Authentication

V1 authentication includes:

- Email/password login
- Sign in with Apple
- Sign in with Google
- Refresh-token renewal
- Logout
- Device/session revocation
- Role-aware bootstrap after login

Tokens must be stored in Keychain. Refresh tokens should be revocable per device. The backend should track mobile sessions so owners can revoke lost devices.

## Offline-First Data Model

The iPhone keeps a local data store for operational records. The recommended implementation is SwiftData if the deployment target supports it cleanly, otherwise Core Data. The implementation plan should select the final persistence technology after checking the project’s minimum iOS target.

Records stored offline include:

- Current user and business context
- Permissions and enabled modules
- Clients
- Properties
- Property notes
- Jobs
- Job notes
- Job service items
- Job photos and pending photo uploads
- Job issues
- Crews
- Employees
- Calendar windows
- Estimates and line items
- Invoices and line items
- Promotions
- Monthly invoice queue records
- Time entries
- Location timeline events
- Sync mutations
- Sync conflicts

Every synced record should include:

- Local UUID
- Server ID when known
- Business ID
- Last server update timestamp or revision
- Local dirty state
- Deleted/tombstone state when supported

Every offline action becomes a queued mutation. The mutation stores:

- Entity type
- Entity local ID
- Server ID if known
- Operation type
- Payload
- Base server revision
- Created timestamp
- Retry count
- Failure reason
- Required confirmation state for sensitive actions

## Sync Rules

The server remains the source of truth. The device can work offline, but all local changes must eventually reconcile with the backend.

Automatic sync:

- Pull latest records after login
- Pull deltas by sync cursor
- Push local mutations in order
- Retry transient failures with backoff
- Preserve local pending changes while refreshing server data

Queued online-required actions:

- Send invoice
- Send invoice reminder
- Send estimate
- Send estimate follow-up
- Charge card on file
- Send SMS/customer message
- Upload photo/media
- Refresh Stripe payment state

Those actions show a clear queued state until the device reconnects. The app must not pretend an external action happened before the backend confirms it.

Conflict handling:

- If only one side changed a record, sync automatically.
- If the phone and server both changed the same record from the same base revision, create a conflict.
- Owners/managers can resolve by keeping server, keeping phone, or merging these supported fields individually: title/name, notes, scheduled date/time, assigned crew/employee, status, address/contact fields, line item description, quantity, unit price, and visibility. Fields outside the supported merge list use keep-server or keep-phone.
- Crew users see a simplified “needs manager review” state for sensitive records such as invoices, estimates, pricing, customer billing settings, and payment settings.
- Conflict resolution is audited.

## Location Tracking

V1 uses the lighter location model, not continuous live map playback.

Tracked events:

- Clock-in location
- Clock-out location
- Job arrival location
- Job departure/completion location
- Periodic pings while clocked in

The app only tracks location while an employee is clocked in. It displays a clear active tracking indicator while location tracking is active.

Owner/manager visibility is a timeline:

- Time entry events
- Job arrival/departure/completion events
- Periodic “last seen while clocked in” pings
- Optional map opening for individual events

V1 does not include full route playback.

## Media and Photos

The app must support:

- Camera capture
- Photo library selection
- Job photos
- Completion photos
- Issue photos
- Estimate photos
- Receipt photos if the financial module uses them
- Business logo/profile media where permitted

Photos are saved locally first, then uploaded through the sync queue. Failed uploads are retryable. The user should see whether a photo is local-only, uploading, uploaded, or failed.

The backend media API must upload to the production storage provider already configured for the Django app and return either a permanent public URL for public-safe assets or a time-limited signed URL for private job/client media.

## Maps and Navigation

The app should support Apple Maps handoff by default and Google Maps where available.

Navigation actions:

- Open route destination
- Open property address
- Open single timeline event location

The app does not need custom turn-by-turn navigation in V1.

## Billing and Payments

The app can create and edit estimates, invoices, line items, discounts, promotions, and monthly invoice batches offline.

External payment actions require internet and confirmation:

- Charge card on file
- Start Stripe checkout
- Send invoice with payment link
- Send estimate deposit link

When offline, these actions become queued actions only after the user confirms what will happen when the phone reconnects. The queued action screen must show the customer, amount, and action clearly.

The app should never charge a card silently because an offline queue replayed without a visible confirmation history.

## Security

Security requirements:

- Tokens stored in Keychain
- API uses HTTPS only in production
- Mobile sessions are revocable
- All API data is scoped by business and role
- Sensitive local data is protected by iOS data protection
- Consider encrypted local storage for higher-risk cached records
- Payment card details are never stored directly in the app
- Audit sensitive actions
- Respect existing role permissions

Sensitive actions requiring explicit confirmation:

- Delete records
- Charge card
- Send customer-facing message
- Send invoice/reminder
- Send estimate/follow-up
- Upload/share files externally
- Enable background location permissions

## App Store Readiness

Required App Store items:

- Bundle ID
- App icon and launch screen using FIELDLGX branding
- Display name: FIELDLGX
- Privacy policy URL
- Terms URL
- Support URL
- Account deletion/support path
- App Store screenshots
- App description and keywords
- TestFlight groups for owner, manager, and crew testing

Required iOS permission descriptions:

- Location when in use
- Background location
- Camera
- Photo library
- Push notifications when added

Privacy labels must reflect actual data collection:

- Contact info
- User content
- Photos/videos
- Location
- Identifiers
- Diagnostics
- Payment-related metadata, if collected

Background location justification:

FIELDLGX uses location only while an employee is clocked in to record clock/job timeline events for field-service accountability and routing context.

## Testing Strategy

Backend tests:

- Mobile auth
- API permission scoping
- Sync pull/push
- Conflict creation and resolution
- Offline queued action replay
- Media upload
- Location timeline writes
- Billing and payment queue safety

iOS tests:

- API client tests with mocked responses
- Sync queue unit tests
- Offline creation/edit tests
- Conflict resolution tests
- Auth token refresh tests
- Location permission state tests
- Photo queue tests
- Role-based navigation tests

Manual QA:

- Owner login
- Manager login
- Crew login
- Offline job completion
- Offline estimate creation
- Offline invoice edit
- Offline client creation
- Photo capture offline then sync
- Clock in/out with location
- Conflict resolution
- App kill/relaunch with pending queue
- Weak signal simulation
- Permission denial paths
- TestFlight install/upgrade

## Rollout Plan

Phase 1: Backend mobile API foundation and mobile auth.

Phase 2: SwiftUI project scaffold, app shell, login, bootstrap, local persistence, and sync queue.

Phase 3: Crew field workflows: Today, route, job detail, notes, photos, issues, completion, time, and location timeline.

Phase 4: Owner/manager workflows: Command, calendar, jobs, clients, money, employees, and settings.

Phase 5: Full offline editing, queued external actions, and conflict resolution.

Phase 6: App Store polish: icons, launch, privacy copy, permissions, screenshots, TestFlight, release checklist.

## Non-Goals for V1

- iPad-specific layouts
- Continuous live map playback
- Custom turn-by-turn navigation
- Native Android app
- Full replacement of the web app
- Storing raw credit card data on device
- Silent offline replay of payment charges without visible confirmation

## Implementation Defaults

The implementation plan should use these defaults unless a hard technical blocker is found during setup:

- Minimum iOS version: iOS 17.
- Local persistence: SwiftData for typed records, backed by file protection; fall back to Core Data only if SwiftData blocks the sync queue design.
- Token model: short-lived access token plus rotating refresh token stored in Keychain. Refresh tokens expire after 30 days of inactivity and can be revoked per device.
- Mobile API style: Django JSON views under `/api/mobile/v1/` using existing models and permission helpers first. Introduce Django REST Framework only if serializer/viewset structure clearly reduces complexity during implementation.
- Conflict payload schema: `{entity_type, server_id, local_id, base_revision, server_revision, local_payload, server_payload, mergeable_fields, created_at}`.
- Media uploads: compress images on device, create a media upload record, upload multipart data through Django, store in the configured production storage backend, and retry failed uploads from the sync queue.
- Push notifications: implement backend/device-token registration in the foundation, but make push notification delivery a later V1 milestone after offline sync and core workflows are stable.

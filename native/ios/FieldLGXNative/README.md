# FIELDLGX Native iOS

This is the true native SwiftUI iPhone app for FIELDLGX.

The existing Capacitor wrapper lives at `native/ios/App` and remains untouched until this app fully replaces it.

Minimum target: iOS 17.

Primary capabilities:
- Offline-first business data
- Owner, manager, and crew roles
- Location events while clocked in
- Camera and photo library
- Mobile API under `/api/mobile/v1/`

## Project Status

This project is now the active native iPhone build. It includes:

- Premium FIELDLGX sign-in with email/username and Sign in with Apple.
- Keychain refresh-token storage with automatic session restore on launch.
- Owner/manager Command, Calendar, Work, Clients, Money, and More tabs.
- Crew Today, Route, Time, and More tabs.
- Native job detail actions: start, complete, skip, edit schedule/crew/notes, add field notes, report issues, upload completion proof, upload site photos, and direct camera capture.
- Native client list/detail/create flows with inline client creation from job, invoice, and estimate creation.
- Native invoice/estimate lists, detail screens, create flows, invoice send/reminder actions, estimate sent/follow-up actions, monthly batch invoice review/send, and invoice line-item paid/unpaid toggles.
- SwiftData offline mutation queue for key field actions plus client, job, invoice, and estimate creation.
- Mobile API integration under `/api/mobile/v1/`.

The checked-in `FieldLGXNative.xcodeproj` is a minimal hand-authored Xcode project so the native app can build without touching the existing Capacitor project.

## Release Configuration

The native app reads `FIELDLGX_API_BASE_URL` from `FieldLGXNative/Info.plist`.
The Xcode project sets it per configuration:

```text
Debug: http://127.0.0.1:8004
Release: https://fieldlgx.com
```

Before TestFlight or App Store submission, confirm the Release value matches the production HTTPS API host and that the backend exposes `/api/mobile/v1/`.

App Store setup still requires:

- Confirm the Apple Developer account owns bundle identifier `com.fieldlgx.native`.
- Confirm Apple Developer Team `7KFZG78236` is the correct production team.
- Confirm the Release API base URL is the production HTTPS host and exposes `/api/mobile/v1/`.
- Configure Apple Sign-In server verification with the Apple service/client ID.
- Prepare App Store Connect metadata, support URL, privacy nutrition labels, location/photos disclosure copy, and a demo login for App Review.
- Google Sign-In can be enabled after the Google iOS client ID and native SDK are added to the Xcode project.

Use a DerivedData path outside the repo for local builds, for example:

```text
xcodebuild -project native/ios/FieldLGXNative/FieldLGXNative.xcodeproj -scheme FieldLGXNative -derivedDataPath /private/tmp/fieldlgx-native-derived build
```

## Verification

Recent local verification:

- `./run test mobile_api` passes.
- Xcode simulator build/run passes for scheme `FieldLGXNative`.

Run both before any production push.

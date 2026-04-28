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

This scaffold is intentionally lightweight. It includes an iPhone-only SwiftUI app shell, email/password mobile API login, Keychain refresh-token storage, role-aware tabs, SwiftData offline mutation queue scaffolding, permission copy, and empty asset catalog metadata.

The checked-in `FieldLGXNative.xcodeproj` is a minimal hand-authored Xcode project so the foundation can build without touching the existing Capacitor project.

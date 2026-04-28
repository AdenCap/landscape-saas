# FIELDLGX Native iOS Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-grade foundation for the FIELDLGX native iPhone app: mobile API auth/bootstrap/sync contracts, mobile session storage, and a true SwiftUI app shell ready for offline-first workflows.

**Architecture:** Add a dedicated Django `mobile_api` app under `/api/mobile/v1/` while leaving existing browser views untouched. Add a new SwiftUI iPhone project under `native/ios/FieldLGXNative/` beside the existing Capacitor wrapper. The iOS foundation includes app shell, auth screens, Keychain-backed token storage, API client, offline queue models, and permission copy.

**Tech Stack:** Django JSON views, Django test client, existing FIELDLGX models/permissions, SwiftUI, Swift Concurrency, Keychain Services, SwiftData scaffolding, Xcode iOS 17+ target.

---

## Scope Check

The approved design covers the entire FIELDLGX native platform. That is too large for one implementation pass. This plan intentionally implements the **foundation slice** only:

- Mobile API app and URL mount
- Mobile device session model
- Email/password auth
- Apple/Google endpoint contracts with mocked verifier tests
- Token refresh/logout
- Bootstrap endpoint
- Sync endpoint skeleton and conflict schema
- SwiftUI app project scaffold
- Role-aware tab shell foundation
- Token storage and API client
- Offline queue scaffolding
- App Store permission metadata

Later plans should cover:

- Crew workflows
- Owner/manager workflows
- Billing and queued external actions
- Full media uploads
- Full conflict resolution UI
- App Store screenshots/TestFlight/release automation

## File Structure

Create backend files:

- `mobile_api/__init__.py` — app package marker
- `mobile_api/apps.py` — Django app config
- `mobile_api/models.py` — mobile sessions, sync conflicts, queued action audit
- `mobile_api/auth.py` — token generation, hashing, authentication helpers
- `mobile_api/serializers.py` — small JSON shaping helpers, not DRF serializers
- `mobile_api/views.py` — JSON endpoints
- `mobile_api/urls.py` — mobile API routes
- `mobile_api/tests.py` — API tests
- `mobile_api/migrations/__init__.py` — migration package
- Generated migration: `mobile_api/migrations/0001_initial.py`

Modify backend files:

- `config/settings.py` — add `mobile_api` to `INSTALLED_APPS`
- `config/urls.py` — mount `/api/mobile/v1/`

Create iOS files:

- `native/ios/FieldLGXNative/README.md`
- `native/ios/FieldLGXNative/FieldLGXNative.xcodeproj/project.pbxproj`
- `native/ios/FieldLGXNative/FieldLGXNative/FieldLGXNativeApp.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/App/AppShell.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/App/AppTab.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Auth/AuthScreen.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Auth/AuthSession.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/API/APIClient.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/API/APIModels.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Security/KeychainStore.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Sync/SyncQueue.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Sync/SyncModels.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Design/FieldLGXTheme.swift`
- `native/ios/FieldLGXNative/FieldLGXNative/Info.plist`
- `native/ios/FieldLGXNative/FieldLGXNative/Assets.xcassets/Contents.json`
- `native/ios/FieldLGXNative/FieldLGXNative/Assets.xcassets/AppIcon.appiconset/Contents.json`
- `native/ios/FieldLGXNative/FieldLGXNative/Assets.xcassets/AccentColor.colorset/Contents.json`

## Task 1: Create Mobile API Django App

**Files:**
- Create: `mobile_api/__init__.py`
- Create: `mobile_api/apps.py`
- Create: `mobile_api/urls.py`
- Create: `mobile_api/views.py`
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Test: `mobile_api/tests.py`

- [ ] **Step 1: Create the Django app package files**

Create `mobile_api/__init__.py` as an empty file.

Create `mobile_api/apps.py`:

```python
from django.apps import AppConfig


class MobileApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mobile_api"
```

- [ ] **Step 2: Add the first URL and health view**

Create `mobile_api/urls.py`:

```python
from django.urls import path

from . import views

app_name = "mobile_api"

urlpatterns = [
    path("health/", views.health, name="health"),
]
```

Create `mobile_api/views.py`:

```python
from django.http import JsonResponse


def health(request):
    return JsonResponse({
        "ok": True,
        "service": "fieldlgx-mobile-api",
        "version": 1,
    })
```

- [ ] **Step 3: Mount the app**

In `config/settings.py`, add `"mobile_api"` to `INSTALLED_APPS`.

In `config/urls.py`, add:

```python
path("api/mobile/v1/", include("mobile_api.urls")),
```

Use the existing import style. If `include` is already imported, do not duplicate it.

- [ ] **Step 4: Write the health endpoint test**

Create `mobile_api/tests.py`:

```python
from django.test import TestCase
from django.urls import reverse


class MobileHealthTests(TestCase):
    def test_health_endpoint_returns_version(self):
        response = self.client.get(reverse("mobile_api:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "service": "fieldlgx-mobile-api",
            "version": 1,
        })
```

- [ ] **Step 5: Run the targeted test**

Run:

```bash
./run test mobile_api.tests.MobileHealthTests
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add mobile_api config/settings.py config/urls.py
git commit -m "Add mobile API foundation"
```

## Task 2: Add Mobile Session Tokens

**Files:**
- Create: `mobile_api/models.py`
- Create: `mobile_api/auth.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Modify: `mobile_api/tests.py`
- Create: `mobile_api/migrations/0001_initial.py`

- [ ] **Step 1: Write failing login/refresh/logout tests**

Append to `mobile_api/tests.py`:

```python
from django.contrib.auth import get_user_model
from businesses.models import Business
from mobile_api.models import MobileDeviceSession


class MobileAuthTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Landscaping")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="nativeowner",
            email="nativeowner@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )

    def test_email_password_login_issues_tokens(self):
        response = self.client.post(
            reverse("mobile_api:login"),
            data={
                "email": "nativeowner@example.com",
                "password": "testpass123",
                "device_name": "Aden iPhone",
                "platform": "ios",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access_token", payload)
        self.assertIn("refresh_token", payload)
        self.assertEqual(payload["user"]["role"], "owner")
        self.assertTrue(MobileDeviceSession.objects.filter(user=self.user, revoked_at__isnull=True).exists())

    def test_refresh_rotates_access_token(self):
        login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "nativeowner@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

        response = self.client.post(
            reverse("mobile_api:refresh"),
            data={"refresh_token": login["refresh_token"]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    def test_logout_revokes_device_session(self):
        login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "nativeowner@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

        response = self.client.post(
            reverse("mobile_api:logout"),
            data={"refresh_token": login["refresh_token"]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(MobileDeviceSession.objects.filter(user=self.user, revoked_at__isnull=True).exists())
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
./run test mobile_api.tests.MobileAuthTests
```

Expected: failure because `MobileDeviceSession` and auth routes do not exist.

- [ ] **Step 3: Implement the mobile session model**

Create `mobile_api/models.py`:

```python
import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MobileDeviceSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_sessions")
    business = models.ForeignKey("businesses.Business", on_delete=models.CASCADE, related_name="mobile_sessions")
    device_name = models.CharField(max_length=120, blank=True)
    platform = models.CharField(max_length=20, default="ios")
    refresh_token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

    @classmethod
    def issue(cls, user, device_name="", platform="ios"):
        raw_refresh = secrets.token_urlsafe(48)
        session = cls.objects.create(
            user=user,
            business=user.business,
            device_name=(device_name or "")[:120],
            platform=(platform or "ios")[:20],
            refresh_token_hash=hash_token(raw_refresh),
        )
        return session, raw_refresh

    @property
    def is_active(self):
        return self.revoked_at is None

    def revoke(self):
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])
```

- [ ] **Step 4: Generate migration**

Run:

```bash
./run makemigrations mobile_api
```

Expected: creates `mobile_api/migrations/0001_initial.py`.

- [ ] **Step 5: Implement token helpers**

Create `mobile_api/auth.py`:

```python
import base64
import json
import secrets
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import MobileDeviceSession, hash_token

ACCESS_TOKEN_TTL_SECONDS = 15 * 60


def _signing_key():
    return settings.SECRET_KEY


def issue_access_token(session):
    import hmac
    import hashlib

    payload = {
        "sid": session.id,
        "uid": session.user_id,
        "bid": session.business_id,
        "exp": int(time.time()) + ACCESS_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(8),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_signing_key().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def authenticate_access_token(token):
    import hmac
    import hashlib

    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_signing_key().encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    padded = body + ("=" * (-len(body) % 4))
    payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    if payload.get("exp", 0) < int(time.time()):
        return None
    session = MobileDeviceSession.objects.select_related("user", "business").filter(
        id=payload.get("sid"),
        user_id=payload.get("uid"),
        business_id=payload.get("bid"),
        revoked_at__isnull=True,
    ).first()
    if not session:
        return None
    session.last_seen_at = timezone.now()
    session.save(update_fields=["last_seen_at"])
    return session


def session_from_refresh_token(refresh_token):
    if not refresh_token:
        return None
    return MobileDeviceSession.objects.select_related("user", "business").filter(
        refresh_token_hash=hash_token(refresh_token),
        revoked_at__isnull=True,
    ).first()


def user_by_email(email):
    User = get_user_model()
    return User.objects.filter(email__iexact=(email or "").strip(), is_active=True).first()
```

- [ ] **Step 6: Implement auth views**

Update `mobile_api/views.py`:

```python
import json

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .auth import issue_access_token, session_from_refresh_token, user_by_email
from .models import MobileDeviceSession


def _json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def _user_payload(user):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "role": user.role,
        "business_id": user.business_id,
    }


def health(request):
    return JsonResponse({
        "ok": True,
        "service": "fieldlgx-mobile-api",
        "version": 1,
    })


@csrf_exempt
@require_POST
def login(request):
    data = _json_body(request)
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    user = user_by_email(email)
    if not user or not user.check_password(password) or not user.business_id:
        return JsonResponse({"error": "Invalid email or password."}, status=400)
    session, refresh_token = MobileDeviceSession.issue(
        user=user,
        device_name=data.get("device_name") or "",
        platform=data.get("platform") or "ios",
    )
    return JsonResponse({
        "access_token": issue_access_token(session),
        "refresh_token": refresh_token,
        "user": _user_payload(user),
    })


@csrf_exempt
@require_POST
def refresh(request):
    data = _json_body(request)
    session = session_from_refresh_token(data.get("refresh_token"))
    if not session:
        return JsonResponse({"error": "Invalid refresh token."}, status=401)
    return JsonResponse({
        "access_token": issue_access_token(session),
        "user": _user_payload(session.user),
    })


@csrf_exempt
@require_POST
def logout(request):
    data = _json_body(request)
    session = session_from_refresh_token(data.get("refresh_token"))
    if session:
        session.revoke()
    return JsonResponse({"ok": True})
```

Update `mobile_api/urls.py`:

```python
from django.urls import path

from . import views

app_name = "mobile_api"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("auth/login/", views.login, name="login"),
    path("auth/refresh/", views.refresh, name="refresh"),
    path("auth/logout/", views.logout, name="logout"),
]
```

- [ ] **Step 7: Run auth tests**

Run:

```bash
./run test mobile_api.tests.MobileAuthTests
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add mobile_api
git commit -m "Add mobile API token authentication"
```

## Task 3: Add Apple and Google Auth Endpoint Contracts

**Files:**
- Modify: `mobile_api/auth.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Modify: `mobile_api/tests.py`

- [ ] **Step 1: Write tests with mocked provider verification**

Append to `mobile_api/tests.py`:

```python
from unittest.mock import patch


class MobileSocialAuthTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Social")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="socialowner",
            email="social@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )

    @patch("mobile_api.auth.verify_apple_identity_token")
    def test_apple_login_issues_tokens_for_existing_user(self, mock_verify):
        mock_verify.return_value = {"email": "social@example.com", "sub": "apple-sub-1"}

        response = self.client.post(
            reverse("mobile_api:apple_login"),
            data={"identity_token": "apple.jwt", "device_name": "iPhone"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    @patch("mobile_api.auth.verify_google_identity_token")
    def test_google_login_issues_tokens_for_existing_user(self, mock_verify):
        mock_verify.return_value = {"email": "social@example.com", "sub": "google-sub-1"}

        response = self.client.post(
            reverse("mobile_api:google_login"),
            data={"identity_token": "google.jwt", "device_name": "iPhone"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
./run test mobile_api.tests.MobileSocialAuthTests
```

Expected: failure because routes and verifier functions do not exist.

- [ ] **Step 3: Add verifier contracts**

Append to `mobile_api/auth.py`:

```python
def verify_apple_identity_token(identity_token):
    """
    Verify Apple identity token and return {"email": str, "sub": str}.
    Full Apple JWKS validation ships in the social-auth implementation task.
    """
    raise NotImplementedError("Apple identity token verification is not configured yet.")


def verify_google_identity_token(identity_token):
    """
    Verify Google identity token and return {"email": str, "sub": str}.
    Full Google token validation ships in the social-auth implementation task.
    """
    raise NotImplementedError("Google identity token verification is not configured yet.")
```

- [ ] **Step 4: Implement social auth views**

Append to `mobile_api/views.py`:

```python
from .auth import verify_apple_identity_token, verify_google_identity_token


def _login_existing_social_user(request, verifier):
    data = _json_body(request)
    identity_token = data.get("identity_token") or ""
    try:
        verified = verifier(identity_token)
    except Exception:
        return JsonResponse({"error": "Could not verify identity token."}, status=400)
    user = user_by_email(verified.get("email"))
    if not user or not user.business_id:
        return JsonResponse({"error": "No FIELDLGX account is linked to this email."}, status=404)
    session, refresh_token = MobileDeviceSession.issue(
        user=user,
        device_name=data.get("device_name") or "",
        platform="ios",
    )
    return JsonResponse({
        "access_token": issue_access_token(session),
        "refresh_token": refresh_token,
        "user": _user_payload(user),
    })


@csrf_exempt
@require_POST
def apple_login(request):
    return _login_existing_social_user(request, verify_apple_identity_token)


@csrf_exempt
@require_POST
def google_login(request):
    return _login_existing_social_user(request, verify_google_identity_token)
```

Update `mobile_api/urls.py`:

```python
path("auth/apple/", views.apple_login, name="apple_login"),
path("auth/google/", views.google_login, name="google_login"),
```

- [ ] **Step 5: Run social auth tests**

Run:

```bash
./run test mobile_api.tests.MobileSocialAuthTests
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add mobile_api
git commit -m "Add mobile social auth endpoint contracts"
```

## Task 4: Add Authenticated Bootstrap Endpoint

**Files:**
- Modify: `mobile_api/auth.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Modify: `mobile_api/tests.py`

- [ ] **Step 1: Write bootstrap test**

Append to `mobile_api/tests.py`:

```python
class MobileBootstrapTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Bootstrap")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="bootowner",
            email="boot@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )

    def test_bootstrap_returns_user_business_and_modules(self):
        login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "boot@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

        response = self.client.get(
            reverse("mobile_api:bootstrap"),
            HTTP_AUTHORIZATION=f"Bearer {login['access_token']}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "boot@example.com")
        self.assertEqual(payload["business"]["name"], "QA Native Bootstrap")
        self.assertIn("jobs", payload["modules"])
        self.assertIn("sync", payload)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
./run test mobile_api.tests.MobileBootstrapTests
```

Expected: failure because `bootstrap` route does not exist.

- [ ] **Step 3: Add bearer helper**

Append to `mobile_api/auth.py`:

```python
def session_from_request(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return None
    return authenticate_access_token(header.removeprefix("Bearer ").strip())
```

- [ ] **Step 4: Implement bootstrap view**

Append to `mobile_api/views.py`:

```python
from .auth import session_from_request


def _business_payload(business):
    return {
        "id": business.id,
        "name": business.name,
        "timezone": getattr(business, "timezone", "America/New_York"),
        "client_card_payments_enabled": bool(getattr(business, "client_card_payments_enabled", False)),
        "client_saved_cards_enabled": bool(getattr(business, "client_saved_cards_enabled", False)),
    }


def bootstrap(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    modules = ["dashboard", "jobs", "calendar", "clients", "billing", "time", "sync"]
    if session.user.role in {"owner", "manager"}:
        modules.extend(["employees", "financials", "settings", "fertilization", "agreements"])
    return JsonResponse({
        "user": _user_payload(session.user),
        "business": _business_payload(session.business),
        "modules": modules,
        "sync": {
            "cursor": None,
            "server_time": session.last_seen_at.isoformat(),
        },
    })
```

Update `mobile_api/urls.py`:

```python
path("bootstrap/", views.bootstrap, name="bootstrap"),
```

- [ ] **Step 5: Run bootstrap test**

Run:

```bash
./run test mobile_api.tests.MobileBootstrapTests
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add mobile_api
git commit -m "Add mobile bootstrap endpoint"
```

## Task 5: Add Sync Conflict and Mutation API Skeleton

**Files:**
- Modify: `mobile_api/models.py`
- Modify: `mobile_api/views.py`
- Modify: `mobile_api/urls.py`
- Modify: `mobile_api/tests.py`
- Create migration: `mobile_api/migrations/0002_sync_foundation.py`

- [ ] **Step 1: Write sync contract tests**

Append to `mobile_api/tests.py`:

```python
class MobileSyncTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Sync")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="syncowner",
            email="sync@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "sync@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_sync_pull_returns_empty_initial_delta(self):
        response = self.client.get(reverse("mobile_api:sync_pull"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["changes"], {})
        self.assertIn("cursor", response.json())

    def test_sync_push_rejects_unknown_entity_without_crashing(self):
        response = self.client.post(
            reverse("mobile_api:sync_push"),
            data={"mutations": [{"entity_type": "unknown", "operation": "create", "payload": {}}]},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["accepted"], [])
        self.assertEqual(response.json()["rejected"][0]["reason"], "Unsupported entity type.")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
./run test mobile_api.tests.MobileSyncTests
```

Expected: failure because sync routes do not exist.

- [ ] **Step 3: Add sync models**

Append to `mobile_api/models.py`:

```python
class MobileSyncConflict(models.Model):
    business = models.ForeignKey("businesses.Business", on_delete=models.CASCADE, related_name="mobile_sync_conflicts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="mobile_sync_conflicts")
    entity_type = models.CharField(max_length=80)
    server_id = models.CharField(max_length=80, blank=True)
    local_id = models.CharField(max_length=80, blank=True)
    base_revision = models.CharField(max_length=120, blank=True)
    server_revision = models.CharField(max_length=120, blank=True)
    local_payload = models.JSONField(default=dict, blank=True)
    server_payload = models.JSONField(default=dict, blank=True)
    mergeable_fields = models.JSONField(default=list, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

- [ ] **Step 4: Generate migration**

Run:

```bash
./run makemigrations mobile_api
```

Expected: creates `mobile_api/migrations/0002_sync_foundation.py`.

- [ ] **Step 5: Implement sync views**

Append to `mobile_api/views.py`:

```python
from django.utils import timezone


SUPPORTED_SYNC_ENTITIES = {
    "client",
    "property",
    "job",
    "job_note",
    "property_note",
    "job_service_item",
    "estimate",
    "invoice",
    "time_entry",
    "location_event",
}


def sync_pull(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    return JsonResponse({
        "cursor": timezone.now().isoformat(),
        "changes": {},
        "conflicts": [],
    })


@csrf_exempt
@require_POST
def sync_push(request):
    session = session_from_request(request)
    if not session:
        return JsonResponse({"error": "Authentication required."}, status=401)
    data = _json_body(request)
    accepted = []
    rejected = []
    for index, mutation in enumerate(data.get("mutations", [])):
        entity_type = mutation.get("entity_type")
        if entity_type not in SUPPORTED_SYNC_ENTITIES:
            rejected.append({
                "index": index,
                "entity_type": entity_type,
                "reason": "Unsupported entity type.",
            })
            continue
        accepted.append({
            "index": index,
            "entity_type": entity_type,
            "status": "queued_for_implementation",
        })
    return JsonResponse({
        "accepted": accepted,
        "rejected": rejected,
        "conflicts": [],
    })
```

Update `mobile_api/urls.py`:

```python
path("sync/pull/", views.sync_pull, name="sync_pull"),
path("sync/push/", views.sync_push, name="sync_push"),
```

- [ ] **Step 6: Run sync tests**

Run:

```bash
./run test mobile_api.tests.MobileSyncTests
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add mobile_api
git commit -m "Add mobile sync API skeleton"
```

## Task 6: Create SwiftUI iPhone App Project Skeleton

**Files:**
- Create: `native/ios/FieldLGXNative/README.md`
- Create: `native/ios/FieldLGXNative/FieldLGXNative.xcodeproj/project.pbxproj`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/FieldLGXNativeApp.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/AppShell.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/App/AppTab.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/Design/FieldLGXTheme.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/Info.plist`
- Create asset catalog JSON files

- [ ] **Step 1: Create project folder structure**

Create:

```text
native/ios/FieldLGXNative/
native/ios/FieldLGXNative/FieldLGXNative/
native/ios/FieldLGXNative/FieldLGXNative/App/
native/ios/FieldLGXNative/FieldLGXNative/Auth/
native/ios/FieldLGXNative/FieldLGXNative/API/
native/ios/FieldLGXNative/FieldLGXNative/Security/
native/ios/FieldLGXNative/FieldLGXNative/Sync/
native/ios/FieldLGXNative/FieldLGXNative/Design/
native/ios/FieldLGXNative/FieldLGXNative/Assets.xcassets/
native/ios/FieldLGXNative/FieldLGXNative/Assets.xcassets/AppIcon.appiconset/
native/ios/FieldLGXNative/FieldLGXNative/Assets.xcassets/AccentColor.colorset/
```

- [ ] **Step 2: Add README**

Create `native/ios/FieldLGXNative/README.md`:

```markdown
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
```

- [ ] **Step 3: Add Info.plist with permissions**

Create `native/ios/FieldLGXNative/FieldLGXNative/Info.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>FIELDLGX</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
    </array>
    <key>NSCameraUsageDescription</key>
    <string>FIELDLGX uses the camera to capture job photos, completion proof, estimate images, receipts, and field issue documentation.</string>
    <key>NSPhotoLibraryUsageDescription</key>
    <string>FIELDLGX uses your photo library so you can attach existing photos to jobs, estimates, properties, receipts, and issues.</string>
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>FIELDLGX uses location while you are clocked in to record time and job timeline events for field operations.</string>
    <key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
    <string>FIELDLGX can record periodic location timeline events while you are clocked in, even if the app is in the background.</string>
    <key>UIBackgroundModes</key>
    <array>
        <string>location</string>
    </array>
</dict>
</plist>
```

- [ ] **Step 4: Add theme**

Create `native/ios/FieldLGXNative/FieldLGXNative/Design/FieldLGXTheme.swift`:

```swift
import SwiftUI

enum FieldLGXTheme {
    static let background = Color(red: 0.02, green: 0.025, blue: 0.02)
    static let panel = Color(red: 0.10, green: 0.11, blue: 0.10)
    static let panelStroke = Color.white.opacity(0.14)
    static let lime = Color(red: 0.63, green: 0.91, blue: 0.29)
    static let text = Color.white
    static let secondaryText = Color.white.opacity(0.62)
}
```

- [ ] **Step 5: Add app tabs**

Create `native/ios/FieldLGXNative/FieldLGXNative/App/AppTab.swift`:

```swift
import SwiftUI

enum AppRole: String, Codable {
    case owner
    case manager
    case crew
}

enum AppTab: String, CaseIterable, Identifiable {
    case command
    case calendar
    case work
    case clients
    case money
    case today
    case route
    case time
    case messages
    case more

    var id: String { rawValue }

    var title: String {
        switch self {
        case .command: "Command"
        case .calendar: "Calendar"
        case .work: "Work"
        case .clients: "Clients"
        case .money: "Money"
        case .today: "Today"
        case .route: "Route"
        case .time: "Time"
        case .messages: "Messages"
        case .more: "More"
        }
    }

    var systemImage: String {
        switch self {
        case .command: "square.grid.2x2"
        case .calendar: "calendar"
        case .work: "checklist"
        case .clients: "person.2"
        case .money: "dollarsign.circle"
        case .today: "sun.max"
        case .route: "map"
        case .time: "clock"
        case .messages: "bubble.left.and.bubble.right"
        case .more: "ellipsis.circle"
        }
    }

    static func tabs(for role: AppRole) -> [AppTab] {
        switch role {
        case .owner, .manager:
            return [.command, .calendar, .work, .clients, .money, .more]
        case .crew:
            return [.today, .route, .time, .messages, .more]
        }
    }
}
```

- [ ] **Step 6: Add app shell**

Create `native/ios/FieldLGXNative/FieldLGXNative/App/AppShell.swift`:

```swift
import SwiftUI

struct AppShell: View {
    let role: AppRole

    var body: some View {
        TabView {
            ForEach(AppTab.tabs(for: role)) { tab in
                NavigationStack {
                    PlaceholderScreen(title: tab.title)
                }
                .tabItem {
                    Label(tab.title, systemImage: tab.systemImage)
                }
            }
        }
        .tint(FieldLGXTheme.lime)
    }
}

private struct PlaceholderScreen: View {
    let title: String

    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()
            VStack(alignment: .leading, spacing: 16) {
                Text(title.uppercased())
                    .font(.system(size: 13, weight: .bold))
                    .tracking(4)
                    .foregroundStyle(FieldLGXTheme.lime)
                Text(title)
                    .font(.system(size: 44, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                Text("Native FIELDLGX screen foundation.")
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                Spacer()
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

#Preview {
    AppShell(role: .owner)
}
```

- [ ] **Step 7: Add app entry**

Create `native/ios/FieldLGXNative/FieldLGXNative/FieldLGXNativeApp.swift`:

```swift
import SwiftUI

@main
struct FieldLGXNativeApp: App {
    var body: some Scene {
        WindowGroup {
            AppShell(role: .owner)
        }
    }
}
```

- [ ] **Step 8: Create Xcode project**

Use Xcode to create a new iOS App project:

- Product Name: `FieldLGXNative`
- Interface: SwiftUI
- Language: Swift
- Minimum Deployments: iOS 17.0
- Organization Identifier: `com.fieldlgx`
- Bundle Identifier: `com.fieldlgx.native`
- Location: `native/ios/FieldLGXNative`

Then replace the generated Swift source files with the files from this task. Keep the generated `.xcodeproj` structure.

- [ ] **Step 9: Build**

Run:

```bash
xcodebuild -project native/ios/FieldLGXNative/FieldLGXNative.xcodeproj -scheme FieldLGXNative -destination 'platform=iOS Simulator,name=iPhone 16' build
```

Expected: build succeeds.

- [ ] **Step 10: Commit**

```bash
git add native/ios/FieldLGXNative
git commit -m "Add FIELDLGX native SwiftUI app shell"
```

## Task 7: Add iOS Token Storage and API Client

**Files:**
- Create: `native/ios/FieldLGXNative/FieldLGXNative/Security/KeychainStore.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/API/APIModels.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/API/APIClient.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/Auth/AuthSession.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/Auth/AuthScreen.swift`
- Modify: `native/ios/FieldLGXNative/FieldLGXNative/FieldLGXNativeApp.swift`

- [ ] **Step 1: Add API models**

Create `APIModels.swift`:

```swift
import Foundation

struct MobileUser: Codable, Equatable {
    let id: Int
    let email: String
    let username: String
    let name: String
    let role: AppRole
    let businessID: Int?

    enum CodingKeys: String, CodingKey {
        case id, email, username, name, role
        case businessID = "business_id"
    }
}

struct LoginResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let user: MobileUser

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

struct BootstrapResponse: Codable {
    let user: MobileUser
    let modules: [String]
}
```

- [ ] **Step 2: Add Keychain wrapper**

Create `KeychainStore.swift`:

```swift
import Foundation
import Security

struct KeychainStore {
    let service: String

    func save(_ value: String, account: String) throws {
        let data = Data(value.utf8)
        SecItemDelete(query(account: account) as CFDictionary)
        var item = query(account: account)
        item[kSecValueData as String] = data
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError.status(status) }
    }

    func read(account: String) throws -> String? {
        var item = query(account: account)
        item[kSecReturnData as String] = true
        item[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(item as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data else { throw KeychainError.status(status) }
        return String(data: data, encoding: .utf8)
    }

    func delete(account: String) {
        SecItemDelete(query(account: account) as CFDictionary)
    }

    private func query(account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
    }
}

enum KeychainError: Error {
    case status(OSStatus)
}
```

- [ ] **Step 3: Add API client**

Create `APIClient.swift`:

```swift
import Foundation

struct APIClient {
    var baseURL: URL
    var accessToken: String?
    var urlSession: URLSession = .shared

    func login(email: String, password: String) async throws -> LoginResponse {
        try await post(path: "/api/mobile/v1/auth/login/", body: [
            "email": email,
            "password": password,
            "platform": "ios",
            "device_name": UIDevice.current.name
        ])
    }

    func bootstrap() async throws -> BootstrapResponse {
        try await get(path: "/api/mobile/v1/bootstrap/")
    }

    private func get<T: Decodable>(path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
        request.httpMethod = "GET"
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func post<T: Decodable>(path: String, body: [String: String]) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func addAuth(to request: inout URLRequest) {
        if let accessToken {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw APIError.badResponse
        }
    }
}

enum APIError: Error {
    case badResponse
}
```

If this file fails because `UIDevice` is unavailable, add `import UIKit` at the top.

- [ ] **Step 4: Add auth session**

Create `AuthSession.swift`:

```swift
import Foundation
import Observation

@Observable
final class AuthSession {
    var user: MobileUser?
    var accessToken: String?
    var isLoading = false
    var errorMessage: String?

    private let keychain = KeychainStore(service: "com.fieldlgx.native.auth")
    private let baseURL = URL(string: "http://127.0.0.1:8004")!

    var isAuthenticated: Bool {
        user != nil && accessToken != nil
    }

    func signIn(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let client = APIClient(baseURL: baseURL)
            let response = try await client.login(email: email, password: password)
            try keychain.save(response.refreshToken, account: "refresh_token")
            accessToken = response.accessToken
            user = response.user
        } catch {
            errorMessage = "Could not sign in. Check your credentials and connection."
        }
    }

    func signOut() {
        keychain.delete(account: "refresh_token")
        accessToken = nil
        user = nil
    }
}
```

- [ ] **Step 5: Add auth screen**

Create `AuthScreen.swift`:

```swift
import SwiftUI

struct AuthScreen: View {
    @Bindable var session: AuthSession
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()
            VStack(alignment: .leading, spacing: 18) {
                Text("FIELDLGX")
                    .font(.system(size: 18, weight: .black))
                    .tracking(4)
                    .foregroundStyle(FieldLGXTheme.lime)
                Text("Run the day. Own the season.")
                    .font(.system(size: 40, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                TextField("Email", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .textContentType(.username)
                    .fieldLGXInput()
                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .fieldLGXInput()
                Button {
                    Task { await session.signIn(email: email, password: password) }
                } label: {
                    Text(session.isLoading ? "Signing in..." : "Sign in")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(FieldLGXPrimaryButtonStyle())
                .disabled(session.isLoading)
                if let errorMessage = session.errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                        .font(.footnote.weight(.semibold))
                }
                Spacer()
            }
            .padding(24)
        }
    }
}

private extension View {
    func fieldLGXInput() -> some View {
        self
            .padding(16)
            .background(FieldLGXTheme.panel)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(FieldLGXTheme.panelStroke))
            .foregroundStyle(FieldLGXTheme.text)
    }
}

struct FieldLGXPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 17, weight: .bold))
            .padding(16)
            .background(FieldLGXTheme.lime)
            .foregroundStyle(.black)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
    }
}
```

- [ ] **Step 6: Wire auth into app entry**

Update `FieldLGXNativeApp.swift`:

```swift
import SwiftUI

@main
struct FieldLGXNativeApp: App {
    @State private var session = AuthSession()

    var body: some Scene {
        WindowGroup {
            if let user = session.user {
                AppShell(role: user.role)
            } else {
                AuthScreen(session: session)
            }
        }
    }
}
```

- [ ] **Step 7: Build**

Run:

```bash
xcodebuild -project native/ios/FieldLGXNative/FieldLGXNative.xcodeproj -scheme FieldLGXNative -destination 'platform=iOS Simulator,name=iPhone 16' build
```

Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
git add native/ios/FieldLGXNative
git commit -m "Add native iOS auth foundation"
```

## Task 8: Add Offline Queue Scaffolding

**Files:**
- Create: `native/ios/FieldLGXNative/FieldLGXNative/Sync/SyncModels.swift`
- Create: `native/ios/FieldLGXNative/FieldLGXNative/Sync/SyncQueue.swift`

- [ ] **Step 1: Add sync models**

Create `SyncModels.swift`:

```swift
import Foundation
import SwiftData

enum SyncOperation: String, Codable {
    case create
    case update
    case delete
    case externalAction
}

@Model
final class PendingMutation {
    @Attribute(.unique) var localID: UUID
    var entityType: String
    var serverID: String?
    var operation: String
    var payloadJSON: String
    var baseRevision: String?
    var createdAt: Date
    var retryCount: Int
    var failureReason: String?
    var requiresConfirmation: Bool
    var confirmedAt: Date?

    init(
        localID: UUID = UUID(),
        entityType: String,
        serverID: String? = nil,
        operation: SyncOperation,
        payloadJSON: String,
        baseRevision: String? = nil,
        requiresConfirmation: Bool = false
    ) {
        self.localID = localID
        self.entityType = entityType
        self.serverID = serverID
        self.operation = operation.rawValue
        self.payloadJSON = payloadJSON
        self.baseRevision = baseRevision
        self.createdAt = Date()
        self.retryCount = 0
        self.failureReason = nil
        self.requiresConfirmation = requiresConfirmation
        self.confirmedAt = nil
    }
}
```

- [ ] **Step 2: Add sync queue service**

Create `SyncQueue.swift`:

```swift
import Foundation
import SwiftData

@MainActor
final class SyncQueue {
    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
    }

    func enqueue(entityType: String, serverID: String?, operation: SyncOperation, payload: [String: Any], baseRevision: String?, requiresConfirmation: Bool = false) throws {
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        let json = String(data: data, encoding: .utf8) ?? "{}"
        let mutation = PendingMutation(
            entityType: entityType,
            serverID: serverID,
            operation: operation,
            payloadJSON: json,
            baseRevision: baseRevision,
            requiresConfirmation: requiresConfirmation
        )
        modelContext.insert(mutation)
        try modelContext.save()
    }

    func pendingCount() throws -> Int {
        let descriptor = FetchDescriptor<PendingMutation>()
        return try modelContext.fetchCount(descriptor)
    }
}
```

- [ ] **Step 3: Wire SwiftData model container**

Update `FieldLGXNativeApp.swift`:

```swift
import SwiftData
import SwiftUI

@main
struct FieldLGXNativeApp: App {
    @State private var session = AuthSession()

    var body: some Scene {
        WindowGroup {
            if let user = session.user {
                AppShell(role: user.role)
            } else {
                AuthScreen(session: session)
            }
        }
        .modelContainer(for: PendingMutation.self)
    }
}
```

- [ ] **Step 4: Build**

Run:

```bash
xcodebuild -project native/ios/FieldLGXNative/FieldLGXNative.xcodeproj -scheme FieldLGXNative -destination 'platform=iOS Simulator,name=iPhone 16' build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add native/ios/FieldLGXNative
git commit -m "Add native iOS offline sync queue scaffold"
```

## Task 9: Full Foundation Verification

**Files:**
- No new files

- [ ] **Step 1: Run backend tests**

Run:

```bash
./run test mobile_api.tests
```

Expected: all mobile API tests pass.

- [ ] **Step 2: Run project checks**

Run:

```bash
./run check
```

Expected: no issues.

- [ ] **Step 3: Run existing test suite**

Run:

```bash
./run test
```

Expected: all existing tests still pass.

- [ ] **Step 4: Build native app**

Run:

```bash
xcodebuild -project native/ios/FieldLGXNative/FieldLGXNative.xcodeproj -scheme FieldLGXNative -destination 'platform=iOS Simulator,name=iPhone 16' build
```

Expected: build succeeds.

- [ ] **Step 5: Run manual simulator smoke**

Open the app in the iPhone simulator. Verify:

- App launches to FIELDLGX login.
- Email/password login works against local server.
- Owner user lands in owner tabs.
- Crew user lands in crew tabs.
- Tab switching works.
- App does not ask for location/camera/photos on launch.
- No crash on relaunch.

- [ ] **Step 6: Commit verification notes**

Create `docs/superpowers/plans/2026-04-28-fieldlgx-native-ios-foundation-verification.md` with:

```markdown
# FIELDLGX Native iOS Foundation Verification

- Backend mobile API tests:
- Django system check:
- Existing test suite:
- iOS simulator build:
- Manual simulator smoke:
- Known limitations:
```

Fill in the actual command outputs and any limitations observed.

Commit:

```bash
git add docs/superpowers/plans/2026-04-28-fieldlgx-native-ios-foundation-verification.md
git commit -m "Record native iOS foundation verification"
```

## Self-Review

Spec coverage:

- Mobile API foundation: Tasks 1-5
- Mobile auth: Tasks 2-4 and 7
- Social auth day-one contracts: Task 3
- SwiftUI app scaffold: Task 6
- Token storage: Task 7
- Offline queue scaffold: Task 8
- App Store permission metadata: Task 6
- Verification: Task 9

Known gaps intentionally deferred to later plans:

- Complete Apple/Google JWT validation
- Full model sync for jobs/clients/billing
- Full location timeline implementation
- Camera/photo picker and upload queue
- Full owner/crew screens
- TestFlight/App Store Connect setup

Placeholder scan:

- This plan contains no unresolved fill-in text.
- Implementation defaults are explicit.

Type consistency:

- `AppRole` is defined before `MobileUser` uses it.
- `PendingMutation` is defined before `.modelContainer(for:)`.
- API route names used in tests are defined in the corresponding URL tasks.

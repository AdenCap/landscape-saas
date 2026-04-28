from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from businesses.models import Business


class MobileHealthTests(TestCase):
    def test_health_endpoint_returns_version(self):
        response = self.client.get(reverse("mobile_api:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "service": "fieldlgx-mobile-api",
            "version": 1,
        })


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
        from mobile_api.models import MobileDeviceSession

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

    def test_access_token_authenticates_device_session(self):
        from mobile_api.auth import authenticate_access_token

        login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "nativeowner@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

        session = authenticate_access_token(login["access_token"])

        self.assertIsNotNone(session)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.business, self.business)

    def test_invalid_access_token_fails_closed(self):
        from mobile_api.auth import authenticate_access_token

        self.assertIsNone(authenticate_access_token("not-a-real-token"))
        self.assertIsNone(authenticate_access_token("broken.signature"))

    def test_logout_revokes_device_session(self):
        from mobile_api.models import MobileDeviceSession

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
            data={"identity_token": "apple.jwt", "device_name": "Aden iPhone"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    @patch("mobile_api.auth.verify_google_identity_token")
    def test_google_login_issues_tokens_for_existing_user(self, mock_verify):
        mock_verify.return_value = {"email": "social@example.com", "sub": "google-sub-1"}

        response = self.client.post(
            reverse("mobile_api:google_login"),
            data={"identity_token": "google.jwt", "device_name": "Aden iPhone"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    @patch("mobile_api.auth.verify_apple_identity_token")
    def test_social_login_requires_existing_business_user(self, mock_verify):
        mock_verify.return_value = {"email": "not-linked@example.com", "sub": "apple-sub-2"}

        response = self.client.post(
            reverse("mobile_api:apple_login"),
            data={"identity_token": "apple.jwt"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)


class MobileBootstrapTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Bootstrap")
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="bootowner",
            email="boot@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.crew = User.objects.create_user(
            username="bootcrew",
            email="crewboot@example.com",
            password="testpass123",
            business=self.business,
            role="crew",
        )

    def _login(self, email):
        return self.client.post(
            reverse("mobile_api:login"),
            data={"email": email, "password": "testpass123"},
            content_type="application/json",
        ).json()

    def test_bootstrap_returns_user_business_and_modules(self):
        login = self._login("boot@example.com")

        response = self.client.get(
            reverse("mobile_api:bootstrap"),
            HTTP_AUTHORIZATION=f"Bearer {login['access_token']}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "boot@example.com")
        self.assertEqual(payload["business"]["name"], "QA Native Bootstrap")
        self.assertIn("jobs", payload["modules"])
        self.assertIn("financials", payload["modules"])
        self.assertIn("sync", payload)

    def test_bootstrap_limits_crew_modules(self):
        login = self._login("crewboot@example.com")

        response = self.client.get(
            reverse("mobile_api:bootstrap"),
            HTTP_AUTHORIZATION=f"Bearer {login['access_token']}",
        )

        self.assertEqual(response.status_code, 200)
        modules = response.json()["modules"]
        self.assertIn("jobs", modules)
        self.assertNotIn("financials", modules)
        self.assertNotIn("settings", modules)

    def test_bootstrap_requires_bearer_token(self):
        response = self.client.get(reverse("mobile_api:bootstrap"))

        self.assertEqual(response.status_code, 401)


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
        payload = response.json()
        self.assertEqual(payload["changes"], {})
        self.assertIn("cursor", payload)
        self.assertIn("server_time", payload)

    def test_sync_push_rejects_unknown_entity_without_crashing(self):
        response = self.client.post(
            reverse("mobile_api:sync_push"),
            data={"mutations": [{"entity_type": "unknown", "operation": "create", "payload": {}}]},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accepted"], [])
        self.assertEqual(payload["rejected"][0]["reason"], "Unsupported entity type.")

    def test_sync_requires_authentication(self):
        response = self.client.get(reverse("mobile_api:sync_pull"))

        self.assertEqual(response.status_code, 401)

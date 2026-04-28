from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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

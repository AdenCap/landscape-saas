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

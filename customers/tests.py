from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from businesses.models import Business


class CustomerFormAddressInputTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="customer-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.client.force_login(self.owner)

    @override_settings(GOOGLE_MAPS_API_KEY="test-browser-key")
    def test_customer_add_uses_real_google_maps_key_and_keeps_manual_address_entry_enabled(self):
        response = self.client.get(reverse("customer_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "key=test-browser-key&libraries=places&callback=initAutocomplete")
        self.assertNotContains(response, "key=*** google_maps_api_key }}")
        self.assertContains(response, "restoreManualCustomerAddressInput")
        self.assertContains(response, "input.disabled = false")
        self.assertNotContains(response, "id_address_line1\" disabled")
        self.assertNotContains(response, "id_address_line1\" readonly")

    def test_customer_add_form_has_mobile_friendly_layout_rules(self):
        response = self.client.get(reverse("customer_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@media (max-width: 640px)")
        self.assertContains(response, "grid-template-columns: 1fr")
        self.assertContains(response, "font-size: 16px")

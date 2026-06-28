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


class CustomerOnboardingWorkflowTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
            enabled_modules=["fertilization"],
        )
        self.owner = User.objects.create_user(
            username="onboard-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.client.force_login(self.owner)

    def test_onboarding_creates_mowing_client_recurring_schedule_and_first_job(self):
        response = self.client.post(reverse("customer_onboard"), {
            "name": "Maple Ridge",
            "email": "maple@example.com",
            "address_line1": "100 Maple St",
            "city": "Fort Wayne",
            "state": "IN",
            "postal_code": "46802",
            "property_address": "100 Maple St, Fort Wayne, IN 46802",
            "enable_mowing": "on",
            "mowing_frequency": "biweekly",
            "mowing_price": "72.50",
            "mowing_start_date": "2026-06-20",
            "mowing_schedule_first": "on",
            "mowing_description": "Cut, trim, edge, and blow off hard surfaces.",
        })

        self.assertEqual(response.status_code, 302)

        from customers.models import Customer, Property
        from jobs.models import Job, RecurringJob
        from pricing.models import PropertyServiceRate, ServiceTemplate

        customer = Customer.objects.get(name="Maple Ridge")
        prop = Property.objects.get(customer=customer)
        service = ServiceTemplate.objects.get(business=self.business, name="Mowing")
        recurring = RecurringJob.objects.get(property=prop)
        job = Job.objects.get(property=prop)
        item = job.service_items.get()

        self.assertEqual(recurring.frequency, "biweekly")
        self.assertEqual(str(PropertyServiceRate.objects.get(property=prop, service=service).override_rate), "72.50")
        self.assertEqual(job.scheduled_date.isoformat(), "2026-06-20")
        self.assertEqual(item.description, "Mowing")
        self.assertEqual(item.detail_description, "Cut, trim, edge, and blow off hard surfaces.")
        self.assertEqual(str(item.unit_price), "72.50")

    def test_onboarding_can_schedule_mowing_for_whole_season(self):
        response = self.client.post(reverse("customer_onboard"), {
            "name": "Season Mowing Client",
            "property_address": "500 Season Way",
            "enable_mowing": "on",
            "mowing_frequency": "biweekly",
            "mowing_price": "55.00",
            "mowing_start_date": "2026-06-01",
            "mowing_schedule_mode": "season",
            "mowing_season_end": "2026-07-01",
        })

        self.assertEqual(response.status_code, 302)

        from customers.models import Customer
        from jobs.models import Job, RecurringJob

        customer = Customer.objects.get(name="Season Mowing Client")
        prop = customer.properties.get()
        recurring = RecurringJob.objects.get(property=prop)
        jobs = list(Job.objects.filter(property=prop).order_by("scheduled_date"))

        self.assertEqual(recurring.frequency, "biweekly")
        self.assertEqual([job.scheduled_date.isoformat() for job in jobs], [
            "2026-06-01",
            "2026-06-15",
            "2026-06-29",
        ])
        self.assertTrue(all(job.recurring_job_id == recurring.id for job in jobs))

    def test_onboarding_fertilization_can_start_mid_season_and_schedule_first_round(self):
        from fertilization.models import FertilizationProgram, ProgramRound, ScheduledRound
        from jobs.models import Job

        program = FertilizationProgram.objects.create(
            business=self.business,
            name="Premium Lawn Program",
            grass_type="cool_season",
        )
        for round_number in range(1, 5):
            ProgramRound.objects.create(
                program=program,
                round_number=round_number,
                name=f"Round {round_number}",
                target_month_start=round_number + 2,
                target_month_end=round_number + 2,
            )

        response = self.client.post(reverse("customer_onboard"), {
            "name": "Oak Hollow",
            "property_address": "55 Oak Hollow Dr",
            "enable_fertilization": "on",
            "fert_program": str(program.id),
            "fert_start_round": "3",
            "fert_year": "2026",
            "fert_pricing_method": "per_application",
            "fert_price_per_application": "95.00",
            "fert_first_date": "2026-06-22",
            "fert_schedule_first": "on",
            "fert_notes": "Start at grub control round.",
        })

        self.assertEqual(response.status_code, 302)

        rounds = list(ScheduledRound.objects.order_by("round_number"))
        self.assertEqual([round.round_number for round in rounds], [3, 4])
        self.assertEqual(rounds[0].status, "scheduled")
        self.assertEqual(rounds[0].scheduled_date.isoformat(), "2026-06-22")
        self.assertIsNotNone(rounds[0].job)

        job = Job.objects.get(id=rounds[0].job_id)
        self.assertEqual(job.scheduled_date.isoformat(), "2026-06-22")
        self.assertIn("[Fertilization]", job.notes)
        self.assertEqual(str(job.service_items.get().unit_price), "95.00")

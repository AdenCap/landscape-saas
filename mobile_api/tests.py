from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from datetime import date, time, timedelta
from decimal import Decimal

from billing.models import Estimate, EstimateImage, EstimateLineItem, Invoice, InvoiceLineItem
from businesses.models import Business
from customers.models import Customer, Property
from financials.models import Receipt
from jobs.models import Crew, Job, JobCompletionPhoto, JobIssue, JobNote, JobPhoto, JobServiceItem, PropertyNote
from pricing.models import ServiceTemplate
from time_tracking.models import TimeEntry, TimeEntryLocationPing


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

    def test_login_accepts_username_for_local_native_testing(self):
        response = self.client.post(
            reverse("mobile_api:login"),
            data={
                "email": "nativeowner",
                "password": "testpass123",
                "device_name": "Aden iPhone",
                "platform": "ios",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], "nativeowner@example.com")

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


class MobileCommandTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Command")
        self.other_business = Business.objects.create(name="Other Command")
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="commandowner",
            email="command@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.crew = User.objects.create_user(
            username="commandcrew",
            email="commandcrew@example.com",
            password="testpass123",
            business=self.business,
            role="crew",
        )
        self.customer = Customer.objects.create(business=self.business, name="Maple Ridge")
        self.property = Property.objects.create(customer=self.customer, address="123 Command Ave")
        self.today = date(2026, 5, 6)
        Job.objects.create(
            property=self.property,
            scheduled_date=self.today,
            scheduled_time=time(8, 0),
            status="scheduled",
            assigned_to=self.crew,
        )
        Job.objects.create(
            property=self.property,
            scheduled_date=self.today,
            scheduled_time=time(10, 0),
            status="scheduled",
        )
        Job.objects.create(
            property=self.property,
            scheduled_date=None,
            schedule_by_date=self.today,
            status="scheduled",
        )
        Job.objects.create(
            property=self.property,
            scheduled_date=self.today,
            status="completed",
            completed_at=timezone.now(),
        )
        Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            total=Decimal("125.00"),
            due_date=self.today,
        )
        Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            property=self.property,
            title="Patio Cleanup",
            status="sent",
        )
        other_customer = Customer.objects.create(business=self.other_business, name="Other")
        other_property = Property.objects.create(customer=other_customer, address="999 Away")
        Job.objects.create(property=other_property, scheduled_date=self.today, status="scheduled")
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "command@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_command_returns_owner_operational_summary(self):
        response = self.client.get(
            reverse("mobile_api:command"),
            {"date": self.today.isoformat()},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["date"], "2026-05-06")
        self.assertEqual(payload["summary"]["today_jobs"], 3)
        self.assertEqual(payload["summary"]["active_routes"], 1)
        self.assertEqual(payload["summary"]["unassigned_jobs"], 2)
        self.assertEqual(payload["summary"]["needs_scheduled"], 1)
        self.assertEqual(payload["summary"]["ready_to_bill"], 1)
        self.assertEqual(payload["summary"]["outstanding_total"], "125.00")
        self.assertEqual(payload["summary"]["open_estimates"], 1)
        self.assertEqual(payload["attention"][0]["kind"], "schedule")
        self.assertEqual(payload["next_jobs"][0]["customer"]["name"], "Maple Ridge")

    def test_command_requires_owner_or_manager(self):
        crew_login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "commandcrew@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

        response = self.client.get(
            reverse("mobile_api:command"),
            HTTP_AUTHORIZATION=f"Bearer {crew_login['access_token']}",
        )

        self.assertEqual(response.status_code, 403)


class MobileWorkTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Work")
        self.other_business = Business.objects.create(name="Other Work")
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="workowner",
            email="work@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.customer = Customer.objects.create(business=self.business, name="Birch Lawn")
        self.property = Property.objects.create(customer=self.customer, address="500 Work Way")
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mowing",
            default_rate=Decimal("70.00"),
        )
        self.today = date(2026, 5, 7)
        self.upcoming = Job.objects.create(
            property=self.property,
            scheduled_date=self.today + timedelta(days=2),
            scheduled_time=time(9, 0),
            status="scheduled",
        )
        JobServiceItem.objects.create(job=self.upcoming, service=self.service, quantity=1, unit_price=Decimal("70.00"))
        self.needs_scheduled = Job.objects.create(
            property=self.property,
            scheduled_date=None,
            schedule_by_date=self.today,
            status="scheduled",
        )
        JobServiceItem.objects.create(job=self.needs_scheduled, service=self.service, quantity=1, unit_price=Decimal("70.00"))
        self.finished = Job.objects.create(
            property=self.property,
            scheduled_date=self.today - timedelta(days=1),
            status="completed",
            completed_at=timezone.now(),
        )
        JobServiceItem.objects.create(job=self.finished, service=self.service, quantity=1, unit_price=Decimal("70.00"))
        self.billed = Job.objects.create(
            property=self.property,
            scheduled_date=self.today - timedelta(days=2),
            status="completed",
            completed_at=timezone.now(),
        )
        Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            job=self.billed,
            status="draft",
            total=Decimal("70.00"),
        )
        other_customer = Customer.objects.create(business=self.other_business, name="Other")
        other_property = Property.objects.create(customer=other_customer, address="999 Away")
        Job.objects.create(property=other_property, scheduled_date=self.today + timedelta(days=1), status="scheduled")
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "work@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_work_returns_owner_pipeline_sections(self):
        response = self.client.get(
            reverse("mobile_api:work"),
            {"date": self.today.isoformat()},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["upcoming"], 1)
        self.assertEqual(payload["summary"]["needs_scheduled"], 1)
        self.assertEqual(payload["summary"]["finished"], 2)
        self.assertEqual(payload["summary"]["needs_billing"], 1)
        self.assertEqual(payload["sections"]["upcoming"][0]["id"], self.upcoming.id)
        self.assertEqual(payload["sections"]["needs_scheduled"][0]["id"], self.needs_scheduled.id)
        self.assertEqual(payload["sections"]["finished"][0]["customer"]["name"], "Birch Lawn")
        self.assertEqual(payload["sections"]["needs_billing"][0]["id"], self.finished.id)
        self.assertEqual(payload["service_filters"][0]["label"], "All")
        self.assertIn("Mowing", [item["label"] for item in payload["service_filters"]])

    def test_work_filters_by_service(self):
        response = self.client.get(
            reverse("mobile_api:work"),
            {"date": self.today.isoformat(), "service": "mowing"},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["upcoming"], 1)

    def test_work_requires_owner_or_manager(self):
        self.owner.role = "crew"
        self.owner.save(update_fields=["role"])

        response = self.client.get(
            reverse("mobile_api:work"),
            {"date": self.today.isoformat()},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 403)


class MobileClientTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Clients")
        self.other_business = Business.objects.create(name="Other Clients")
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="clientowner",
            email="clients@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Willow Creek",
            email="willow@example.com",
            phone="555-1000",
            invoice_frequency="monthly",
            card_last4="4242",
            card_brand="visa",
            auto_charge_monthly_invoices=True,
            notes="Prefers Thursday mornings.",
        )
        self.property = Property.objects.create(
            customer=self.customer,
            address="42 Willow Lane",
            gate_code="9012",
            has_dog=True,
        )
        other_customer = Customer.objects.create(business=self.other_business, name="Other")
        Property.objects.create(customer=other_customer, address="999 Away")
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "clients@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_clients_list_returns_business_clients_and_billing_context(self):
        response = self.client.get(reverse("mobile_api:clients"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["clients"][0]["name"], "Willow Creek")
        self.assertEqual(payload["clients"][0]["primary_address"], "42 Willow Lane")
        self.assertEqual(payload["clients"][0]["billing"]["invoice_frequency"], "monthly")
        self.assertTrue(payload["clients"][0]["billing"]["has_card_on_file"])
        self.assertEqual(payload["clients"][0]["properties"][0]["gate_code"], "9012")

    def test_client_detail_returns_full_profile(self):
        response = self.client.get(
            reverse("mobile_api:client_detail", args=[self.customer.id]),
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["client"]["notes"], "Prefers Thursday mornings.")

    def test_create_client_creates_property_for_native_inline_flow(self):
        response = self.client.post(
            reverse("mobile_api:clients"),
            data={
                "name": "Native New Client",
                "email": "nativeclient@example.com",
                "phone": "555-2020",
                "address": "77 Native Court",
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        created = Customer.objects.get(name="Native New Client")
        self.assertEqual(created.business, self.business)
        self.assertEqual(created.properties.first().address, "77 Native Court")
        self.assertEqual(response.json()["client"]["primary_address"], "77 Native Court")


class MobileCalendarTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Calendar")
        self.other_business = Business.objects.create(name="Other Calendar")
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="calendarowner",
            email="calendar@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.customer = Customer.objects.create(business=self.business, name="Calendar Client")
        self.property = Property.objects.create(customer=self.customer, address="88 Calendar Ave")
        self.today = date(2026, 5, 8)
        self.job = Job.objects.create(
            property=self.property,
            scheduled_date=self.today,
            scheduled_time=time(8, 30),
            status="scheduled",
        )
        self.multi_day = Job.objects.create(
            property=self.property,
            scheduled_date=self.today - timedelta(days=1),
            scheduled_end_date=self.today + timedelta(days=1),
            status="scheduled",
        )
        other_customer = Customer.objects.create(business=self.other_business, name="Other")
        other_property = Property.objects.create(customer=other_customer, address="999 Away")
        Job.objects.create(property=other_property, scheduled_date=self.today, status="scheduled")
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "calendar@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_calendar_returns_day_jobs_and_multi_day_overlap(self):
        response = self.client.get(
            reverse("mobile_api:calendar"),
            {"date": self.today.isoformat(), "view": "day"},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["range"]["start"], "2026-05-08")
        self.assertEqual(payload["range"]["end"], "2026-05-08")
        self.assertEqual(payload["summary"]["total"], 2)
        self.assertEqual({job["id"] for job in payload["jobs"]}, {self.job.id, self.multi_day.id})

    def test_calendar_week_view_expands_range(self):
        response = self.client.get(
            reverse("mobile_api:calendar"),
            {"date": self.today.isoformat(), "view": "week"},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["range"]["start"], "2026-05-04")
        self.assertEqual(response.json()["range"]["end"], "2026-05-10")

    def test_create_job_from_native_updates_shared_calendar_data(self):
        service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mulch",
            default_rate=Decimal("250.00"),
            default_unit="yard",
        )

        response = self.client.post(
            reverse("mobile_api:jobs"),
            data={
                "property_id": self.property.id,
                "scheduled_date": "2026-05-09",
                "scheduled_time": "10:15",
                "notes": "Native-created job.",
                "service_items": [
                    {
                        "service_id": service.id,
                        "description": "Mulch install",
                        "detail_description": "Freshen front beds.",
                        "quantity": "3",
                        "unit": "yard",
                        "unit_price": "250.00",
                    }
                ],
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        job = Job.objects.get(id=response.json()["job"]["id"])
        self.assertEqual(job.property, self.property)
        self.assertEqual(job.scheduled_date.isoformat(), "2026-05-09")
        self.assertEqual(job.service_items.first().detail_description, "Freshen front beds.")

    def test_update_job_from_native_changes_schedule_and_notes(self):
        response = self.client.patch(
            reverse("mobile_api:job_detail", args=[self.job.id]),
            data={
                "scheduled_date": "2026-05-10",
                "scheduled_end_date": "2026-05-12",
                "scheduled_time": "13:45",
                "scheduled_end_time": "16:15",
                "notes": "Moved from native app.",
                "status": "in_progress",
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.scheduled_date.isoformat(), "2026-05-10")
        self.assertEqual(self.job.scheduled_end_date.isoformat(), "2026-05-12")
        self.assertEqual(self.job.scheduled_time.strftime("%H:%M"), "13:45")
        self.assertEqual(self.job.scheduled_end_time.strftime("%H:%M"), "16:15")
        self.assertEqual(self.job.status, "in_progress")
        self.assertEqual(self.job.notes, "Moved from native app.")

    def test_job_options_returns_properties_services_and_crews(self):
        service = ServiceTemplate.objects.create(business=self.business, name="Edging", default_rate=Decimal("45.00"))
        crew = Crew.objects.create(business=self.business, name="Crew Native")

        response = self.client.get(reverse("mobile_api:job_options"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(self.property.id, [item["id"] for item in payload["properties"]])
        self.assertIn(service.id, [item["id"] for item in payload["services"]])
        self.assertIn(crew.id, [item["id"] for item in payload["crews"]])


class MobileMoneyTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Money")
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="moneyowner",
            email="money@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.customer = Customer.objects.create(business=self.business, name="Money Client")
        self.property = Property.objects.create(customer=self.customer, address="90 Money Ave")
        self.invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            total=Decimal("180.00"),
            due_date=date(2026, 5, 1),
        )
        self.estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            property=self.property,
            title="Landscape Refresh",
            status="sent",
            accepted_total=Decimal("950.00"),
        )
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "money@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_money_returns_invoice_and_estimate_queue(self):
        response = self.client.get(reverse("mobile_api:money"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["outstanding"], "180.00")
        self.assertEqual(payload["summary"]["open_estimates"], 1)
        self.assertEqual(payload["invoices"][0]["id"], self.invoice.id)
        self.assertEqual(payload["estimates"][0]["title"], "Landscape Refresh")

    def test_invoice_detail_returns_line_items_for_native_review(self):
        InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="April mowing",
            detail_description="Weekly maintenance visits",
            quantity=2,
            unit_price=Decimal("90.00"),
        )

        response = self.client.get(reverse("mobile_api:invoice_detail", args=[self.invoice.id]), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["invoice"]["id"], self.invoice.id)
        self.assertEqual(payload["line_items"][0]["description"], "April mowing")
        self.assertEqual(payload["line_items"][0]["line_total"], "180.00")

    def test_estimate_detail_returns_deposit_and_line_items_for_native_review(self):
        self.estimate.deposit_required = True
        self.estimate.deposit_type = "percent"
        self.estimate.deposit_amount = Decimal("25.00")
        self.estimate.save(update_fields=["deposit_required", "deposit_type", "deposit_amount"])
        EstimateLineItem.objects.create(
            estimate=self.estimate,
            description="Landscape bed cleanup",
            detail_description="Remove debris and reset bed edges",
            quantity=Decimal("1.00"),
            unit="project",
            unit_price=Decimal("950.00"),
        )

        response = self.client.get(reverse("mobile_api:estimate_detail", args=[self.estimate.id]), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["estimate"]["title"], "Landscape Refresh")
        self.assertEqual(payload["deposit"]["type"], "percent")
        self.assertEqual(payload["deposit"]["amount_due"], "237.50")
        self.assertEqual(payload["line_items"][0]["description"], "Landscape bed cleanup")

    def test_create_invoice_from_native_with_line_item(self):
        response = self.client.post(
            reverse("mobile_api:invoices"),
            data={
                "customer_id": self.customer.id,
                "due_date": "2026-05-30",
                "enable_card_payment": False,
                "line_items": [
                    {
                        "description": "May mowing",
                        "detail_description": "Weekly service",
                        "quantity": "2",
                        "unit_price": "85.00",
                    }
                ],
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        invoice = Invoice.objects.get(id=response.json()["invoice"]["id"])
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.total, Decimal("170.00"))
        self.assertFalse(invoice.enable_card_payment)

    def test_create_estimate_from_native_with_deposit(self):
        response = self.client.post(
            reverse("mobile_api:estimates"),
            data={
                "customer_id": self.customer.id,
                "property_id": self.property.id,
                "title": "Native Patio Quote",
                "notes": "Created from iPhone.",
                "deposit_required": True,
                "deposit_type": "fixed",
                "deposit_amount": "150.00",
                "line_items": [
                    {
                        "description": "Patio prep",
                        "detail_description": "Excavation and base prep",
                        "quantity": "1",
                        "unit": "project",
                        "unit_price": "900.00",
                    }
                ],
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        estimate = Estimate.objects.get(id=response.json()["estimate"]["id"])
        self.assertEqual(estimate.title, "Native Patio Quote")
        self.assertTrue(estimate.deposit_required)
        self.assertEqual(estimate.total(), Decimal("900.00"))

    def test_upload_estimate_photo_from_native(self):
        photo = SimpleUploadedFile(
            "before.jpg",
            b"fake-image",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("mobile_api:estimate_photos", args=[self.estimate.id]),
            data={"image": photo, "caption": "Front bed before cleanup."},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["photo_count"], 1)
        estimate_image = EstimateImage.objects.get(estimate=self.estimate)
        self.assertEqual(estimate_image.caption, "Front bed before cleanup.")

    def test_upload_receipt_from_native_links_to_job(self):
        job = Job.objects.create(
            property=self.property,
            status="scheduled",
            scheduled_date=date(2026, 5, 6),
        )
        photo = SimpleUploadedFile(
            "receipt.jpg",
            b"fake-image",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("mobile_api:receipts"),
            data={
                "file": photo,
                "job_id": job.id,
                "receipt_date": "2026-05-06",
                "amount": "42.18",
                "vendor": "Landscape Supply",
                "description": "Mulch bags",
                "category": "materials",
            },
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        receipt = Receipt.objects.get(id=response.json()["receipt"]["id"])
        self.assertEqual(receipt.job, job)
        self.assertEqual(receipt.amount, Decimal("42.18"))
        self.assertEqual(receipt.category, "materials")

    def test_send_invoice_from_native_approves_draft(self):
        draft = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            total=Decimal("25.00"),
        )

        response = self.client.post(
            reverse("mobile_api:invoice_action", args=[draft.id]),
            data={"action": "send"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "sent")
        self.assertTrue(draft.payment_token)

    def test_monthly_invoice_queue_returns_drafts_for_native_batch_review(self):
        monthly = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            total=Decimal("240.00"),
        )

        response = self.client.get(reverse("mobile_api:monthly_invoices"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["draft_count"], 1)
        self.assertEqual(payload["summary"]["draft_total"], "240.00")
        self.assertEqual(payload["invoices"][0]["id"], monthly.id)
        self.assertTrue(payload["invoices"][0]["is_monthly"])

    def test_monthly_invoice_batch_send_from_native_approves_selected_drafts(self):
        monthly = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            total=Decimal("240.00"),
        )
        InvoiceLineItem.objects.create(
            invoice=monthly,
            description="May mowing",
            quantity=1,
            unit_price=Decimal("240.00"),
        )

        response = self.client.post(
            reverse("mobile_api:monthly_invoices"),
            data={"action": "send_selected", "invoice_ids": [monthly.id]},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        monthly.refresh_from_db()
        self.assertEqual(monthly.status, "sent")
        self.assertEqual(response.json()["result"]["sent"], 1)

    def test_mark_invoice_line_item_paid_from_native_updates_invoice_payment_state(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
        )
        line_item = InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Mowing",
            quantity=1,
            unit_price=Decimal("85.00"),
        )

        response = self.client.post(
            reverse("mobile_api:invoice_line_item_action", args=[invoice.id, line_item.id]),
            data={"action": "paid", "payment_method": "card"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        line_item.refresh_from_db()
        invoice.refresh_from_db()
        self.assertTrue(line_item.is_paid)
        self.assertEqual(line_item.payment_method, "card")
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(response.json()["summary"]["paid_items"], 1)


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
        self.assertEqual(payload["changes"]["clients"], [])
        self.assertEqual(payload["changes"]["jobs"], [])
        self.assertEqual(payload["changes"]["invoices"], [])
        self.assertEqual(payload["changes"]["estimates"], [])
        self.assertIn("cursor", payload)
        self.assertIn("server_time", payload)

    def test_sync_pull_returns_business_snapshot_for_native_cache(self):
        customer = Customer.objects.create(business=self.business, name="Pull Client")
        property_obj = Property.objects.create(customer=customer, address="300 Pull Lane")
        job = Job.objects.create(property=property_obj, scheduled_date=date(2026, 5, 21), notes="Pull job")
        invoice = Invoice.objects.create(business=self.business, customer=customer, status="draft", total=Decimal("25.00"))
        estimate = Estimate.objects.create(business=self.business, customer=customer, title="Pull Estimate", status="draft")

        response = self.client.get(reverse("mobile_api:sync_pull"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        changes = response.json()["changes"]
        self.assertEqual(changes["clients"][0]["id"], customer.id)
        self.assertEqual(changes["jobs"][0]["id"], job.id)
        self.assertEqual(changes["invoices"][0]["id"], invoice.id)
        self.assertEqual(changes["estimates"][0]["id"], estimate.id)

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

    def test_sync_push_creates_client_for_offline_native_mutation(self):
        response = self.client.post(
            reverse("mobile_api:sync_push"),
            data={
                "mutations": [
                    {
                        "local_id": "client-local-1",
                        "entity_type": "client",
                        "operation": "create",
                        "payload": {
                            "name": "Offline Client",
                            "email": "offline@example.com",
                            "phone": "555-0199",
                            "address": "101 Offline Way",
                            "notes": "Created while offline.",
                        },
                    }
                ]
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rejected"], [])
        self.assertEqual(payload["accepted"][0]["local_id"], "client-local-1")
        customer = Customer.objects.get(name="Offline Client")
        self.assertEqual(customer.business, self.business)
        self.assertEqual(customer.properties.first().address, "101 Offline Way")

    def test_sync_push_creates_job_for_offline_native_mutation(self):
        customer = Customer.objects.create(business=self.business, name="Sync Job Client")
        property_obj = Property.objects.create(customer=customer, address="222 Sync Lane")

        response = self.client.post(
            reverse("mobile_api:sync_push"),
            data={
                "mutations": [
                    {
                        "local_id": "job-local-1",
                        "entity_type": "job",
                        "operation": "create",
                        "payload": {
                            "property_id": property_obj.id,
                            "scheduled_date": "2026-05-20",
                            "scheduled_time": "08:15",
                            "notes": "Queued job.",
                        },
                    }
                ]
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rejected"], [])
        created_job = Job.objects.get(id=payload["accepted"][0]["server_id"])
        self.assertEqual(created_job.property, property_obj)
        self.assertEqual(created_job.scheduled_date, date(2026, 5, 20))

    def test_sync_push_creates_invoice_for_offline_native_mutation(self):
        customer = Customer.objects.create(business=self.business, name="Sync Invoice Client")

        response = self.client.post(
            reverse("mobile_api:sync_push"),
            data={
                "mutations": [
                    {
                        "local_id": "invoice-local-1",
                        "entity_type": "invoice",
                        "operation": "create",
                        "payload": {
                            "customer_id": customer.id,
                            "due_date": "2026-05-31",
                            "enable_card_payment": False,
                            "line_items": [
                                {
                                    "description": "Offline mowing",
                                    "detail_description": "Front and back lawn.",
                                    "quantity": "2",
                                    "unit_price": "45.00",
                                }
                            ],
                        },
                    }
                ]
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rejected"], [])
        invoice = Invoice.objects.get(id=payload["accepted"][0]["server_id"])
        self.assertEqual(invoice.customer, customer)
        self.assertEqual(invoice.total, Decimal("90.00"))
        self.assertFalse(invoice.enable_card_payment)

    def test_sync_push_creates_estimate_for_offline_native_mutation(self):
        customer = Customer.objects.create(business=self.business, name="Sync Estimate Client")

        response = self.client.post(
            reverse("mobile_api:sync_push"),
            data={
                "mutations": [
                    {
                        "local_id": "estimate-local-1",
                        "entity_type": "estimate",
                        "operation": "create",
                        "payload": {
                            "customer_id": customer.id,
                            "title": "Offline landscape quote",
                            "notes": "Created from the native app.",
                            "valid_until": "2026-06-15",
                            "deposit_required": True,
                            "deposit_type": "fixed",
                            "deposit_amount": "250.00",
                            "line_items": [
                                {
                                    "description": "Mulch install",
                                    "detail_description": "Premium dark mulch.",
                                    "quantity": "10",
                                    "unit": "yard",
                                    "unit_price": "80.00",
                                }
                            ],
                        },
                    }
                ]
            },
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rejected"], [])
        estimate = Estimate.objects.get(id=payload["accepted"][0]["server_id"])
        self.assertEqual(estimate.customer, customer)
        self.assertEqual(estimate.title, "Offline landscape quote")
        self.assertEqual(estimate.total(), Decimal("800.00"))
        self.assertTrue(estimate.deposit_required)

    def test_sync_requires_authentication(self):
        response = self.client.get(reverse("mobile_api:sync_pull"))

        self.assertEqual(response.status_code, 401)


class MobileTimeClockTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Time")
        User = get_user_model()
        self.crew_user = User.objects.create_user(
            username="timecrew",
            email="timecrew@example.com",
            password="testpass123",
            business=self.business,
            role="crew",
        )
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "timecrew@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_time_clock_status_returns_active_entry_and_today_total(self):
        now = timezone.now()
        first = TimeEntry.objects.create(
            user=self.crew_user,
            clock_in=now - timezone.timedelta(minutes=50),
            clock_out=now - timezone.timedelta(minutes=20),
        )
        active = TimeEntry.objects.create(
            user=self.crew_user,
            clock_in=now - timezone.timedelta(minutes=10),
            clock_in_latitude=Decimal("39.7684000"),
            clock_in_longitude=Decimal("-86.1581000"),
        )

        response = self.client.get(reverse("mobile_api:time_clock_status"), **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_clocked_in"])
        self.assertEqual(payload["active_entry"]["id"], active.id)
        self.assertGreaterEqual(payload["today_minutes"], first.duration_minutes)
        self.assertIn("today_display", payload)

    def test_clock_in_creates_active_time_entry_with_location(self):
        response = self.client.post(
            reverse("mobile_api:time_clock_in"),
            data={"latitude": "39.7684", "longitude": "-86.1581"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        entry = TimeEntry.objects.get(user=self.crew_user, clock_out__isnull=True)
        self.assertEqual(str(entry.clock_in_latitude), "39.7684000")
        self.assertEqual(str(entry.clock_in_longitude), "-86.1581000")
        self.assertTrue(response.json()["is_clocked_in"])
        self.assertEqual(response.json()["active_entry"]["id"], entry.id)

    def test_clock_in_returns_existing_active_entry_instead_of_duplicate(self):
        active = TimeEntry.objects.create(user=self.crew_user, clock_in=timezone.now())

        response = self.client.post(
            reverse("mobile_api:time_clock_in"),
            data={"latitude": "39.7684", "longitude": "-86.1581"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TimeEntry.objects.filter(user=self.crew_user, clock_out__isnull=True).count(), 1)
        self.assertEqual(response.json()["active_entry"]["id"], active.id)

    def test_clock_out_closes_active_entry_with_location(self):
        entry = TimeEntry.objects.create(user=self.crew_user, clock_in=timezone.now() - timezone.timedelta(hours=1))

        response = self.client.post(
            reverse("mobile_api:time_clock_out"),
            data={"latitude": "39.7700", "longitude": "-86.1600"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertIsNotNone(entry.clock_out)
        self.assertEqual(str(entry.clock_out_latitude), "39.7700000")
        self.assertEqual(str(entry.clock_out_longitude), "-86.1600000")
        self.assertFalse(response.json()["is_clocked_in"])

    def test_clock_out_requires_active_entry(self):
        response = self.client.post(
            reverse("mobile_api:time_clock_out"),
            data={},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "No active clock-in found.")

    def test_location_ping_records_against_active_time_entry(self):
        entry = TimeEntry.objects.create(user=self.crew_user, clock_in=timezone.now())

        response = self.client.post(
            reverse("mobile_api:time_clock_location"),
            data={"latitude": "39.7684", "longitude": "-86.1581", "accuracy": "14.2"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        ping = TimeEntryLocationPing.objects.get(time_entry=entry)
        self.assertEqual(ping.user, self.crew_user)
        self.assertEqual(str(ping.latitude), "39.7684000")
        self.assertEqual(str(ping.longitude), "-86.1581000")
        self.assertEqual(str(ping.accuracy_meters), "14.20")
        self.assertEqual(response.json()["location"]["id"], ping.id)

    def test_location_ping_requires_active_time_entry(self):
        response = self.client.post(
            reverse("mobile_api:time_clock_location"),
            data={"latitude": "39.7684", "longitude": "-86.1581"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Clock in before sharing location.")

    def test_time_clock_requires_authentication(self):
        response = self.client.get(reverse("mobile_api:time_clock_status"))

        self.assertEqual(response.status_code, 401)


class MobileTodayTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Today")
        self.other_business = Business.objects.create(name="Other Company")
        User = get_user_model()
        self.crew_user = User.objects.create_user(
            username="todaycrew",
            email="todaycrew@example.com",
            password="testpass123",
            business=self.business,
            role="crew",
        )
        self.other_crew = User.objects.create_user(
            username="othercrew",
            email="othercrew@example.com",
            password="testpass123",
            business=self.other_business,
            role="crew",
        )
        self.owner = User.objects.create_user(
            username="todayowner",
            email="todayowner@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.customer = Customer.objects.create(business=self.business, name="Maple Ridge")
        self.property = Property.objects.create(
            customer=self.customer,
            address="123 Test Lawn Ave",
            gate_code="2480",
            has_dog=True,
            notes="Park near the left gate.",
        )
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mowing",
            default_rate=Decimal("65.00"),
        )
        self.today = date(2026, 5, 4)
        self.job = Job.objects.create(
            property=self.property,
            scheduled_date=self.today,
            scheduled_time=time(8, 30),
            status="scheduled",
            assigned_to=self.crew_user,
            route_order=2,
        )
        JobServiceItem.objects.create(
            job=self.job,
            service=self.service,
            quantity=Decimal("1.00"),
            unit="visit",
            unit_price=Decimal("65.00"),
            detail_description="Trim fence line and blow clippings.",
        )
        PropertyNote.objects.create(
            property=self.property,
            author=self.owner,
            text="Crew can use side gate.",
            visibility=PropertyNote.VISIBILITY_CREW,
        )
        PropertyNote.objects.create(
            property=self.property,
            author=self.owner,
            text="Billing dispute note.",
            visibility=PropertyNote.VISIBILITY_INTERNAL,
        )
        other_customer = Customer.objects.create(business=self.other_business, name="Other Customer")
        other_property = Property.objects.create(customer=other_customer, address="999 Elsewhere")
        Job.objects.create(
            property=other_property,
            scheduled_date=self.today,
            status="scheduled",
            assigned_to=self.other_crew,
        )
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "todaycrew@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_today_returns_assigned_jobs_with_field_context(self):
        response = self.client.get(
            reverse("mobile_api:today"),
            {"date": self.today.isoformat()},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["date"], "2026-05-04")
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["summary"]["remaining"], 1)
        self.assertEqual(payload["jobs"][0]["id"], self.job.id)
        self.assertEqual(payload["jobs"][0]["customer"]["name"], "Maple Ridge")
        self.assertEqual(payload["jobs"][0]["property"]["address"], "123 Test Lawn Ave")
        self.assertEqual(payload["jobs"][0]["service_items"][0]["name"], "Mowing")
        self.assertEqual(payload["jobs"][0]["service_items"][0]["detail_description"], "Trim fence line and blow clippings.")
        alert_text = " ".join(alert["text"] for alert in payload["jobs"][0]["alerts"])
        self.assertIn("2480", alert_text)
        self.assertIn("Crew can use side gate.", alert_text)
        self.assertNotIn("Billing dispute note.", alert_text)

    def test_today_includes_crew_membership_and_multi_day_jobs(self):
        crew = Crew.objects.create(business=self.business, name="Crew A")
        crew.members.add(self.crew_user)
        multi_day = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 5, 3),
            scheduled_end_date=date(2026, 5, 5),
            status="scheduled",
            assigned_crew=crew,
            route_order=1,
        )

        response = self.client.get(
            reverse("mobile_api:today"),
            {"date": self.today.isoformat()},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        job_ids = [job["id"] for job in response.json()["jobs"]]
        self.assertEqual(job_ids, [multi_day.id, self.job.id])

    def test_today_requires_authentication(self):
        response = self.client.get(reverse("mobile_api:today"))

        self.assertEqual(response.status_code, 401)


@override_settings(
    MEDIA_ROOT="/tmp/fieldlgx-mobile-api-test-media",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MobileJobDetailTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="QA Native Job Detail")
        self.other_business = Business.objects.create(name="Other Detail Company")
        User = get_user_model()
        self.crew_user = User.objects.create_user(
            username="detailcrew",
            email="detailcrew@example.com",
            password="testpass123",
            business=self.business,
            role="crew",
        )
        self.owner = User.objects.create_user(
            username="detailowner",
            email="detailowner@example.com",
            password="testpass123",
            business=self.business,
            role="owner",
        )
        self.customer = Customer.objects.create(business=self.business, name="Oak Hollow")
        self.property = Property.objects.create(
            customer=self.customer,
            address="400 Crew Lane",
            gate_code="6124",
            notes="Use the east entrance.",
        )
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Cleanup",
            default_rate=Decimal("125.00"),
        )
        self.job = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 5, 5),
            scheduled_time=time(9, 0),
            status="scheduled",
            assigned_to=self.crew_user,
        )
        JobServiceItem.objects.create(
            job=self.job,
            service=self.service,
            quantity=Decimal("1.00"),
            unit="job",
            unit_price=Decimal("125.00"),
            detail_description="Haul limbs by garage.",
        )
        JobNote.objects.create(
            job=self.job,
            author=self.owner,
            text="Customer asked for a text before arrival.",
            visibility=JobNote.VISIBILITY_CREW,
        )
        JobNote.objects.create(
            job=self.job,
            author=self.owner,
            text="Owner-only pricing note.",
            visibility=JobNote.VISIBILITY_INTERNAL,
        )
        self.login = self.client.post(
            reverse("mobile_api:login"),
            data={"email": "detailcrew@example.com", "password": "testpass123"},
            content_type="application/json",
        ).json()

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.login['access_token']}"}

    def test_job_detail_returns_field_context_and_actions(self):
        response = self.client.get(
            reverse("mobile_api:job_detail", args=[self.job.id]),
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["job"]["id"], self.job.id)
        self.assertEqual(payload["job"]["customer"]["name"], "Oak Hollow")
        self.assertEqual(payload["job"]["service_items"][0]["detail_description"], "Haul limbs by garage.")
        self.assertTrue(payload["actions"]["can_start"])
        self.assertFalse(payload["actions"]["can_complete"])
        note_text = " ".join(note["text"] for note in payload["job_notes"])
        self.assertIn("Customer asked for a text before arrival.", note_text)
        self.assertNotIn("Owner-only pricing note.", note_text)

    def test_crew_cannot_open_unassigned_job(self):
        other_job = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 5, 5),
            status="scheduled",
        )

        response = self.client.get(
            reverse("mobile_api:job_detail", args=[other_job.id]),
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 403)

    def test_start_job_marks_in_progress_and_records_location(self):
        response = self.client.post(
            reverse("mobile_api:job_start", args=[self.job.id]),
            data={"latitude": "39.7684", "longitude": "-86.1581"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "in_progress")
        self.assertIsNotNone(self.job.started_at)
        self.assertEqual(str(self.job.technician_latitude), "39.7684000")
        self.assertTrue(response.json()["actions"]["can_complete"])

    def test_complete_job_marks_completed_without_touching_completed_history(self):
        self.job.status = "in_progress"
        self.job.started_at = timezone.now()
        self.job.save(update_fields=["status", "started_at"])

        response = self.client.post(
            reverse("mobile_api:job_complete", args=[self.job.id]),
            data={"latitude": "39.7684", "longitude": "-86.1581"},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "completed")
        self.assertEqual(self.job.completed_by, self.crew_user)
        self.assertIsNotNone(self.job.completed_at)

    def test_complete_job_requires_photo_when_business_requires_it(self):
        self.business.require_completion_photo = True
        self.business.save(update_fields=["require_completion_photo"])
        self.job.status = "in_progress"
        self.job.started_at = timezone.now()
        self.job.save(update_fields=["status", "started_at"])

        response = self.client.post(
            reverse("mobile_api:job_complete", args=[self.job.id]),
            data={},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Completion photo required.")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "in_progress")

        JobCompletionPhoto.objects.create(job=self.job, uploaded_by=self.crew_user)

        completed = self.client.post(
            reverse("mobile_api:job_complete", args=[self.job.id]),
            data={},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(completed.status_code, 200)

    def test_skip_job_requires_reason_and_records_skip(self):
        missing_reason = self.client.post(
            reverse("mobile_api:job_skip", args=[self.job.id]),
            data={},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(missing_reason.status_code, 400)

        response = self.client.post(
            reverse("mobile_api:job_skip", args=[self.job.id]),
            data={"reason": "Customer requested next week."},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "skipped")
        self.assertEqual(self.job.skip_reason, "Customer requested next week.")
        self.assertIsNotNone(self.job.skipped_at)

    def test_upload_completion_photo_attaches_proof_and_enables_completion(self):
        self.business.require_completion_photo = True
        self.business.save(update_fields=["require_completion_photo"])
        self.job.status = "in_progress"
        self.job.started_at = timezone.now()
        self.job.save(update_fields=["status", "started_at"])
        photo = SimpleUploadedFile(
            "completion.jpg",
            b"fake-jpeg-data",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("mobile_api:job_completion_photo", args=[self.job.id]),
            data={"image": photo},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(JobCompletionPhoto.objects.filter(job=self.job, uploaded_by=self.crew_user).count(), 1)
        payload = response.json()
        self.assertTrue(payload["actions"]["has_completion_photo"])
        self.assertTrue(payload["actions"]["can_complete"])

    def test_upload_completion_photo_rejects_non_images(self):
        document = SimpleUploadedFile(
            "notes.txt",
            b"not-image",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("mobile_api:job_completion_photo", args=[self.job.id]),
            data={"image": document},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid file type.")

    def test_upload_site_photo_attaches_photo_to_job(self):
        photo = SimpleUploadedFile(
            "before.jpg",
            b"fake-jpeg-data",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("mobile_api:job_photos", args=[self.job.id]),
            data={"image": photo, "category": "before", "caption": "Before cleanup."},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        site_photo = JobPhoto.objects.get(job=self.job, uploaded_by=self.crew_user)
        self.assertEqual(site_photo.category, "before")
        self.assertEqual(site_photo.caption, "Before cleanup.")
        self.assertEqual(response.json()["job"]["photo_count"], 1)

    def test_upload_site_photo_rejects_non_images(self):
        document = SimpleUploadedFile(
            "notes.txt",
            b"not-image",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("mobile_api:job_photos", args=[self.job.id]),
            data={"image": document, "category": "during"},
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid file type.")

    def test_crew_can_add_job_note_from_the_field(self):
        response = self.client.post(
            reverse("mobile_api:job_notes", args=[self.job.id]),
            data={"text": "Back gate was locked.", "visibility": JobNote.VISIBILITY_INTERNAL},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        note = JobNote.objects.get(job=self.job, text="Back gate was locked.")
        self.assertEqual(note.author, self.crew_user)
        self.assertEqual(note.visibility, JobNote.VISIBILITY_CREW)
        note_text = " ".join(note["text"] for note in response.json()["job_notes"])
        self.assertIn("Back gate was locked.", note_text)

    def test_add_job_note_requires_text(self):
        response = self.client.post(
            reverse("mobile_api:job_notes", args=[self.job.id]),
            data={"text": "   "},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Note text is required.")

    def test_crew_can_report_job_issue_from_the_field(self):
        response = self.client.post(
            reverse("mobile_api:job_issues", args=[self.job.id]),
            data={"issue_type": "access", "description": "Back gate is locked."},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        issue = JobIssue.objects.get(job=self.job, description="Back gate is locked.")
        self.assertEqual(issue.reported_by, self.crew_user)
        self.assertEqual(issue.issue_type, "access")
        self.assertEqual(issue.status, "open")
        payload = response.json()
        self.assertEqual(payload["job_issues"][0]["description"], "Back gate is locked.")
        self.assertEqual(payload["job_issues"][0]["status"], "open")

    def test_report_job_issue_requires_description(self):
        response = self.client.post(
            reverse("mobile_api:job_issues", args=[self.job.id]),
            data={"issue_type": "damage", "description": ""},
            content_type="application/json",
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Issue description is required.")

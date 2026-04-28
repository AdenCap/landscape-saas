from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from datetime import date, time
from decimal import Decimal

from businesses.models import Business
from customers.models import Customer, Property
from jobs.models import Crew, Job, JobCompletionPhoto, JobIssue, JobNote, JobServiceItem, PropertyNote
from pricing.models import ServiceTemplate


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

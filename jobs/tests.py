import json
from decimal import Decimal
from datetime import date, time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from billing.models import Invoice
from businesses.models import Business
from customers.models import Customer, Property
from jobs.models import Crew, Job, JobNote, JobServiceItem, PropertyNote, RecurringJob
from pricing.models import ServiceTemplate


class CalendarRecurringRescheduleTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Home",
        )
        self.property = Property.objects.create(
            customer=self.customer,
            address="123 Lawn Ave",
        )
        self.recurring_job = RecurringJob.objects.create(
            property=self.property,
            frequency="weekly",
            start_date=date(2026, 5, 4),
        )
        self.client.force_login(self.owner)

    def _create_job(self, scheduled_date, start_time=time(8, 0), end_time=time(9, 0)):
        return Job.objects.create(
            property=self.property,
            recurring_job=self.recurring_job,
            scheduled_date=scheduled_date,
            scheduled_time=start_time,
            scheduled_end_time=end_time,
            status="scheduled",
        )

    def test_reschedule_recurring_job_to_future_updates_future_dates_and_times(self):
        selected_job = self._create_job(date(2026, 5, 4))
        next_job = self._create_job(date(2026, 5, 11))
        later_job = self._create_job(date(2026, 5, 18))

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[selected_job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-06T10:30:00",
                    "scheduled_end": "2026-05-06T12:00:00",
                    "apply_to_future": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        next_job.refresh_from_db()
        later_job.refresh_from_db()
        self.recurring_job.refresh_from_db()

        self.assertEqual(selected_job.scheduled_date, date(2026, 5, 6))
        self.assertEqual(selected_job.scheduled_time, time(10, 30))
        self.assertEqual(selected_job.scheduled_end_time, time(12, 0))
        self.assertEqual(next_job.scheduled_date, date(2026, 5, 13))
        self.assertEqual(later_job.scheduled_date, date(2026, 5, 20))
        self.assertEqual(next_job.scheduled_time, time(10, 30))
        self.assertEqual(later_job.scheduled_time, time(10, 30))
        self.assertEqual(next_job.scheduled_end_time, time(12, 0))
        self.assertEqual(later_job.scheduled_end_time, time(12, 0))
        self.assertEqual(self.recurring_job.start_date, date(2026, 5, 6))

    def test_reschedule_recurring_job_this_only_leaves_future_jobs_unchanged(self):
        selected_job = self._create_job(date(2026, 5, 4))
        next_job = self._create_job(date(2026, 5, 11))

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[selected_job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-06T10:30:00",
                    "scheduled_end": "2026-05-06T12:00:00",
                    "apply_to_future": False,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        next_job.refresh_from_db()
        self.recurring_job.refresh_from_db()

        self.assertEqual(selected_job.scheduled_date, date(2026, 5, 6))
        self.assertEqual(selected_job.scheduled_time, time(10, 30))
        self.assertEqual(selected_job.scheduled_end_time, time(12, 0))
        self.assertEqual(next_job.scheduled_date, date(2026, 5, 11))
        self.assertEqual(next_job.scheduled_time, time(8, 0))
        self.assertEqual(next_job.scheduled_end_time, time(9, 0))
        self.assertEqual(self.recurring_job.start_date, date(2026, 5, 4))

    def test_reschedule_recurring_job_to_future_updates_times_when_date_does_not_change(self):
        selected_job = self._create_job(date(2026, 5, 4))
        next_job = self._create_job(date(2026, 5, 11))

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[selected_job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-04T10:30:00",
                    "scheduled_end": "2026-05-04T12:00:00",
                    "apply_to_future": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        next_job.refresh_from_db()
        self.recurring_job.refresh_from_db()

        self.assertEqual(selected_job.scheduled_date, date(2026, 5, 4))
        self.assertEqual(selected_job.scheduled_time, time(10, 30))
        self.assertEqual(selected_job.scheduled_end_time, time(12, 0))
        self.assertEqual(next_job.scheduled_date, date(2026, 5, 11))
        self.assertEqual(next_job.scheduled_time, time(10, 30))
        self.assertEqual(next_job.scheduled_end_time, time(12, 0))
        self.assertEqual(self.recurring_job.start_date, date(2026, 5, 4))

    def test_reschedule_timed_job_across_days_sets_scheduled_end_date(self):
        job = self._create_job(date(2026, 5, 4))

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-04T10:30:00",
                    "scheduled_end": "2026-05-05T12:00:00",
                    "scheduled_end_date": "2026-05-05",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()

        self.assertEqual(job.scheduled_date, date(2026, 5, 4))
        self.assertEqual(job.scheduled_end_date, date(2026, 5, 5))
        self.assertEqual(job.scheduled_time, time(10, 30))
        self.assertEqual(job.scheduled_end_time, time(12, 0))

    def test_reschedule_with_null_end_date_clears_multi_day_job(self):
        job = self._create_job(date(2026, 5, 4))
        job.scheduled_end_date = date(2026, 5, 6)
        job.save(update_fields=["scheduled_end_date"])

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-04T10:30:00",
                    "scheduled_end": "2026-05-04T12:00:00",
                    "scheduled_end_date": None,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()

        self.assertIsNone(job.scheduled_end_date)
        self.assertEqual(job.scheduled_time, time(10, 30))
        self.assertEqual(job.scheduled_end_time, time(12, 0))

    def test_reschedule_all_day_clears_times_so_job_renders_as_day_bar(self):
        job = self._create_job(date(2026, 5, 4))

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-04",
                    "scheduled_end_date": "2026-05-06",
                    "all_day": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()

        self.assertEqual(job.scheduled_date, date(2026, 5, 4))
        self.assertEqual(job.scheduled_end_date, date(2026, 5, 6))
        self.assertIsNone(job.scheduled_time)
        self.assertIsNone(job.scheduled_end_time)

    def test_resize_recurring_job_to_future_updates_future_end_dates(self):
        selected_job = self._create_job(date(2026, 5, 4), start_time=None, end_time=None)
        future_job = self._create_job(date(2026, 5, 11), start_time=None, end_time=None)

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[selected_job.id]),
            data=json.dumps(
                {
                    "scheduled_date": "2026-05-04",
                    "scheduled_end_date": "2026-05-06",
                    "all_day": True,
                    "apply_to_future": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        future_job.refresh_from_db()
        self.assertEqual(selected_job.scheduled_end_date, date(2026, 5, 6))
        self.assertEqual(future_job.scheduled_end_date, date(2026, 5, 13))

    def test_add_note_to_job_scope_creates_one_time_job_note(self):
        job = self._create_job(date(2026, 5, 4))

        response = self.client.post(
            reverse("add_job_note", args=[job.id]),
            data=json.dumps({"text": "Trim by the mailbox today.", "scope": "job"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(JobNote.objects.filter(job=job).count(), 1)
        self.assertEqual(PropertyNote.objects.filter(property=self.property).count(), 0)
        self.recurring_job.refresh_from_db()
        self.assertEqual(self.recurring_job.notes, "")

    def test_add_note_to_property_scope_creates_permanent_property_note(self):
        job = self._create_job(date(2026, 5, 4))

        response = self.client.post(
            reverse("add_job_note", args=[job.id]),
            data=json.dumps({"text": "Gate code is 2481.", "scope": "property"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(JobNote.objects.filter(job=job).count(), 0)
        note = PropertyNote.objects.get(property=self.property)
        self.assertEqual(note.text, "Gate code is 2481.")
        self.assertEqual(note.visibility, PropertyNote.VISIBILITY_CREW)

    def test_internal_property_note_is_hidden_from_crew_notes_feed(self):
        job = self._create_job(date(2026, 5, 4))
        crew_user = User.objects.create_user(
            username="crew",
            password="password",
            role="crew",
            business=self.business,
        )
        job.assigned_to = crew_user
        job.save(update_fields=["assigned_to"])

        PropertyNote.objects.create(
            property=self.property,
            author=self.owner,
            text="Billing issue only owner should see.",
            visibility=PropertyNote.VISIBILITY_INTERNAL,
        )
        PropertyNote.objects.create(
            property=self.property,
            author=self.owner,
            text="Gate code is 2481.",
            visibility=PropertyNote.VISIBILITY_CREW,
        )

        self.client.force_login(crew_user)
        response = self.client.get(reverse("get_job_notes", args=[job.id]))

        self.assertEqual(response.status_code, 200)
        texts = [note["text"] for note in response.json()["notes"]]
        self.assertIn("Gate code is 2481.", texts)
        self.assertNotIn("Billing issue only owner should see.", texts)

    def test_add_note_to_recurring_scope_updates_series_and_future_jobs(self):
        selected_job = self._create_job(date(2026, 5, 4))
        future_job = self._create_job(date(2026, 5, 11))
        completed_future_job = self._create_job(date(2026, 5, 18))
        completed_future_job.status = "completed"
        completed_future_job.save(update_fields=["status"])

        response = self.client.post(
            reverse("add_job_note", args=[selected_job.id]),
            data=json.dumps({"text": "Always bag clippings by the pool.", "scope": "recurring"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.recurring_job.refresh_from_db()
        selected_job.refresh_from_db()
        future_job.refresh_from_db()
        completed_future_job.refresh_from_db()

        self.assertEqual(self.recurring_job.notes, "Always bag clippings by the pool.")
        self.assertEqual(selected_job.notes, "Always bag clippings by the pool.")
        self.assertEqual(future_job.notes, "Always bag clippings by the pool.")
        self.assertEqual(completed_future_job.notes, "")

    def test_update_recurring_job_crew_this_only_leaves_future_jobs_unchanged(self):
        old_crew = Crew.objects.create(business=self.business, name="Crew A")
        new_crew = Crew.objects.create(business=self.business, name="Crew B")
        self.recurring_job.assigned_crew = old_crew
        self.recurring_job.save(update_fields=["assigned_crew"])
        selected_job = self._create_job(date(2026, 5, 4))
        future_job = self._create_job(date(2026, 5, 11))
        selected_job.assigned_crew = old_crew
        selected_job.save(update_fields=["assigned_crew"])
        future_job.assigned_crew = old_crew
        future_job.save(update_fields=["assigned_crew"])

        response = self.client.post(
            reverse("calendar_job_update", args=[selected_job.id]),
            data=json.dumps({
                "assigned_crew_id": new_crew.id,
                "apply_assignment_to_future": False,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        future_job.refresh_from_db()
        self.recurring_job.refresh_from_db()
        self.assertEqual(selected_job.assigned_crew_id, new_crew.id)
        self.assertEqual(future_job.assigned_crew_id, old_crew.id)
        self.assertEqual(self.recurring_job.assigned_crew_id, old_crew.id)

    def test_update_recurring_job_crew_future_updates_series_and_future_jobs(self):
        old_crew = Crew.objects.create(business=self.business, name="Crew A")
        new_crew = Crew.objects.create(business=self.business, name="Crew B")
        self.recurring_job.assigned_crew = old_crew
        self.recurring_job.save(update_fields=["assigned_crew"])
        selected_job = self._create_job(date(2026, 5, 4))
        future_job = self._create_job(date(2026, 5, 11))
        completed_future_job = self._create_job(date(2026, 5, 18))
        for job in (selected_job, future_job, completed_future_job):
            job.assigned_crew = old_crew
            job.save(update_fields=["assigned_crew"])
        completed_future_job.status = "completed"
        completed_future_job.save(update_fields=["status"])

        response = self.client.post(
            reverse("calendar_job_update", args=[selected_job.id]),
            data=json.dumps({
                "assigned_crew_id": new_crew.id,
                "apply_assignment_to_future": True,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        future_job.refresh_from_db()
        completed_future_job.refresh_from_db()
        self.recurring_job.refresh_from_db()
        self.assertEqual(selected_job.assigned_crew_id, new_crew.id)
        self.assertEqual(future_job.assigned_crew_id, new_crew.id)
        self.assertEqual(completed_future_job.assigned_crew_id, old_crew.id)
        self.assertEqual(self.recurring_job.assigned_crew_id, new_crew.id)

    def test_update_recurring_job_employee_future_updates_series_and_future_jobs(self):
        old_crew = Crew.objects.create(business=self.business, name="Crew A")
        employee = User.objects.create_user(
            username="crew1",
            password="password",
            role="crew",
            business=self.business,
        )
        self.recurring_job.assigned_crew = old_crew
        self.recurring_job.save(update_fields=["assigned_crew"])
        selected_job = self._create_job(date(2026, 5, 4))
        future_job = self._create_job(date(2026, 5, 11))
        for job in (selected_job, future_job):
            job.assigned_crew = old_crew
            job.save(update_fields=["assigned_crew"])

        response = self.client.post(
            reverse("calendar_job_update", args=[selected_job.id]),
            data=json.dumps({
                "assigned_crew_id": None,
                "assigned_to_id": employee.id,
                "assigned_employee_ids": [employee.id],
                "apply_assignment_to_future": True,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        selected_job.refresh_from_db()
        future_job.refresh_from_db()
        self.recurring_job.refresh_from_db()
        self.assertIsNone(selected_job.assigned_crew_id)
        self.assertEqual(selected_job.assigned_to_id, employee.id)
        self.assertIsNone(future_job.assigned_crew_id)
        self.assertEqual(future_job.assigned_to_id, employee.id)
        self.assertEqual(list(future_job.assigned_employees.values_list("id", flat=True)), [employee.id])
        self.assertIsNone(self.recurring_job.assigned_crew_id)
        self.assertEqual(self.recurring_job.assigned_to_id, employee.id)


class MowingFrequencyUpdateTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="mowing-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Home",
        )
        self.property = Property.objects.create(
            customer=self.customer,
            address="123 Lawn Ave",
        )
        self.recurring_job = RecurringJob.objects.create(
            property=self.property,
            frequency="weekly",
            start_date=date(2026, 4, 7),
        )
        self.mowing_service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mowing",
            default_rate=Decimal("85.00"),
        )
        self.client.force_login(self.owner)

    def _mowing_job(self, scheduled_date, status="scheduled"):
        job = Job.objects.create(
            property=self.property,
            recurring_job=self.recurring_job,
            scheduled_date=scheduled_date,
            status=status,
        )
        JobServiceItem.objects.create(
            job=job,
            service=self.mowing_service,
            description="Mowing",
            quantity=1,
            unit="visit",
            unit_price=Decimal("85.00"),
        )
        return job

    def _change_frequency(self, frequency):
        return self.client.post(
            reverse("mowing_update_frequency"),
            data=json.dumps({
                "recurring_id": self.recurring_job.id,
                "frequency": frequency,
            }),
            content_type="application/json",
        )

    def _scheduled_dates(self):
        return list(
            Job.objects.filter(
                property=self.property,
                recurring_job=self.recurring_job,
                status="scheduled",
            ).order_by("scheduled_date").values_list("scheduled_date", flat=True)
        )

    def _seed_completed_and_future(self, completed_date, future_dates):
        completed_job = self._mowing_job(completed_date, status="completed")
        for future_date in future_dates:
            self._mowing_job(future_date)
        return completed_job

    def _assert_frequency_change(self, frequency, expected_dates, completed_job):
        response = self._change_frequency(frequency)

        self.assertEqual(response.status_code, 200)
        self.recurring_job.refresh_from_db()
        completed_job.refresh_from_db()
        self.assertEqual(self.recurring_job.frequency, frequency)
        self.assertEqual(completed_job.scheduled_date, date(2026, 4, 28))
        self.assertEqual(completed_job.status, "completed")
        self.assertEqual(self._scheduled_dates(), expected_dates)

    @patch("jobs.views._business_today")
    def test_weekly_to_biweekly_reschedules_from_last_completed_service(self, mock_today):
        mock_today.return_value = date(2026, 5, 1)
        completed_job = self._mowing_job(date(2026, 4, 28), status="completed")
        future_dates = [
            date(2026, 5, 5),
            date(2026, 5, 12),
            date(2026, 5, 19),
            date(2026, 5, 26),
        ]
        for future_date in future_dates:
            self._mowing_job(future_date)

        self._assert_frequency_change(
            "biweekly",
            [date(2026, 5, 12), date(2026, 5, 26)],
            completed_job,
        )

    @patch("jobs.views._business_today")
    def test_biweekly_to_weekly_reschedules_from_last_completed_service(self, mock_today):
        mock_today.return_value = date(2026, 5, 1)
        self.recurring_job.frequency = "biweekly"
        self.recurring_job.save(update_fields=["frequency"])
        completed_job = self._seed_completed_and_future(
            date(2026, 4, 28),
            [date(2026, 5, 12), date(2026, 5, 26), date(2026, 6, 9)],
        )

        self._assert_frequency_change(
            "weekly",
            [
                date(2026, 5, 5),
                date(2026, 5, 12),
                date(2026, 5, 19),
                date(2026, 5, 26),
                date(2026, 6, 2),
                date(2026, 6, 9),
            ],
            completed_job,
        )

    @patch("jobs.views._business_today")
    def test_weekly_to_ten_day_reschedules_from_last_completed_service(self, mock_today):
        mock_today.return_value = date(2026, 5, 1)
        completed_job = self._seed_completed_and_future(
            date(2026, 4, 28),
            [
                date(2026, 5, 5),
                date(2026, 5, 12),
                date(2026, 5, 19),
                date(2026, 5, 26),
                date(2026, 6, 2),
            ],
        )

        self._assert_frequency_change(
            "10day",
            [date(2026, 5, 8), date(2026, 5, 18), date(2026, 5, 28)],
            completed_job,
        )

    @patch("jobs.views._business_today")
    def test_biweekly_to_ten_day_reschedules_from_last_completed_service(self, mock_today):
        mock_today.return_value = date(2026, 5, 1)
        self.recurring_job.frequency = "biweekly"
        self.recurring_job.save(update_fields=["frequency"])
        completed_job = self._seed_completed_and_future(
            date(2026, 4, 28),
            [date(2026, 5, 12), date(2026, 5, 26), date(2026, 6, 9)],
        )

        self._assert_frequency_change(
            "10day",
            [date(2026, 5, 8), date(2026, 5, 18), date(2026, 5, 28), date(2026, 6, 7)],
            completed_job,
        )


class JobCompletionAutoChargeTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
            auto_invoice_send_behavior="send",
            stripe_connect_account_id="acct_test",
            stripe_connect_charges_enabled=True,
            client_card_payments_enabled=True,
            client_saved_cards_enabled=True,
        )
        self.owner = User.objects.create_user(
            username="auto-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Home",
            invoice_frequency="per_service",
            stripe_customer_id="cus_test",
            stripe_payment_method_id="pm_test",
            card_brand="visa",
            card_last4="4242",
            auto_charge_completed_jobs=True,
            auto_charge_monthly_invoices=False,
        )
        self.property = Property.objects.create(customer=self.customer, address="123 Lawn Ave")
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mowing",
            default_rate=Decimal("85.00"),
        )
        self.job = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 5, 4),
            status="scheduled",
        )
        JobServiceItem.objects.create(
            job=self.job,
            service=self.service,
            description="Mowing",
            quantity=Decimal("1.00"),
            unit_price=Decimal("85.00"),
        )
        self.client.force_login(self.owner)

    @patch("billing.services.stripe.PaymentIntent.create")
    def test_completed_per_service_job_charges_card_when_customer_allows_it(self, mock_create):
        mock_create.return_value.status = "succeeded"
        mock_create.return_value.id = "pi_job"
        mock_create.return_value.latest_charge = "ch_job"

        response = self.client.post(reverse("complete_job", args=[self.job.id]))

        self.job.refresh_from_db()
        invoice = self.job.invoice
        self.assertRedirects(response, reverse("billing:invoice_detail", args=[invoice.id]))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.payment_method, "card")
        mock_create.assert_called_once()

    def test_owner_can_create_draft_invoice_from_scheduled_job(self):
        response = self.client.post(reverse("job_bill_now", args=[self.job.id]))

        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get(job=self.job)
        self.assertEqual(response["Location"], reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.total, Decimal("85.00"))


class MonthlyBillingCompletionTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="monthly-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Monthly Client",
            invoice_frequency="monthly",
        )
        self.property = Property.objects.create(customer=self.customer, address="42 April Ave")
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mowing",
            default_rate=Decimal("90.00"),
        )
        self.job = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 4, 22),
            status="scheduled",
        )
        self.item = JobServiceItem.objects.create(
            job=self.job,
            service=self.service,
            description="Mowing",
            quantity=Decimal("1.00"),
            unit_price=Decimal("90.00"),
        )
        self.client.force_login(self.owner)

    def test_ajax_owner_completion_adds_job_to_monthly_invoice_queue(self):
        response = self.client.post(
            reverse("complete_job", args=[self.job.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.item.refresh_from_db()
        invoice = Invoice.objects.get(customer=self.customer, period_start=date(2026, 4, 1))
        self.assertEqual(self.job.status, "completed")
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.total, Decimal("90.00"))
        self.assertEqual(self.item.billed_invoice, invoice)

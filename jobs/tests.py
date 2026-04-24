import json
from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from businesses.models import Business
from customers.models import Customer, Property
from jobs.models import Job, RecurringJob


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

import json
from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from businesses.models import Business
from customers.models import Customer, Property
from jobs.models import Crew, Job, JobNote, PropertyNote, RecurringJob


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

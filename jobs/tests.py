import json
from decimal import Decimal
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from billing.models import Estimate, EstimateImage, EstimateLineItem, Invoice
from businesses.models import Business
from customers.models import Customer, Property
from jobs.models import Crew, Job, JobDayAssignment, JobNote, JobServiceItem, JobWorkVisit, Meeting, PropertyNote, RecurringJob
from jobs.services import generate_jobs
from pricing.models import ServiceTemplate


class EstimateSchedulingOptionalItemsTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="estimate-owner",
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
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Landscape",
            active=True,
        )
        self.client.force_login(self.owner)

    def _accepted_estimate_with_options(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            property=self.property,
            title="Landscape cleanup",
            status="accepted",
            accepted_total=Decimal("425.00"),
            notes="Client wants the west bed cleaned first.\nUse dark brown mulch.",
            site_visit_notes="Gate code 2468. Avoid parking on driveway.",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base cleanup",
            detail_description="Remove leaves, cut back grasses, and haul debris.",
            quantity=1,
            unit_price=Decimal("0.00"),
            material_cost=Decimal("180.00"),
            labor_cost=Decimal("120.00"),
        )
        selected = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Mulch refresh",
            detail_description="Install 3 yards around front beds.",
            quantity=1,
            unit_price=Decimal("125.00"),
            is_addon=True,
        )
        declined = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Seasonal color",
            quantity=1,
            unit_price=Decimal("95.00"),
            is_addon=True,
        )
        estimate.accepted_optional_item_ids = [selected.id]
        estimate.save(update_fields=["accepted_optional_item_ids"])
        EstimateImage.objects.create(
            estimate=estimate,
            image="estimates/2026/05/front-bed-before.jpg",
            caption="Front bed before cleanup",
            order=1,
        )
        EstimateImage.objects.create(
            estimate=estimate,
            image="estimates/2026/05/gate-access.jpg",
            caption="Gate/access point",
            order=2,
        )
        return estimate, selected, declined

    def test_schedule_from_estimate_copies_only_accepted_items_to_job(self):
        estimate, _selected, declined = self._accepted_estimate_with_options()

        response = self.client.post(
            reverse("schedule_from_estimate", args=[estimate.id]),
            data={"schedule_date": "2026-05-06"},
        )

        self.assertRedirects(response, reverse("job_list"))
        job = Job.objects.get(property=self.property, scheduled_date=date(2026, 5, 6))
        descriptions = list(job.service_items.order_by("id").values_list("description", flat=True))
        self.assertEqual(descriptions, ["Base cleanup", "Mulch refresh"])
        self.assertNotIn(declined.description, descriptions)

    def test_schedule_from_estimate_transfers_notes_and_descriptions_to_job(self):
        estimate, _selected, _declined = self._accepted_estimate_with_options()

        response = self.client.post(
            reverse("schedule_from_estimate", args=[estimate.id]),
            data={"schedule_date": "2026-05-06"},
        )

        self.assertRedirects(response, reverse("job_list"))
        job = Job.objects.get(property=self.property, scheduled_date=date(2026, 5, 6))
        self.assertIn("Client wants the west bed cleaned first.", job.notes)
        self.assertIn("Gate code 2468", job.notes)
        details = list(job.service_items.order_by("id").values_list("detail_description", flat=True))
        self.assertEqual(details, [
            "Remove leaves, cut back grasses, and haul debris.",
            "Install 3 yards around front beds.",
        ])

    def test_schedule_from_estimate_transfers_photos_to_job_site_photos(self):
        estimate, _selected, _declined = self._accepted_estimate_with_options()

        response = self.client.post(
            reverse("schedule_from_estimate", args=[estimate.id]),
            data={"schedule_date": "2026-05-06"},
        )

        self.assertRedirects(response, reverse("job_list"))
        job = Job.objects.get(property=self.property, scheduled_date=date(2026, 5, 6))
        photos = list(job.site_photos.order_by("caption"))
        self.assertEqual(len(photos), 2)
        self.assertEqual({photo.caption for photo in photos}, {"Front bed before cleanup", "Gate/access point"})
        self.assertEqual({photo.category for photo in photos}, {"before"})
        self.assertEqual({photo.uploaded_by_id for photo in photos}, {self.owner.id})
        self.assertIn("estimates/2026/05/front-bed-before.jpg", {photo.image.name for photo in photos})

    def test_estimate_to_scheduled_job_to_completed_job_to_invoice_preserves_quote_details(self):
        self.customer.invoice_frequency = "per_service"
        self.customer.save(update_fields=["invoice_frequency"])
        estimate, _selected, _declined = self._accepted_estimate_with_options()

        response = self.client.post(
            reverse("schedule_from_estimate", args=[estimate.id]),
            data={"schedule_date": "2026-05-06"},
        )
        self.assertRedirects(response, reverse("job_list"))
        job = Job.objects.get(property=self.property, scheduled_date=date(2026, 5, 6))

        self.assertIn("From estimate", job.notes)
        self.assertEqual(job.site_photos.count(), 2)
        job_items = list(job.service_items.order_by("id"))
        self.assertEqual([item.description for item in job_items], ["Base cleanup", "Mulch refresh"])
        self.assertEqual([item.detail_description for item in job_items], [
            "Remove leaves, cut back grasses, and haul debris.",
            "Install 3 yards around front beds.",
        ])
        self.assertEqual([item.unit_price for item in job_items], [Decimal("300.00"), Decimal("125.00")])

        response = self.client.post(reverse("complete_job", args=[job.id]))

        invoice = Invoice.objects.get(job=job)
        self.assertRedirects(response, reverse("billing:invoice_detail", args=[invoice.id]))
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.site_photos.count(), 2)
        invoice_items = list(invoice.line_items.order_by("id"))
        self.assertEqual([item.description for item in invoice_items], ["Base cleanup", "Mulch refresh"])
        self.assertEqual([item.detail_description for item in invoice_items], [
            "Remove leaves, cut back grasses, and haul debris.",
            "Install 3 yards around front beds.",
        ])
        self.assertEqual([item.unit_price for item in invoice_items], [Decimal("300.00"), Decimal("125.00")])
        self.assertEqual(invoice.total, Decimal("425.00"))

    def test_accepted_estimate_can_be_scheduled_and_invoiced_without_existing_service_templates(self):
        self.service.delete()
        estimate, _selected, _declined = self._accepted_estimate_with_options()

        response = self.client.post(
            reverse("schedule_from_estimate", args=[estimate.id]),
            data={"schedule_date": "2026-05-06"},
        )

        self.assertRedirects(response, reverse("job_list"))
        job = Job.objects.get(property=self.property, scheduled_date=date(2026, 5, 6))
        self.assertEqual(job.service_items.count(), 2)

        response = self.client.post(reverse("job_bill_now", args=[job.id]))

        invoice = Invoice.objects.get(job=job)
        descriptions = list(invoice.line_items.order_by("id").values_list("description", flat=True))
        details = list(invoice.line_items.order_by("id").values_list("detail_description", flat=True))
        self.assertEqual(response["Location"], reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(descriptions, ["Base cleanup", "Mulch refresh"])
        self.assertEqual(details, [
            "Remove leaves, cut back grasses, and haul debris.",
            "Install 3 yards around front beds.",
        ])
        self.assertEqual(invoice.total, Decimal("425.00"))

    def test_create_job_prefill_from_estimate_uses_only_accepted_items(self):
        estimate, _selected, declined = self._accepted_estimate_with_options()

        response = self.client.get(reverse("create_job") + f"?estimate={estimate.id}")

        self.assertEqual(response.status_code, 200)
        formset = response.context["formset"]
        initial_names = [form.initial.get("service_name") for form in formset.forms if form.initial]
        self.assertEqual(initial_names, ["Base cleanup", "Mulch refresh"])
        self.assertNotIn(declined.description, initial_names)

    def test_create_job_prefill_from_estimate_includes_estimate_notes(self):
        estimate, _selected, _declined = self._accepted_estimate_with_options()

        response = self.client.get(reverse("create_job") + f"?estimate={estimate.id}")

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("Client wants the west bed cleaned first.", form.initial["notes"])
        self.assertIn("Gate code 2468", form.initial["notes"])


class JobServiceItemSchedulingTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="project-owner",
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
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Patio install",
            active=True,
        )
        self.job = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 5, 11),
            scheduled_end_date=date(2026, 5, 15),
            status="scheduled",
        )
        self.item = JobServiceItem.objects.create(
            job=self.job,
            service=self.service,
            description="Base prep",
            quantity=1,
            unit_price=Decimal("900.00"),
        )
        self.client.force_login(self.owner)

    def test_owner_can_schedule_line_item_start_and_end_dates(self):
        response = self.client.post(
            reverse("update_job_service_item", args=[self.job.id, self.item.id]),
            data=json.dumps({
                "scheduled_date": "2026-05-12",
                "scheduled_end_date": "2026-05-14",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.scheduled_date, date(2026, 5, 12))
        self.assertEqual(self.item.scheduled_end_date, date(2026, 5, 14))

    def test_line_item_end_date_cannot_be_before_start_date(self):
        response = self.client.post(
            reverse("update_job_service_item", args=[self.job.id, self.item.id]),
            data=json.dumps({
                "scheduled_date": "2026-05-14",
                "scheduled_end_date": "2026-05-12",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.scheduled_date)

    def test_owner_can_update_job_line_item_title_description_quantity_and_price(self):
        response = self.client.post(
            reverse("update_job_service_item", args=[self.job.id, self.item.id]),
            data=json.dumps({
                "description": "Patio base prep",
                "detail_description": "Excavate, compact stone, and prepare the paver base.",
                "quantity": "2.50",
                "unit_price": "475.25",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.description, "Patio base prep")
        self.assertEqual(self.item.detail_description, "Excavate, compact stone, and prepare the paver base.")
        self.assertEqual(self.item.quantity, Decimal("2.50"))
        self.assertEqual(self.item.unit_price, Decimal("475.25"))

    def test_owner_can_add_multiple_titled_line_items_for_same_service(self):
        response = self.client.post(
            reverse("add_job_service_item", args=[self.job.id]),
            data={
                "service": self.service.id,
                "description": "Paver base",
                "detail_description": "Stone base and compaction.",
                "quantity": "1.00",
                "unit_price": "450.00",
            },
        )
        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))

        response = self.client.post(
            reverse("add_job_service_item", args=[self.job.id]),
            data={
                "service": self.service.id,
                "description": "Edge restraint",
                "detail_description": "Install edge restraint and spikes.",
                "quantity": "1.00",
                "unit_price": "175.00",
            },
        )
        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))

        descriptions = list(
            self.job.service_items.order_by("id").values_list("description", flat=True)
        )
        self.assertIn("Paver base", descriptions)
        self.assertIn("Edge restraint", descriptions)

    def test_calendar_job_data_includes_job_line_item_descriptions(self):
        self.item.description = "Patio base prep"
        self.item.detail_description = "Excavate, compact stone, and prepare the paver base."
        self.item.save(update_fields=["description", "detail_description"])

        response = self.client.get(reverse("calendar_job_data", args=[self.job.id]))

        self.assertEqual(response.status_code, 200)
        service = response.json()["job"]["services"][0]
        self.assertEqual(service["name"], "Patio base prep")
        self.assertEqual(service["service_name"], "Patio install")
        self.assertEqual(service["description"], "Patio base prep")
        self.assertEqual(service["detail_description"], "Excavate, compact stone, and prepare the paver base.")

    def test_crew_today_shows_line_item_descriptions(self):
        today = date.today()
        self.job.scheduled_date = today
        self.job.scheduled_end_date = None
        self.job.save(update_fields=["scheduled_date", "scheduled_end_date"])
        self.item.description = "Patio base prep"
        self.item.detail_description = "Excavate, compact stone, and prepare the paver base."
        self.item.save(update_fields=["description", "detail_description"])

        response = self.client.get(reverse("crew_today"))

        self.assertContains(response, "Patio base prep")
        self.assertContains(response, "Excavate, compact stone, and prepare the paver base.")

    def test_owner_can_add_non_consecutive_return_visit_to_same_job_item(self):
        response = self.client.post(
            reverse("add_job_work_visit", args=[self.job.id]),
            data={
                "service_item": self.item.id,
                "scheduled_date": "2026-05-19",
                "notes": "Return after pavers arrive.",
            },
        )

        self.assertRedirects(response, reverse("job_detail", args=[self.job.id]))
        visit = JobWorkVisit.objects.get(job=self.job)
        self.assertEqual(visit.service_item, self.item)
        self.assertEqual(visit.scheduled_date, date(2026, 5, 19))
        self.assertIsNone(visit.scheduled_end_date)
        self.assertEqual(visit.notes, "Return after pavers arrive.")

    def test_owner_can_add_return_visit_inline_from_calendar_modal(self):
        response = self.client.post(
            reverse("add_job_work_visit", args=[self.job.id]),
            data={
                "service_item": self.item.id,
                "scheduled_date": "2026-05-21",
                "scheduled_end_date": "2026-05-22",
                "notes": "Finish cleanup after inspection.",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["visit"]["service_item_id"], self.item.id)
        self.assertEqual(payload["visit"]["scheduled_date"], "2026-05-21")
        self.assertEqual(payload["visit"]["scheduled_end_date"], "2026-05-22")
        self.assertEqual(payload["visit"]["notes"], "Finish cleanup after inspection.")

    def test_owner_can_move_return_visit_without_moving_original_job(self):
        visit = JobWorkVisit.objects.create(
            job=self.job,
            service_item=self.item,
            scheduled_date=date(2026, 5, 19),
            notes="Return after pavers arrive.",
        )

        response = self.client.post(
            reverse("update_job_work_visit", args=[self.job.id, visit.id]),
            data=json.dumps({
                "scheduled_date": "2026-05-23",
                "scheduled_end_date": "2026-05-24",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        visit.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(visit.scheduled_date, date(2026, 5, 23))
        self.assertEqual(visit.scheduled_end_date, date(2026, 5, 24))
        self.assertEqual(self.job.scheduled_date, date(2026, 5, 11))

    def test_owner_can_remove_return_visit_inline_from_calendar_modal(self):
        visit = JobWorkVisit.objects.create(
            job=self.job,
            service_item=self.item,
            scheduled_date=date(2026, 5, 19),
        )

        response = self.client.post(
            reverse("remove_job_work_visit", args=[self.job.id, visit.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertFalse(JobWorkVisit.objects.filter(id=visit.id).exists())

    def test_calendar_events_include_return_visit_without_moving_original_job(self):
        JobWorkVisit.objects.create(
            job=self.job,
            service_item=self.item,
            scheduled_date=date(2026, 5, 19),
            notes="Return after pavers arrive.",
        )

        response = self.client.get(reverse("calendar_events"), {"start": "2026-05-01", "end": "2026-05-31"})

        self.assertEqual(response.status_code, 200)
        events = response.json()
        original = [e for e in events if e["id"] == str(self.job.id)]
        returns = [e for e in events if e["id"] == f"visit-{self.job.id}-{self.item.id}-2026-05-19"]
        self.assertEqual(len(original), 1)
        self.assertEqual(original[0]["start"], "2026-05-11")
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0]["start"], "2026-05-19T08:00:00")
        self.assertEqual(returns[0]["extendedProps"]["jobId"], self.job.id)
        self.assertTrue(returns[0]["extendedProps"]["returnVisit"])

    def test_crew_today_includes_non_consecutive_return_visit(self):
        from accounts.timezone_utils import business_today
        today = business_today(self.business)
        self.job.scheduled_date = date(2026, 5, 11)
        self.job.scheduled_end_date = None
        self.job.save(update_fields=["scheduled_date", "scheduled_end_date"])
        JobWorkVisit.objects.create(
            job=self.job,
            service_item=self.item,
            scheduled_date=today,
            notes="Return after pavers arrive.",
        )
        self.assertEqual(JobWorkVisit.objects.filter(job=self.job, scheduled_date=today).count(), 1)
        self.assertEqual(
            Job.objects.filter(
                Q(scheduled_date=today)
                | Q(scheduled_date__lte=today, scheduled_end_date__gte=today)
                | Q(work_visits__scheduled_date=today)
                | Q(work_visits__scheduled_date__lte=today, work_visits__scheduled_end_date__gte=today),
                property__customer__business=self.business,
            ).distinct().count(),
            1,
        )

        response = self.client.get(reverse("crew_today"))

        self.assertEqual(response.status_code, 200)
        route_jobs = list(response.context["jobs"])
        self.assertEqual(len(route_jobs), 1)
        self.assertEqual(route_jobs[0].filtered_service_items[0].description, "Base prep")
        self.assertEqual(route_jobs[0].active_return_visits[0].notes, "Return after pavers arrive.")


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

    def test_reschedule_in_progress_job_clears_actual_times_so_calendar_does_not_snap_back(self):
        job = self._create_job(date(2026, 5, 4), start_time=time(8, 0), end_time=time(9, 0))
        started_at = timezone.make_aware(datetime(2026, 5, 4, 8, 15))
        job.status = "in_progress"
        job.started_at = started_at
        job.save(update_fields=["status", "started_at"])

        response = self.client.post(
            reverse("calendar_job_reschedule", args=[job.id]),
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
        job.refresh_from_db()
        self.assertEqual(job.scheduled_date, date(2026, 5, 6))
        self.assertEqual(job.scheduled_time, time(10, 30))
        self.assertEqual(job.scheduled_end_time, time(12, 0))
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)

    def test_meeting_can_be_rescheduled_from_calendar_drag_without_defaulting_time(self):
        meeting = Meeting.objects.create(
            business=self.business,
            title="Estimate walk-through",
            customer=self.customer,
            scheduled_at=timezone.make_aware(datetime(2026, 5, 4, 9, 0)),
            duration_minutes=45,
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("calendar_meeting_reschedule", args=[meeting.id]),
            data=json.dumps({"scheduled_at": "2026-05-06T14:35:00"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        meeting.refresh_from_db()
        self.assertEqual(timezone.localtime(meeting.scheduled_at).date(), date(2026, 5, 6))
        self.assertEqual(timezone.localtime(meeting.scheduled_at).time().replace(tzinfo=None), time(14, 35))
        self.assertEqual(meeting.duration_minutes, 45)

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

    def test_multi_day_day_assignment_changes_one_day_without_touching_other_days(self):
        crew_a = Crew.objects.create(business=self.business, name="Crew A")
        crew_b = Crew.objects.create(business=self.business, name="Crew B")
        job = self._create_job(date(2026, 5, 4), start_time=None, end_time=None)
        job.scheduled_end_date = date(2026, 5, 6)
        job.assigned_crew = crew_a
        job.save(update_fields=["scheduled_end_date", "assigned_crew"])

        response = self.client.post(
            reverse("calendar_job_day_assignment_update", args=[job.id]),
            data=json.dumps({"date": "2026-05-05", "assigned_crew_id": crew_b.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.assigned_crew_id, crew_a.id)
        self.assertEqual(JobDayAssignment.objects.get(job=job, date=date(2026, 5, 5)).assigned_crew_id, crew_b.id)
        self.assertFalse(JobDayAssignment.objects.filter(job=job, date=date(2026, 5, 4)).exists())
        self.assertFalse(JobDayAssignment.objects.filter(job=job, date=date(2026, 5, 6)).exists())

    def test_crew_today_uses_day_assignment_override_for_multi_day_job(self):
        today = timezone.localdate()
        crew_a_user = User.objects.create_user(username="crew-a", password="password", role="crew", business=self.business)
        crew_b_user = User.objects.create_user(username="crew-b", password="password", role="crew", business=self.business)
        crew_a = Crew.objects.create(business=self.business, name="Crew A")
        crew_b = Crew.objects.create(business=self.business, name="Crew B")
        crew_a.members.add(crew_a_user)
        crew_b.members.add(crew_b_user)
        job = self._create_job(today, start_time=None, end_time=None)
        job.scheduled_end_date = today + timedelta(days=2)
        job.assigned_crew = crew_a
        job.save(update_fields=["scheduled_end_date", "assigned_crew"])
        JobDayAssignment.objects.create(job=job, date=today, assigned_crew=crew_b)

        self.client.force_login(crew_a_user)
        response_a = self.client.get(reverse("crew_today"))
        self.assertEqual(response_a.status_code, 200)
        self.assertNotIn(job, list(response_a.context["jobs"]))

        self.client.force_login(crew_b_user)
        response_b = self.client.get(reverse("crew_today"))
        self.assertEqual(response_b.status_code, 200)
        self.assertIn(job, list(response_b.context["jobs"]))


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

    @patch("jobs.services._biz_today")
    def test_recurring_generator_uses_clean_mowing_label_for_field_mowing_template(self, mock_today):
        mock_today.return_value = date(2026, 5, 1)
        self.mowing_service.name = "Field Mowing"
        self.mowing_service.save(update_fields=["name"])
        self.recurring_job.service_snapshot = [
            {
                "service_id": self.mowing_service.id,
                "quantity": "1",
                "unit": "visit",
                "unit_price": "85.00",
            }
        ]
        self.recurring_job.start_date = date(2026, 5, 1)
        self.recurring_job.save(update_fields=["service_snapshot", "start_date"])

        generate_jobs(days_ahead=1)

        item = JobServiceItem.objects.get(job__scheduled_date=date(2026, 5, 1))
        self.assertEqual(item.description, "Mowing")


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
        item = self.job.service_items.get()
        item.refresh_from_db()
        self.assertEqual(response["Location"], reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.total, Decimal("85.00"))
        self.assertEqual(item.billed_invoice, invoice)

    def test_bill_now_populates_existing_empty_job_invoice(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            job=self.job,
            status="draft",
            total=Decimal("0.00"),
            subtotal=Decimal("0.00"),
        )
        item = self.job.service_items.get()
        item.description = "Front lawn mowing"
        item.detail_description = "Cut, trim, edge, and clean up clippings."
        item.quantity = Decimal("1.00")
        item.unit_price = Decimal("85.00")
        item.save(update_fields=["description", "detail_description", "quantity", "unit_price"])

        response = self.client.post(reverse("job_bill_now", args=[self.job.id]))

        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        line = invoice.line_items.get()
        item.refresh_from_db()
        self.assertEqual(response["Location"], reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(line.description, "Front lawn mowing")
        self.assertEqual(line.detail_description, "Cut, trim, edge, and clean up clippings.")
        self.assertEqual(line.unit_price, Decimal("85.00"))
        self.assertEqual(invoice.total, Decimal("85.00"))
        self.assertEqual(item.billed_invoice, invoice)


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

    def test_paid_job_is_not_collected_again_by_monthly_repair(self):
        self.job.status = "completed"
        self.job.save(update_fields=["status"])

        response = self.client.post(
            reverse("mark_job_paid", args=[self.job.id]),
            data={"payment_method": "cash"},
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        paid_invoice = Invoice.objects.get(job=self.job)
        self.assertEqual(paid_invoice.status, "paid")
        self.assertEqual(self.item.billed_invoice, paid_invoice)

        self.client.post(
            reverse("billing:monthly_invoice_build_missing"),
            data={"year": "2026", "month": "4"},
        )

        self.assertFalse(
            Invoice.objects.filter(
                customer=self.customer,
                job__isnull=True,
                period_start=date(2026, 4, 1),
            ).exists()
        )

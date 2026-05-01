from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification, User
from businesses.models import Business
from time_tracking.models import TimeEntry


class TimeClockNotificationTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Test Landscaping",
            complimentary_access_enabled=True,
        )
        self.owner = User.objects.create_user(
            username="owner",
            password="pass",
            business=self.business,
            role="owner",
        )
        self.manager = User.objects.create_user(
            username="manager",
            password="pass",
            business=self.business,
            role="manager",
        )
        self.crew = User.objects.create_user(
            username="crew",
            password="pass",
            business=self.business,
            role="crew",
        )

    def test_clock_in_records_time_without_owner_notification(self):
        self.client.force_login(self.crew)

        response = self.client.post(
            reverse("time_clock_in"),
            {"latitude": "39.7684000", "longitude": "-86.1581000"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("time_clock"))
        self.assertEqual(TimeEntry.objects.filter(user=self.crew, clock_out__isnull=True).count(), 1)
        self.assertEqual(Notification.objects.filter(to_user__in=[self.owner, self.manager]).count(), 0)

    def test_clock_out_records_time_without_owner_notification(self):
        TimeEntry.objects.create(user=self.crew, clock_in=timezone.now() - timezone.timedelta(hours=1))
        self.client.force_login(self.crew)

        response = self.client.post(
            reverse("time_clock_out"),
            {"latitude": "39.7700000", "longitude": "-86.1600000"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("time_clock"))
        entry = TimeEntry.objects.get(user=self.crew)
        self.assertIsNotNone(entry.clock_out)
        self.assertEqual(Notification.objects.filter(to_user__in=[self.owner, self.manager]).count(), 0)

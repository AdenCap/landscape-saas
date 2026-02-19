"""
Send in-app meeting reminders to business owners.

Finds meetings where:
  - reminder_sent_at is null
  - scheduled_at is in the future
  - scheduled_at - reminder_hours_before <= now (time to remind)

Creates a Notification for each owner of the business (so they see it in-app).
Run via cron, e.g. every hour:
  0 * * * * cd /path/to/project && python manage.py send_meeting_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from jobs.models import Meeting
from accounts.models import User, Notification


class Command(BaseCommand):
    help = "Send in-app reminders for upcoming meetings (notifications to owners)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Log what would be sent without creating notifications")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        # Meetings that are still in the future but within the reminder window
        meetings = Meeting.objects.filter(
            reminder_sent_at__isnull=True,
            scheduled_at__gt=now,
        ).select_related("business", "created_by", "customer")

        sent = 0
        for meeting in meetings:
            hours_before = meeting.reminder_hours_before or 24
            reminder_at = meeting.scheduled_at - timezone.timedelta(hours=hours_before)
            if now < reminder_at:
                continue  # Not yet time to remind

            business = meeting.business
            owners = list(User.objects.filter(business=business, role="owner"))
            if not owners:
                self.stdout.write(self.style.WARNING(f"Meeting {meeting.id} ({meeting.title}): no owners for business {business.name}, skipping"))
                continue

            # from_user: use meeting creator if they're an owner, else first owner
            from_user = meeting.created_by if (meeting.created_by and meeting.created_by in owners) else owners[0]
            customer_part = f" with {meeting.customer.name}" if meeting.customer else ""
            message = f"Reminder: Meeting “{meeting.title}”{customer_part} at {meeting.scheduled_at.strftime('%b %d, %Y at %I:%M %p')}."

            if dry_run:
                self.stdout.write(f"Would notify {len(owners)} owner(s): {message}")
                sent += 1
                continue

            for to_user in owners:
                Notification.objects.create(
                    business=business,
                    from_user=from_user,
                    to_user=to_user,
                    message=message,
                )
            meeting.reminder_sent_at = now
            meeting.save(update_fields=["reminder_sent_at"])
            sent += 1
            self.stdout.write(f"Sent reminder for meeting “{meeting.title}” to {len(owners)} owner(s)")

        self.stdout.write(self.style.SUCCESS(f"Done. {'Would send' if dry_run else 'Sent'} {sent} meeting reminder(s)."))

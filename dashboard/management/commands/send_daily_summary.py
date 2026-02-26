"""Management command to send daily summary emails to business owners."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from businesses.models import Business
from accounts.models import User
from jobs.models import Job
from billing.models import Invoice
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send daily summary emails to business owners'

    def handle(self, *args, **options):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        businesses = Business.objects.filter(users__role='owner').distinct()
        
        sent = 0
        failed = 0
        
        for business in businesses:
            owner = business.users.filter(role='owner').first()
            if not owner or not owner.email:
                continue
            
            # Get stats
            jobs_today = Job.objects.filter(
                property__customer__business=business,
                scheduled_date=today
            ).count()
            
            jobs_completed_yesterday = Job.objects.filter(
                property__customer__business=business,
                status='completed',
                updated_at__date=yesterday
            ).count()
            
            invoices_sent_yesterday = Invoice.objects.filter(
                business=business,
                status='sent',
                approved_at__date=yesterday
            ).count()
            
            outstanding_invoices = Invoice.objects.filter(
                business=business,
                status='sent'
            ).count()
            
            outstanding_total = sum(
                inv.total for inv in Invoice.objects.filter(
                    business=business,
                    status='sent'
                )
            )
            
            try:
                send_mail(
                    subject=f'Daily Summary - {today.strftime("%B %d, %Y")}',
                    message=(
                        f"Good morning {owner.get_full_name() or owner.username}!\n\n"
                        f"Here's your daily summary for {business.name}:\n\n"
                        f"📅 Jobs Today: {jobs_today}\n"
                        f"✅ Jobs Completed Yesterday: {jobs_completed_yesterday}\n"
                        f"📧 Invoices Sent Yesterday: {invoices_sent_yesterday}\n"
                        f"💰 Outstanding Invoices: {outstanding_invoices} (${outstanding_total:.2f})\n\n"
                        f"Log in to your dashboard to see more details."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    fail_silently=False,
                )
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent summary to {owner.email}'))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f'Failed to send to {owner.email}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Failed: {failed}'))

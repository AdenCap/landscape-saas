"""Management command to send weekly invoice summaries to business owners."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from businesses.models import Business
from accounts.models import User
from billing.models import Invoice
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send weekly invoice summary to business owners'

    def handle(self, *args, **options):
        today = timezone.now().date()
        week_start = today - timedelta(days=7)
        
        businesses = Business.objects.filter(users__role='owner').distinct()
        
        sent = 0
        failed = 0
        
        for business in businesses:
            owner = business.users.filter(role='owner').first()
            if not owner or not owner.email:
                continue
            
            # Get stats for the week
            invoices_sent = Invoice.objects.filter(
                business=business,
                status='sent',
                approved_at__date__gte=week_start
            )
            
            invoices_paid = Invoice.objects.filter(
                business=business,
                status='paid',
                updated_at__date__gte=week_start
            )
            
            total_sent = sum(inv.total for inv in invoices_sent)
            total_paid = sum(inv.total for inv in invoices_paid)
            
            outstanding = Invoice.objects.filter(
                business=business,
                status='sent'
            )
            outstanding_count = outstanding.count()
            outstanding_total = sum(inv.total for inv in outstanding)
            
            try:
                send_mail(
                    subject=f'Weekly Invoice Summary - {business.name}',
                    message=(
                        f"Weekly Invoice Summary for {business.name}:\n\n"
                        f"📧 Invoices Sent This Week: {invoices_sent.count()} (${total_sent:.2f})\n"
                        f"✅ Invoices Paid This Week: {invoices_paid.count()} (${total_paid:.2f})\n"
                        f"💰 Outstanding Invoices: {outstanding_count} (${outstanding_total:.2f})\n\n"
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

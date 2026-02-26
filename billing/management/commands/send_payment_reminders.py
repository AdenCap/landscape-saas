"""Management command to send payment reminders for overdue invoices."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import Invoice
from customers.sms_utils import send_sms
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send payment reminders for overdue invoices'

    def handle(self, *args, **options):
        today = timezone.now().date()
        overdue_invoices = Invoice.objects.filter(
            status='sent',
            due_date__lt=today,
            customer__isnull=False
        ).select_related('customer', 'business')
        
        sent = 0
        failed = 0
        
        for invoice in overdue_invoices:
            customer = invoice.customer
            
            # Generate payment link
            if invoice.payment_token:
                payment_url = f"https://yourdomain.com/billing/{invoice.id}/pay/{invoice.payment_token}/"
            else:
                payment_url = None
            
            # Send via email if available
            if customer.email:
                try:
                    send_mail(
                        subject=f'Payment Reminder: Invoice #{invoice.id}',
                        message=(
                            f"Hi {customer.name},\n\n"
                            f"This is a reminder that Invoice #{invoice.id} for ${invoice.total} "
                            f"is overdue (due date: {invoice.due_date}).\n\n"
                            f"{'Pay online: ' + payment_url if payment_url else ''}\n\n"
                            f"Thank you,\n{invoice.business.name}"
                        ),
                        from_email=invoice.business.get_from_email() or settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[customer.email],
                        fail_silently=False,
                    )
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent payment reminder to {customer.name}'))
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'Failed to send to {customer.name}: {e}'))
            
            # Send via SMS if phone available and prefers SMS
            elif customer.phone and customer.communication_preference in ['sms', 'both']:
                message = (
                    f"Reminder: Invoice #{invoice.id} for ${invoice.total} is overdue. "
                    f"{'Pay: ' + payment_url if payment_url else 'Please contact us to arrange payment.'}"
                )
                success, result = send_sms(customer.phone, message, invoice.business)
                if success:
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent payment reminder to {customer.name} via SMS'))
                else:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'Failed to send SMS to {customer.name}: {result}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Failed: {failed}'))

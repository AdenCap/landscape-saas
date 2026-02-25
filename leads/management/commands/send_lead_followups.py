"""Management command to send follow-up reminders for leads."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from leads.models import Lead
from customers.sms_utils import send_sms
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send follow-up reminders for leads with next_follow_up date today'

    def handle(self, *args, **options):
        today = timezone.now().date()
        leads = Lead.objects.filter(
            next_follow_up=today,
            status__in=['new', 'contacted', 'qualified'],
            business__isnull=False
        ).select_related('business')
        
        sent = 0
        failed = 0
        
        for lead in leads:
            business = lead.business
            
            # Send via email if available
            if lead.email:
                try:
                    send_mail(
                        subject=f'Follow-up: {business.name}',
                        message=(
                            f"Hi {lead.name},\n\n"
                            f"This is a follow-up regarding your inquiry about our services.\n\n"
                            f"{lead.follow_up_notes or 'We wanted to check in and see if you have any questions.'}\n\n"
                            f"Please contact us at {business.contact_phone or business.contact_email}.\n\n"
                            f"Thank you,\n{business.name}"
                        ),
                        from_email=business.get_from_email() or settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[lead.email],
                        fail_silently=False,
                    )
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent follow-up to {lead.name}'))
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'Failed to send to {lead.name}: {e}'))
            
            # Send via SMS if phone available
            elif lead.phone:
                message = (
                    f"Hi {lead.name}, this is {business.name}. "
                    f"We wanted to follow up on your inquiry. "
                    f"Call us at {business.contact_phone or 'our office'} if you have questions."
                )
                success, result = send_sms(lead.phone, message, business)
                if success:
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f'Sent follow-up to {lead.name} via SMS'))
                else:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'Failed to send SMS to {lead.name}: {result}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent: {sent}, Failed: {failed}'))

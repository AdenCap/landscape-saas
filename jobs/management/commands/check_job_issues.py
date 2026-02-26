"""Management command to alert owners about unresolved job issues."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import JobIssue
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Alert owners about unresolved job issues older than 24 hours'

    def handle(self, *args, **options):
        # Find unresolved issues older than 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        unresolved_issues = JobIssue.objects.filter(
            status='open',
            created_at__lt=cutoff_time
        ).select_related('job__property__customer__business', 'reported_by')
        
        if not unresolved_issues.exists():
            self.stdout.write(self.style.SUCCESS('No unresolved issues found'))
            return
        
        # Group by business
        by_business = {}
        for issue in unresolved_issues:
            business = issue.job.property.customer.business if issue.job.property.customer else None
            if not business:
                continue
            if business not in by_business:
                by_business[business] = []
            by_business[business].append(issue)
        
        sent = 0
        for business, issues in by_business.items():
            # Get business owner email
            owner = business.users.filter(role='owner').first()
            if not owner or not owner.email:
                continue
            
            issue_list = '\n'.join([
                f"- Job #{issue.job.id} at {issue.job.property.address}: {issue.get_issue_type_display()} "
                f"(reported {issue.created_at.strftime('%Y-%m-%d %H:%M')} by {issue.reported_by.get_full_name() or issue.reported_by.username})"
                for issue in issues
            ])
            
            try:
                send_mail(
                    subject=f'Unresolved Job Issues: {len(issues)} issue(s)',
                    message=(
                        f"The following job issues have been open for more than 24 hours:\n\n"
                        f"{issue_list}\n\n"
                        f"Please review and resolve these issues."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    fail_silently=False,
                )
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent alert to {owner.email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send alert: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent alerts: {sent}'))

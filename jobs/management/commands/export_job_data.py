"""Management command to export job data for reporting."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job
from businesses.models import Business
import csv
from io import StringIO


class Command(BaseCommand):
    help = 'Export job data to CSV for reporting/analysis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Export jobs for specific business ID',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='jobs_export.csv',
            help='Output CSV filename',
        )

    def handle(self, *args, **options):
        jobs = Job.objects.select_related('property', 'property__customer', 'assigned_to', 'assigned_crew')
        
        if options['business_id']:
            jobs = jobs.filter(property__customer__business_id=options['business_id'])
        
        if options['start_date']:
            jobs = jobs.filter(scheduled_date__gte=options['start_date'])
        
        if options['end_date']:
            jobs = jobs.filter(scheduled_date__lte=options['end_date'])
        
        jobs = jobs.order_by('scheduled_date', 'id')
        
        # Write CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Job ID', 'Date', 'Customer', 'Address', 'Status',
            'Assigned To', 'Crew', 'Labor Cost', 'Material Cost',
            'Created', 'Completed'
        ])
        
        for job in jobs:
            writer.writerow([
                job.id,
                job.scheduled_date or '',
                job.property.customer.name if job.property.customer else '',
                job.property.address,
                job.get_status_display(),
                job.assigned_to.get_full_name() if job.assigned_to else '',
                job.assigned_crew.name if job.assigned_crew else '',
                job.labor_cost,
                job.material_cost,
                job.created_at.strftime('%Y-%m-%d') if job.created_at else '',
                'Yes' if job.status == 'completed' else 'No',
            ])
        
        # Write to file
        with open(options['output'], 'w', newline='') as f:
            f.write(output.getvalue())
        
        self.stdout.write(self.style.SUCCESS(f'Exported {jobs.count()} jobs to {options["output"]}'))

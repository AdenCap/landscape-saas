"""Management command to export invoice data for reporting."""
from django.core.management.base import BaseCommand
from billing.models import Invoice
import csv
from io import StringIO


class Command(BaseCommand):
    help = 'Export invoice data to CSV for reporting/analysis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Export invoices for specific business ID',
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by status (draft, sent, paid, void)',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='invoices_export.csv',
            help='Output CSV filename',
        )

    def handle(self, *args, **options):
        invoices = Invoice.objects.select_related('customer', 'business')
        
        if options['business_id']:
            invoices = invoices.filter(business_id=options['business_id'])
        
        if options['status']:
            invoices = invoices.filter(status=options['status'])
        
        invoices = invoices.order_by('-issue_date', '-id')
        
        # Write CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Invoice ID', 'Issue Date', 'Due Date', 'Customer', 'Status',
            'Subtotal', 'Tax', 'Total', 'Paid Date'
        ])
        
        for invoice in invoices:
            writer.writerow([
                invoice.id,
                invoice.issue_date,
                invoice.due_date or '',
                invoice.customer.name,
                invoice.get_status_display(),
                invoice.subtotal,
                invoice.tax,
                invoice.total,
                invoice.updated_at.strftime('%Y-%m-%d') if invoice.status == 'paid' else '',
            ])
        
        # Write to file
        with open(options['output'], 'w', newline='') as f:
            f.write(output.getvalue())
        
        self.stdout.write(self.style.SUCCESS(f'Exported {invoices.count()} invoices to {options["output"]}'))

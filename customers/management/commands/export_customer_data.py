"""Management command to export customer data for reporting."""
from django.core.management.base import BaseCommand
from customers.models import Customer
import csv
from io import StringIO


class Command(BaseCommand):
    help = 'Export customer data to CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Export customers for specific business ID',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='customers_export.csv',
            help='Output CSV filename',
        )

    def handle(self, *args, **options):
        customers = Customer.objects.select_related('business')
        
        if options['business_id']:
            customers = customers.filter(business_id=options['business_id'])
        
        customers = customers.order_by('name')
        
        # Write CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Name', 'Email', 'Phone', 'Address', 'City', 'State', 'ZIP',
            'Invoice Frequency', 'Created', 'Total Revenue'
        ])
        
        for customer in customers:
            # Calculate total revenue
            from billing.models import Invoice
            total_revenue = sum(
                inv.total for inv in Invoice.objects.filter(
                    customer=customer,
                    status='paid'
                )
            )
            
            writer.writerow([
                customer.id,
                customer.name,
                customer.email,
                customer.phone,
                customer.address_line1,
                customer.city,
                customer.state,
                customer.postal_code,
                customer.get_invoice_frequency_display(),
                customer.created_at.strftime('%Y-%m-%d'),
                total_revenue,
            ])
        
        # Write to file
        with open(options['output'], 'w', newline='') as f:
            f.write(output.getvalue())
        
        self.stdout.write(self.style.SUCCESS(f'Exported {customers.count()} customers to {options["output"]}'))

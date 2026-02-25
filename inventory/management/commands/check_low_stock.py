"""Management command to check for low stock items and send alerts."""
from django.core.management.base import BaseCommand
from inventory.models import InventoryItem
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send alerts for inventory items below threshold'

    def handle(self, *args, **options):
        low_stock_items = InventoryItem.objects.filter(
            is_active=True
        ).select_related('business')
        
        low_stock_items = [item for item in low_stock_items if item.is_low_stock]
        
        if not low_stock_items:
            self.stdout.write(self.style.SUCCESS('No low stock items'))
            return
        
        # Group by business
        by_business = {}
        for item in low_stock_items:
            if item.business not in by_business:
                by_business[item.business] = []
            by_business[item.business].append(item)
        
        sent = 0
        for business, items in by_business.items():
            # Get business owner email
            owner = business.users.filter(role='owner').first()
            if not owner or not owner.email:
                continue
            
            item_list = '\n'.join([
                f"- {item.name}: {item.current_quantity} {item.unit} (threshold: {item.low_stock_threshold})"
                for item in items
            ])
            
            try:
                send_mail(
                    subject=f'Low Stock Alert: {len(items)} item(s)',
                    message=(
                        f"The following inventory items are below their threshold:\n\n"
                        f"{item_list}\n\n"
                        f"Please reorder soon."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    fail_silently=False,
                )
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'Sent low stock alert to {owner.email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send alert: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSent alerts: {sent}'))

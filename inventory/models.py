"""Inventory Management: Track materials, stock levels, and purchases."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from jobs.models import Job
from decimal import Decimal


class InventoryItem(models.Model):
    """Inventory item (material, product, etc.)."""
    UNIT_CHOICES = [
        ('lb', 'Pounds'),
        ('bag', 'Bags'),
        ('gallon', 'Gallons'),
        ('bottle', 'Bottles'),
        ('box', 'Boxes'),
        ('each', 'Each'),
        ('sqft', 'Square Feet'),
        ('cubic_yd', 'Cubic Yards'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='inventory_items'
    )
    name = models.CharField(max_length=255, help_text="e.g. 'Fertilizer 20-10-10', 'Mulch - Brown'")
    sku = models.CharField(max_length=100, blank=True, help_text="SKU or product code")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='each')
    current_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Current stock level"
    )
    low_stock_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Alert when stock falls below this level"
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Cost per unit (for cost tracking)"
    )
    supplier = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.current_quantity} {self.unit})"
    
    @property
    def is_low_stock(self):
        """Check if stock is below threshold."""
        if self.low_stock_threshold is None:
            return False
        return self.current_quantity < self.low_stock_threshold


class InventoryTransaction(models.Model):
    """Track inventory changes (purchases, usage, adjustments)."""
    TRANSACTION_TYPE_CHOICES = [
        ('purchase', 'Purchase'),
        ('usage', 'Usage (Job)'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ]
    
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Positive for purchase/return, negative for usage"
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total cost for this transaction"
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_usage',
        help_text="Job this inventory was used for"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.inventory_item.name} - {self.get_transaction_type_display()} ({self.quantity})"


class PurchaseOrder(models.Model):
    """Purchase order for inventory items."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='purchase_orders'
    )
    supplier = models.CharField(max_length=255)
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-order_date']
    
    def __str__(self):
        return f"PO #{self.id} - {self.supplier} ({self.get_status_display()})"


class PurchaseOrderItem(models.Model):
    """Items in a purchase order."""
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='purchase_orders'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Quantity actually received"
    )
    
    @property
    def total_cost(self):
        return self.quantity * self.unit_cost
    
    def __str__(self):
        return f"{self.inventory_item.name} - {self.quantity}"

"""Inventory Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import InventoryItem, InventoryTransaction, PurchaseOrder


@role_required("owner")
def inventory_list(request):
    """List all inventory items."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    items = InventoryItem.objects.filter(business=business, is_active=True).order_by('name')
    
    # Check for low stock
    low_stock_items = [item for item in items if item.is_low_stock]
    
    return render(request, 'inventory/inventory_list.html', {
        'items': items,
        'low_stock_items': low_stock_items,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def inventory_item_create(request):
    """Create inventory item."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    if request.method == 'POST':
        item = InventoryItem.objects.create(
            business=business,
            name=request.POST.get('name', ''),
            sku=request.POST.get('sku', ''),
            unit=request.POST.get('unit', 'each'),
            current_quantity=request.POST.get('current_quantity', 0) or 0,
            low_stock_threshold=request.POST.get('low_stock_threshold') or None,
            cost_per_unit=request.POST.get('cost_per_unit', 0) or 0,
            supplier=request.POST.get('supplier', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f"Inventory item '{item.name}' added.")
        return redirect('inventory:inventory_item_detail', item_id=item.id)
    
    return render(request, 'inventory/inventory_item_form.html', {'action': 'Add'})


@role_required("owner")
def inventory_item_detail(request, item_id):
    """Inventory item detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    item = get_object_or_404(InventoryItem, pk=item_id, business=business)
    transactions = item.transactions.all()[:20]
    
    return render(request, 'inventory/inventory_item_detail.html', {
        'item': item,
        'transactions': transactions,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def inventory_item_edit(request, item_id):
    """Edit inventory item."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    item = get_object_or_404(InventoryItem, pk=item_id, business=business)
    
    if request.method == 'POST':
        item.name = request.POST.get('name', '')
        item.sku = request.POST.get('sku', '')
        item.unit = request.POST.get('unit', 'each')
        item.current_quantity = request.POST.get('current_quantity', 0) or 0
        item.low_stock_threshold = request.POST.get('low_stock_threshold') or None
        item.cost_per_unit = request.POST.get('cost_per_unit', 0) or 0
        item.supplier = request.POST.get('supplier', '')
        item.notes = request.POST.get('notes', '')
        item.save()
        messages.success(request, "Inventory item updated.")
        return redirect('inventory:inventory_item_detail', item_id=item.id)
    
    return render(request, 'inventory/inventory_item_form.html', {
        'item': item,
        'action': 'Edit',
    })


@role_required("owner")
def purchase_order_list(request):
    """List purchase orders."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    orders = PurchaseOrder.objects.filter(business=business).order_by('-order_date')
    
    return render(request, 'inventory/purchase_order_list.html', {
        'orders': orders,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def purchase_order_create(request):
    """Create purchase order."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    if request.method == 'POST':
        order = PurchaseOrder.objects.create(
            business=business,
            supplier=request.POST.get('supplier', ''),
            order_date=request.POST.get('order_date'),
            expected_delivery_date=request.POST.get('expected_delivery_date') or None,
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        messages.success(request, f"Purchase order #{order.id} created.")
        return redirect('inventory:purchase_order_list')
    
    return render(request, 'inventory/purchase_order_form.html', {'action': 'Create'})

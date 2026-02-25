"""Equipment Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import Equipment, EquipmentMaintenance, EquipmentUsage


@role_required("owner")
def equipment_list(request):
    """List all equipment."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    equipment = Equipment.objects.filter(business=business, is_active=True).order_by('name')
    
    return render(request, 'equipment/equipment_list.html', {
        'equipment': equipment,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def equipment_create(request):
    """Create equipment."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    if request.method == 'POST':
        equipment = Equipment.objects.create(
            business=business,
            name=request.POST.get('name', ''),
            equipment_type=request.POST.get('equipment_type', 'other'),
            make=request.POST.get('make', ''),
            model=request.POST.get('model', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f"Equipment '{equipment.name}' added.")
        return redirect('equipment:equipment_detail', equipment_id=equipment.id)
    
    return render(request, 'equipment/equipment_form.html', {'action': 'Add'})


@role_required("owner")
def equipment_detail(request, equipment_id):
    """Equipment detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    equipment = get_object_or_404(Equipment, pk=equipment_id, business=business)
    maintenance_records = equipment.maintenance_records.all()[:10]
    usage_records = equipment.usage_records.all()[:20]
    
    return render(request, 'equipment/equipment_detail.html', {
        'equipment': equipment,
        'maintenance_records': maintenance_records,
        'usage_records': usage_records,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def equipment_edit(request, equipment_id):
    """Edit equipment."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    equipment = get_object_or_404(Equipment, pk=equipment_id, business=business)
    
    if request.method == 'POST':
        equipment.name = request.POST.get('name', '')
        equipment.equipment_type = request.POST.get('equipment_type', 'other')
        equipment.make = request.POST.get('make', '')
        equipment.model = request.POST.get('model', '')
        equipment.notes = request.POST.get('notes', '')
        equipment.save()
        messages.success(request, "Equipment updated.")
        return redirect('equipment:equipment_detail', equipment_id=equipment.id)
    
    return render(request, 'equipment/equipment_form.html', {
        'equipment': equipment,
        'action': 'Edit',
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def maintenance_add(request, equipment_id):
    """Add maintenance record."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    equipment = get_object_or_404(Equipment, pk=equipment_id, business=business)
    
    if request.method == 'POST':
        maintenance = EquipmentMaintenance.objects.create(
            equipment=equipment,
            maintenance_date=request.POST.get('maintenance_date'),
            maintenance_type=request.POST.get('maintenance_type', ''),
            cost=request.POST.get('cost', 0) or 0,
            notes=request.POST.get('notes', ''),
            performed_by=request.POST.get('performed_by', ''),
        )
        equipment.last_maintenance_date = maintenance.maintenance_date
        equipment.save(update_fields=['last_maintenance_date'])
        messages.success(request, "Maintenance record added.")
        return redirect('equipment:equipment_detail', equipment_id=equipment.id)
    
    return render(request, 'equipment/maintenance_form.html', {
        'equipment': equipment,
    })

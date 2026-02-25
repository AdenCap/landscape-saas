"""Lead Management Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import Lead
from customers.models import Customer


@role_required("owner")
def lead_list(request):
    """List all leads."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    status_filter = request.GET.get('status', '')
    leads = Lead.objects.filter(business=business)
    if status_filter:
        leads = leads.filter(status=status_filter)
    
    leads = leads.order_by('-created_at')
    
    return render(request, 'leads/lead_list.html', {
        'leads': leads,
        'status_filter': status_filter,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def lead_create(request):
    """Create a new lead."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    if request.method == 'POST':
        lead = Lead.objects.create(
            business=business,
            name=request.POST.get('name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            source=request.POST.get('source', 'website'),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        messages.success(request, f"Lead '{lead.name}' created.")
        return redirect('leads:lead_detail', lead_id=lead.id)
    
    return render(request, 'leads/lead_form.html', {'action': 'Create'})


@role_required("owner")
def lead_detail(request, lead_id):
    """Lead detail view."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    lead = get_object_or_404(Lead, pk=lead_id, business=business)
    
    return render(request, 'leads/lead_detail.html', {
        'lead': lead,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def lead_edit(request, lead_id):
    """Edit a lead."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    lead = get_object_or_404(Lead, pk=lead_id, business=business)
    
    if request.method == 'POST':
        lead.name = request.POST.get('name', '')
        lead.email = request.POST.get('email', '')
        lead.phone = request.POST.get('phone', '')
        lead.address = request.POST.get('address', '')
        lead.source = request.POST.get('source', 'website')
        lead.status = request.POST.get('status', 'new')
        lead.notes = request.POST.get('notes', '')
        lead.next_follow_up = request.POST.get('next_follow_up') or None
        lead.follow_up_notes = request.POST.get('follow_up_notes', '')
        lead.save()
        messages.success(request, "Lead updated.")
        return redirect('leads:lead_detail', lead_id=lead.id)
    
    return render(request, 'leads/lead_form.html', {
        'lead': lead,
        'action': 'Edit',
    })


@role_required("owner")
@require_http_methods(["POST"])
def lead_convert(request, lead_id):
    """Convert a lead to a customer."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    lead = get_object_or_404(Lead, pk=lead_id, business=business)
    
    if lead.converted_customer:
        messages.error(request, "This lead has already been converted.")
        return redirect('leads:lead_detail', lead_id=lead.id)
    
    # Create customer from lead
    customer = Customer.objects.create(
        business=business,
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        address_line1=lead.address,
    )
    
    # Update lead
    lead.converted_customer = customer
    lead.status = 'converted'
    lead.converted_at = timezone.now()
    lead.save()
    
    messages.success(request, f"Lead converted to customer: {customer.name}")
    return redirect('customer_detail', customer_id=customer.id)

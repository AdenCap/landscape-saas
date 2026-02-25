"""Customer Request Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import ServiceRequest


@role_required("owner")
def request_list(request):
    """List all service requests."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    status_filter = request.GET.get('status', '')
    requests = ServiceRequest.objects.filter(business=business)
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    requests = requests.order_by('-created_at')
    
    return render(request, 'customer_requests/request_list.html', {
        'requests': requests,
        'status_filter': status_filter,
    })


@require_http_methods(["GET", "POST"])
def request_create_public(request):
    """Public form for customers to request services."""
    if request.method == 'POST':
        # Get business from request (could be from URL param or default)
        business_id = request.POST.get('business_id') or request.GET.get('business_id')
        # For now, get first business - in production, this would be from domain/subdomain
        from businesses.models import Business
        try:
            business = Business.objects.get(pk=business_id) if business_id else Business.objects.first()
        except Business.DoesNotExist:
            messages.error(request, "Business not found.")
            return render(request, 'customer_requests/request_form_public.html')
        
        service_request = ServiceRequest.objects.create(
            business=business,
            name=request.POST.get('name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            request_type=request.POST.get('request_type', 'estimate'),
            service_description=request.POST.get('service_description', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, "Your request has been submitted! We'll contact you soon.")
        return redirect('customer_requests:request_create_public')
    
    return render(request, 'customer_requests/request_form_public.html')


@role_required("owner")
def request_detail(request, request_id):
    """Service request detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    service_request = get_object_or_404(ServiceRequest, pk=request_id, business=business)
    
    return render(request, 'customer_requests/request_detail.html', {
        'request': service_request,
    })


@role_required("owner")
@require_http_methods(["POST"])
def request_review(request, request_id):
    """Review a service request."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    service_request = get_object_or_404(ServiceRequest, pk=request_id, business=business)
    service_request.status = request.POST.get('status', 'reviewed')
    service_request.reviewed_by = request.user
    service_request.reviewed_at = timezone.now()
    service_request.save()
    
    messages.success(request, "Request reviewed.")
    return redirect('customer_requests:request_detail', request_id=service_request.id)

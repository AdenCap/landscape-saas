"""Customer Portal Views: Allow customers to view their invoices, estimates, and service history."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Sum
from django.utils import timezone
from customers.models import Customer
from billing.models import Invoice, Estimate
from jobs.models import Job
from .models import CustomerPortalAccess
import secrets


def portal_login(request):
    """Customer portal login page."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        token = request.POST.get('token', '').strip()
        
        if not email or not token:
            messages.error(request, "Please enter both email and access token.")
            return render(request, 'customer_portal/login.html')
        
        try:
            customer = Customer.objects.get(email=email)
            access = CustomerPortalAccess.objects.filter(
                customer=customer,
                access_token=token,
                is_active=True
            ).first()
            
            if access:
                request.session['customer_portal_id'] = customer.id
                request.session['customer_portal_token'] = token
                access.last_login = timezone.now()
                access.save(update_fields=['last_login'])
                return redirect('customer_portal:dashboard')
            else:
                messages.error(request, "Invalid email or access token.")
        except Customer.DoesNotExist:
            messages.error(request, "Invalid email or access token.")
    
    return render(request, 'customer_portal/login.html')


def _get_customer_from_session(request):
    """Get customer from session if logged in."""
    customer_id = request.session.get('customer_portal_id')
    token = request.session.get('customer_portal_token')
    
    if not customer_id or not token:
        return None
    
    try:
        customer = Customer.objects.get(pk=customer_id)
        access = CustomerPortalAccess.objects.filter(
            customer=customer,
            access_token=token,
            is_active=True
        ).first()
        if access:
            return customer
    except Customer.DoesNotExist:
        pass
    
    return None


def portal_logout(request):
    """Logout from customer portal."""
    request.session.pop('customer_portal_id', None)
    request.session.pop('customer_portal_token', None)
    messages.success(request, "You have been logged out.")
    return redirect('customer_portal:login')


@require_http_methods(["GET"])
def portal_dashboard(request):
    """Customer portal dashboard."""
    customer = _get_customer_from_session(request)
    if not customer:
        messages.error(request, "Please log in to access your portal.")
        return redirect('customer_portal:login')
    
    # Get customer's data
    invoices = Invoice.objects.filter(customer=customer).order_by('-issue_date')[:10]
    estimates = Estimate.objects.filter(customer=customer).order_by('-created_at')[:10]
    recent_jobs = Job.objects.filter(
        property__customer=customer,
        status='completed'
    ).order_by('-scheduled_date')[:10]
    
    # Calculate totals
    total_paid = Invoice.objects.filter(
        customer=customer,
        status='paid'
    ).aggregate(total=models.Sum('total'))['total'] or 0
    
    outstanding_invoices = Invoice.objects.filter(
        customer=customer,
        status='sent'
    )
    outstanding_total = sum(inv.total for inv in outstanding_invoices)
    
    return render(request, 'customer_portal/dashboard.html', {
        'customer': customer,
        'invoices': invoices,
        'estimates': estimates,
        'recent_jobs': recent_jobs,
        'total_paid': total_paid,
        'outstanding_total': outstanding_total,
        'outstanding_count': outstanding_invoices.count(),
    })


@require_http_methods(["GET"])
def portal_invoices(request):
    """Customer's invoice list."""
    customer = _get_customer_from_session(request)
    if not customer:
        return redirect('customer_portal:login')
    
    invoices = Invoice.objects.filter(customer=customer).order_by('-issue_date')
    
    return render(request, 'customer_portal/invoices.html', {
        'customer': customer,
        'invoices': invoices,
    })


@require_http_methods(["GET"])
def portal_invoice_detail(request, invoice_id):
    """Customer's invoice detail."""
    customer = _get_customer_from_session(request)
    if not customer:
        return redirect('customer_portal:login')
    
    invoice = get_object_or_404(
        Invoice.objects.select_related('business', 'customer'),
        pk=invoice_id,
        customer=customer
    )
    
    items = invoice.line_items.all()
    
    return render(request, 'customer_portal/invoice_detail.html', {
        'customer': customer,
        'invoice': invoice,
        'items': items,
    })


@require_http_methods(["GET"])
def portal_estimates(request):
    """Customer's estimate list."""
    customer = _get_customer_from_session(request)
    if not customer:
        return redirect('customer_portal:login')
    
    estimates = Estimate.objects.filter(customer=customer).order_by('-created_at')
    
    return render(request, 'customer_portal/estimates.html', {
        'customer': customer,
        'estimates': estimates,
    })


@require_http_methods(["GET"])
def portal_estimate_detail(request, estimate_id):
    """Customer's estimate detail."""
    customer = _get_customer_from_session(request)
    if not customer:
        return redirect('customer_portal:login')
    
    estimate = get_object_or_404(
        Estimate.objects.select_related('business', 'customer'),
        pk=estimate_id,
        customer=customer
    )
    
    items = estimate.line_items.all()
    images = estimate.images.all()
    
    return render(request, 'customer_portal/estimate_detail.html', {
        'customer': customer,
        'estimate': estimate,
        'items': items,
        'images': images,
    })


@require_http_methods(["GET"])
def portal_jobs(request):
    """Customer's job history."""
    customer = _get_customer_from_session(request)
    if not customer:
        return redirect('customer_portal:login')
    
    jobs = Job.objects.filter(
        property__customer=customer
    ).select_related('property', 'assigned_to', 'assigned_crew').order_by('-scheduled_date')
    
    return render(request, 'customer_portal/jobs.html', {
        'customer': customer,
        'jobs': jobs,
    })

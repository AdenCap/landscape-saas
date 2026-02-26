"""Referral Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import Referral
import secrets


@role_required("owner")
def referral_list(request):
    """List all referrals."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    referrals = Referral.objects.filter(business=business).order_by('-created_at')
    
    # Stats
    total_referrals = referrals.count()
    converted = referrals.filter(status='converted').count()
    total_rewards = sum(r.reward_amount or 0 for r in referrals.filter(reward_paid=True))
    
    return render(request, 'referrals/referral_list.html', {
        'referrals': referrals,
        'total_referrals': total_referrals,
        'converted': converted,
        'total_rewards': total_rewards,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def referral_create(request):
    """Create a referral."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    if request.method == 'POST':
        referrer_id = request.POST.get('referrer')
        if not referrer_id:
            messages.error(request, "Please select a referrer.")
            return render(request, 'referrals/referral_form.html', {
                'action': 'Create',
                'customers': business.customers.all(),
            })
        
        from customers.models import Customer
        referrer = get_object_or_404(Customer, pk=referrer_id, business=business)
        
        referral_code = secrets.token_urlsafe(8).upper()[:10]
        # Ensure unique
        while Referral.objects.filter(referral_code=referral_code).exists():
            referral_code = secrets.token_urlsafe(8).upper()[:10]
        
        referral = Referral.objects.create(
            business=business,
            referrer=referrer,
            referred_name=request.POST.get('referred_name', ''),
            referred_email=request.POST.get('referred_email', ''),
            referred_phone=request.POST.get('referred_phone', ''),
            referral_code=referral_code,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f"Referral created with code: {referral.referral_code}")
        return redirect('referrals:referral_detail', referral_id=referral.id)
    
    from customers.models import Customer
    return render(request, 'referrals/referral_form.html', {
        'action': 'Create',
        'customers': business.customers.all() if business else [],
    })


@role_required("owner")
def referral_detail(request, referral_id):
    """Referral detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    referral = get_object_or_404(Referral, pk=referral_id, business=business)
    
    return render(request, 'referrals/referral_detail.html', {
        'referral': referral,
    })

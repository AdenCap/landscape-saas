"""Review Views."""
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import Review


@role_required("owner")
def review_list(request):
    """List all reviews."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    reviews = Review.objects.filter(business=business).order_by('-created_at')
    
    # Calculate average rating
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    return render(request, 'reviews/review_list.html', {
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
    })


@role_required("owner")
def review_detail(request, review_id):
    """Review detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    review = get_object_or_404(Review, pk=review_id, business=business)
    
    return render(request, 'reviews/review_detail.html', {
        'review': review,
    })

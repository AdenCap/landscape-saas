"""Survey Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Avg
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import Survey
import secrets


@role_required("owner")
def survey_list(request):
    """List all surveys."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    surveys = Survey.objects.filter(business=business).order_by('-completed_at')
    
    # Calculate average satisfaction
    avg_satisfaction = surveys.aggregate(models.Avg('overall_satisfaction'))['overall_satisfaction__avg'] or 0
    
    return render(request, 'surveys/survey_list.html', {
        'surveys': surveys,
        'avg_satisfaction': round(avg_satisfaction, 1),
    })


@role_required("owner")
def survey_detail(request, survey_id):
    """Survey detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    survey = get_object_or_404(Survey, pk=survey_id, business=business)
    
    return render(request, 'surveys/survey_detail.html', {
        'survey': survey,
    })


@require_http_methods(["GET", "POST"])
def survey_respond(request, token):
    """Public survey response form."""
    # In production, token would link to a survey invitation
    # For now, simplified version
    if request.method == 'POST':
        # Create survey response
        # This would normally be linked via token
        messages.success(request, "Thank you for your feedback!")
        return redirect('/')
    
    return render(request, 'surveys/survey_form.html')

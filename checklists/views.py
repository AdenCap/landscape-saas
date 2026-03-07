from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ChecklistTemplate


@login_required
def hub(request):
    biz = request.user.business
    templates = ChecklistTemplate.objects.filter(business=biz, is_active=True)
    return render(request, "checklists/hub.html", {
        "templates": templates,
    })

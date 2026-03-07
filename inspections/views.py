from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import module_required
from .models import InspectionTemplate, Inspection


@login_required
@module_required("inspections")
def hub(request):
    biz = request.user.business
    inspections = Inspection.objects.filter(business=biz).select_related("template", "inspector")
    templates = InspectionTemplate.objects.filter(business=biz, is_active=True)
    return render(request, "inspections/hub.html", {
        "inspections": inspections,
        "templates": templates,
    })

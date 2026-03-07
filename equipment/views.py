from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Equipment


@login_required
def hub(request):
    biz = request.user.business
    equipment_list = Equipment.objects.filter(business=biz).select_related("customer", "property")
    return render(request, "equipment/hub.html", {
        "equipment_list": equipment_list,
    })

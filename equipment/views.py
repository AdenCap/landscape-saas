from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import module_required
from .models import Equipment


@login_required
@module_required("equipment")
def hub(request):
    biz = request.user.business
    equipment_list = Equipment.objects.filter(business=biz).select_related("customer", "service_property")
    return render(request, "equipment/hub.html", {
        "equipment_list": equipment_list,
    })

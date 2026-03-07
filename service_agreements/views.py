from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import module_required
from .models import ServiceAgreement


@login_required
@module_required("service_agreements")
def hub(request):
    biz = request.user.business
    agreements = ServiceAgreement.objects.filter(business=biz).select_related("customer")
    return render(request, "service_agreements/hub.html", {
        "agreements": agreements,
    })

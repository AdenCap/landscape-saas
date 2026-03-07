from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ServiceAgreement


@login_required
def hub(request):
    biz = request.user.business
    agreements = ServiceAgreement.objects.filter(business=biz).select_related("customer")
    return render(request, "service_agreements/hub.html", {
        "agreements": agreements,
    })

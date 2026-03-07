from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404

from accounts.decorators import module_required
from .models import PricebookCategory, PricebookItem


@login_required
@module_required("pricebook")
def hub(request):
    biz = request.user.business
    categories = PricebookCategory.objects.filter(business=biz, is_active=True)
    items = PricebookItem.objects.filter(business=biz, is_active=True).select_related("category")
    return render(request, "pricebook/hub.html", {
        "categories": categories,
        "items": items,
    })

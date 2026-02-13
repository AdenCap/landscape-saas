from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required
from .models import Business
from .forms import BusinessSettingsForm


def _get_business(request):
    return getattr(request.user, "business", None)


@role_required("owner")
@require_http_methods(["GET", "POST"])
def business_settings(request):
    """Owner can configure email/phone used for client communication."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    if request.method == "POST":
        form = BusinessSettingsForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Business settings updated.")
            return redirect("business_settings")
    else:
        form = BusinessSettingsForm(instance=business)

    return render(request, "businesses/business_settings.html", {
        "form": form,
        "business": business,
    })

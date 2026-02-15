"""Crew management views for owners."""
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from .models import Crew
from .crew_forms import CrewForm


@role_required("owner")
def crew_list(request):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    crews = Crew.objects.filter(business=business).prefetch_related('members', 'crew_leader').order_by('name')
    return render(request, "jobs/crew_list.html", {"crews": crews})


@role_required("owner")
@require_http_methods(["GET", "POST"])
def crew_add(request):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    if request.method == "POST":
        form = CrewForm(request.POST, business=business)
        if form.is_valid():
            crew = form.save(commit=False)
            crew.business = business
            crew.save()
            form.save_m2m()
            messages.success(request, f"Crew '{crew.name}' created.")
            return redirect("crew_edit", crew_id=crew.id)
    else:
        form = CrewForm(business=business)

    return render(request, "jobs/crew_form.html", {"form": form, "title": "Add Crew"})


@role_required("owner")
@require_http_methods(["GET", "POST"])
def crew_edit(request, crew_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    crew = get_object_or_404(Crew, id=crew_id, business=business)

    if request.method == "POST":
        form = CrewForm(request.POST, instance=crew, business=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Crew updated.")
            return redirect("crew_edit", crew_id=crew.id)
    else:
        form = CrewForm(instance=crew, business=business)

    return render(request, "jobs/crew_form.html", {"form": form, "crew": crew, "title": "Edit Crew"})

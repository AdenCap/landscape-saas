from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChecklistTemplateForm, ChecklistTemplateItemFormSet
from .models import ChecklistTemplate


@login_required
def template_list(request):
    biz = request.user.business
    templates = (
        ChecklistTemplate.objects.filter(business=biz, is_active=True)
        .prefetch_related("items")
    )
    return render(request, "checklists/hub.html", {"templates": templates})


@login_required
def template_create(request):
    biz = request.user.business
    if request.method == "POST":
        form = ChecklistTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.business = biz
            template.save()
            formset = ChecklistTemplateItemFormSet(request.POST, instance=template)
            if formset.is_valid():
                formset.save()
                messages.success(request, f'Checklist template "{template.name}" created.')
                return redirect("checklists:template_list")
        else:
            formset = ChecklistTemplateItemFormSet(request.POST)
    else:
        form = ChecklistTemplateForm()
        formset = ChecklistTemplateItemFormSet()
    return render(request, "checklists/template_form.html", {
        "form": form,
        "formset": formset,
        "is_edit": False,
    })


@login_required
def template_edit(request, template_id):
    biz = request.user.business
    template = get_object_or_404(ChecklistTemplate, id=template_id, business=biz, is_active=True)
    if request.method == "POST":
        form = ChecklistTemplateForm(request.POST, instance=template)
        formset = ChecklistTemplateItemFormSet(request.POST, instance=template)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Checklist template "{template.name}" updated.')
            return redirect("checklists:template_list")
    else:
        form = ChecklistTemplateForm(instance=template)
        formset = ChecklistTemplateItemFormSet(instance=template)
    return render(request, "checklists/template_form.html", {
        "form": form,
        "formset": formset,
        "template": template,
        "is_edit": True,
    })


@login_required
def template_delete(request, template_id):
    biz = request.user.business
    template = get_object_or_404(ChecklistTemplate, id=template_id, business=biz)
    if request.method == "POST":
        template.is_active = False
        template.save(update_fields=["is_active"])
        messages.success(request, f'Checklist template "{template.name}" deleted.')
    return redirect("checklists:template_list")

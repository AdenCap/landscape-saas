from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Sum, Q, F
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from .models import Receipt, RevenueCategory
from .forms import ReceiptForm, PayScheduleForm
from .receipt_parser import parse_receipt_image


@role_required("owner")
def financials_dashboard(request):
    """Full company financials: revenue, invoices, projected revenue, expenses, labor."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view financials.")
        return redirect("/")

    today = timezone.localdate()
    year_start = today.replace(month=1, day=1)
    year_end = today.replace(year=today.year + 1, month=1, day=1)
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(day=31)
    else:
        month_end = (today.replace(month=today.month + 1, day=1)) - timedelta(days=1)

    from billing.models import Invoice
    from jobs.models import JobServiceItem

    # Revenue (paid invoices only) — using issue_date as the date of revenue
    inv_qs = Invoice.objects.filter(business=business, status="paid")
    revenue_today = inv_qs.filter(issue_date=today).aggregate(Sum("total"))["total__sum"] or Decimal("0")
    revenue_month = inv_qs.filter(issue_date__gte=month_start, issue_date__lte=month_end).aggregate(Sum("total"))["total__sum"] or Decimal("0")
    revenue_year = inv_qs.filter(issue_date__gte=year_start, issue_date__lt=year_end).aggregate(Sum("total"))["total__sum"] or Decimal("0")

    # Invoices past due (sent or draft, due_date < today)
    past_due = Invoice.objects.filter(
        business=business,
        status__in=("sent", "draft"),
        due_date__isnull=False,
        due_date__lt=today,
    ).select_related("customer").order_by("due_date")
    past_due_count = past_due.count()
    past_due_total = past_due.aggregate(Sum("total"))["total__sum"] or Decimal("0")

    # Invoices to be sent (draft)
    to_send = Invoice.objects.filter(business=business, status="draft").select_related("customer").order_by("issue_date")
    to_send_count = to_send.count()
    to_send_total = to_send.aggregate(Sum("total"))["total__sum"] or Decimal("0")

    # Projected revenue: sum of job service item totals for jobs scheduled this year (excluding skipped)
    projected_revenue = (
        JobServiceItem.objects.filter(
            job__property__customer__business=business,
            job__scheduled_date__year=today.year,
        )
        .exclude(job__status="skipped")
        .aggregate(tot=Sum(F("quantity") * F("unit_price")))["tot"]
        or Decimal("0")
    )

    # Total expenses for the year (receipts)
    total_expenses_year = (
        Receipt.objects.filter(business=business, receipt_date__year=today.year).aggregate(Sum("amount"))["amount__sum"]
        or Decimal("0")
    )

    # Labor expenses: receipts with category labor + timesheet labor (hours * hourly_rate)
    labor_receipts = (
        Receipt.objects.filter(business=business, category="labor", receipt_date__year=today.year).aggregate(Sum("amount"))["amount__sum"]
        or Decimal("0")
    )
    from time_tracking.models import TimeEntry
    year_entries = TimeEntry.objects.filter(
        user__business=business,
        clock_out__isnull=False,
        clock_in__date__gte=year_start,
        clock_in__date__lt=year_end,
    ).select_related("user")
    labor_timesheet = Decimal("0")
    for e in year_entries:
        rate = (e.user.hourly_rate or Decimal("0"))
        mins = e.duration_minutes or 0
        labor_timesheet += Decimal(str(mins)) / Decimal("60") * rate
    labor_expenses_year = labor_receipts + labor_timesheet

    # Pay schedule form (for payroll balance on dashboard)
    pay_schedule_form = PayScheduleForm(instance=business)
    if request.method == "POST" and request.POST.get("form_type") == "pay_schedule":
        pay_schedule_form = PayScheduleForm(request.POST, instance=business)
        if pay_schedule_form.is_valid():
            business = pay_schedule_form.save(commit=False)
            freq = pay_schedule_form.cleaned_data.get("pay_frequency")
            if freq == "custom_dates":
                business.pay_specific_days = pay_schedule_form.cleaned_data.get("pay_specific_days_parsed") or []
            else:
                business.pay_specific_days = None
            business.save()
            messages.success(request, "Pay schedule updated.")
            return redirect("financials:dashboard")

    return render(request, "financials/dashboard.html", {
        "revenue_today": revenue_today,
        "revenue_month": revenue_month,
        "revenue_year": revenue_year,
        "past_due_invoices": past_due[:10],
        "past_due_count": past_due_count,
        "past_due_total": past_due_total,
        "to_send_invoices": to_send[:10],
        "to_send_count": to_send_count,
        "to_send_total": to_send_total,
        "projected_revenue": projected_revenue,
        "total_expenses_year": total_expenses_year,
        "labor_expenses_year": labor_expenses_year,
        "today": today,
        "pay_schedule_form": pay_schedule_form,
    })


@role_required("owner")
def revenue_breakdown(request):
    """Deeper dive: revenue by category (owner-defined, e.g. Mowing, Fertilizing)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view financials.")
        return redirect("/")

    from billing.models import Invoice, InvoiceLineItem

    year = request.GET.get("year", "").strip()
    today = timezone.localdate()
    if year and year.isdigit():
        year = int(year)
    else:
        year = today.year
    year_start = today.replace(year=year, month=1, day=1)
    year_end = today.replace(year=year + 1, month=1, day=1)

    # Paid invoices in period
    paid_invoices = Invoice.objects.filter(
        business=business,
        status="paid",
        issue_date__gte=year_start,
        issue_date__lt=year_end,
    ).prefetch_related("line_items__revenue_category")

    # Sum line_total per category (and uncategorized)
    category_totals = {}
    uncategorized_total = Decimal("0")
    for inv in paid_invoices:
        for item in inv.line_items.all():
            amt = item.line_total
            cat = item.revenue_category
            if cat:
                category_totals[cat] = category_totals.get(cat, Decimal("0")) + amt
            else:
                uncategorized_total += amt

    # Sort categories by sort_order/name; build list with name, amount, pct
    categories_ordered = list(RevenueCategory.objects.filter(business=business).order_by("sort_order", "name"))
    breakdown = []
    for cat in categories_ordered:
        amt = category_totals.get(cat, Decimal("0"))
        breakdown.append({"name": cat.name, "amount": amt})
    if uncategorized_total:
        breakdown.append({"name": "Uncategorized", "amount": uncategorized_total})
    total_revenue = sum(b["amount"] for b in breakdown)
    for b in breakdown:
        b["pct"] = (float(b["amount"]) / float(total_revenue) * 100) if total_revenue else 0

    return render(request, "financials/revenue_breakdown.html", {
        "breakdown": breakdown,
        "total_revenue": total_revenue,
        "year": year,
        "years": [today.year, today.year - 1, today.year - 2],
    })


@role_required("owner")
def revenue_categories_list(request):
    """Manage revenue categories and assign services to them."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    from pricing.models import ServiceTemplate

    categories = RevenueCategory.objects.filter(business=business).order_by("sort_order", "name")
    services = ServiceTemplate.objects.filter(business=business).select_related("revenue_category").order_by("name")
    return render(request, "financials/revenue_categories.html", {
        "categories": categories,
        "services": services,
    })


@role_required("owner")
@require_http_methods(["POST"])
def revenue_category_assign(request):
    """Assign a revenue category to a service (AJAX or form POST)."""
    business = _get_business(request)
    if not business:
        return JsonResponse({"ok": False, "error": "No business"}, status=403)
    from pricing.models import ServiceTemplate
    service_id = request.POST.get("service_id")
    category_id = request.POST.get("category_id")
    try:
        service = ServiceTemplate.objects.get(id=service_id, business=business)
    except (ServiceTemplate.DoesNotExist, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid service"}, status=400)
    if category_id:
        try:
            cat = RevenueCategory.objects.get(id=category_id, business=business)
        except (RevenueCategory.DoesNotExist, ValueError):
            return JsonResponse({"ok": False, "error": "Invalid category"}, status=400)
        service.revenue_category = cat
    else:
        service.revenue_category = None
    service.save()
    return redirect("financials:revenue_categories")


@role_required("owner")
@require_http_methods(["GET", "POST"])
def revenue_category_add(request):
    """Add a new revenue category."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Name is required.")
            return redirect("financials:revenue_category_add")
        if RevenueCategory.objects.filter(business=business, name__iexact=name).exists():
            messages.error(request, f"A category named '{name}' already exists.")
            return redirect("financials:revenue_category_add")
        RevenueCategory.objects.create(business=business, name=name, sort_order=RevenueCategory.objects.filter(business=business).count())
        messages.success(request, f"Category '{name}' added.")
        return redirect("financials:revenue_categories")
    return render(request, "financials/revenue_category_form.html", {"title": "Add revenue category"})


@role_required("owner")
@require_http_methods(["GET", "POST"])
def revenue_category_edit(request, category_id):
    """Edit a revenue category."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    cat = get_object_or_404(RevenueCategory, id=category_id, business=business)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Name is required.")
            return redirect("financials:revenue_category_edit", category_id=cat.id)
        if RevenueCategory.objects.filter(business=business, name__iexact=name).exclude(id=cat.id).exists():
            messages.error(request, f"A category named '{name}' already exists.")
            return redirect("financials:revenue_category_edit", category_id=cat.id)
        cat.name = name
        cat.save()
        messages.success(request, "Category updated.")
        return redirect("financials:revenue_categories")
    return render(request, "financials/revenue_category_form.html", {"title": "Edit revenue category", "category": cat})


@role_required("owner")
@require_POST
def revenue_category_delete(request, category_id):
    """Delete a revenue category."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    cat = get_object_or_404(RevenueCategory, id=category_id, business=business)
    name = cat.name
    cat.delete()
    messages.success(request, f"Category '{name}' removed.")
    return redirect("financials:revenue_categories")


@role_required("owner")
def receipt_list(request):
    """Financials hub: list all receipts with filters and summary."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view financials.")
        return redirect("/")

    qs = Receipt.objects.filter(business=business).select_related("job", "job__property", "job__property__customer", "uploaded_by")

    # Filters
    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)
    job_id = request.GET.get("job", "").strip()
    if job_id:
        qs = qs.filter(job_id=job_id)
    year = request.GET.get("year", "").strip()
    if year:
        qs = qs.filter(receipt_date__year=int(year))

    receipts = qs.order_by("-receipt_date", "-created_at")[:500]
    total = qs.aggregate(Sum("amount"))["amount__sum"] or 0

    return render(request, "financials/receipt_list.html", {
        "receipts": receipts,
        "total": total,
        "category": category,
        "job_id": job_id,
        "year": year,
        "receipt_categories": Receipt.CATEGORY_CHOICES,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def receipt_upload(request, job_id=None):
    """Upload a receipt (standalone or for a specific job)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to upload receipts.")
        return redirect("/")

    job = None
    if job_id:
        from jobs.models import Job
        job = get_object_or_404(Job, id=job_id, property__customer__business=business)

    if request.method == "POST":
        form = ReceiptForm(
            request.POST,
            request.FILES,
            business=business,
            for_job=job,
        )
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.business = business
            receipt.uploaded_by = request.user
            if job:
                receipt.job = job
            receipt.save()
            messages.success(request, "Receipt uploaded successfully.")
            if job:
                return redirect("job_detail", job_id=job.id)
            return redirect("financials:receipt_list")
    else:
        form = ReceiptForm(business=business, for_job=job)

    return render(request, "financials/receipt_upload.html", {
        "form": form,
        "job": job,
    })


@role_required("owner")
@require_http_methods(["POST"])
def parse_receipt(request):
    """Parse an uploaded receipt image and return extracted date, vendor, amount as JSON."""
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file"}, status=400)

    allowed = ("image/jpeg", "image/png", "image/gif", "image/webp")
    if file.content_type not in allowed:
        return JsonResponse({"error": "Only image files (JPEG, PNG, GIF, WebP) are supported for parsing."}, status=400)

    try:
        data = parse_receipt_image(file)
        out = {
            "receipt_date": data["receipt_date"].isoformat() if data["receipt_date"] else None,
            "vendor": data["vendor"] or "",
            "amount": str(data["amount"]) if data["amount"] is not None else None,
        }
        return JsonResponse(out)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@role_required("owner", "crew")
@require_POST
def job_add_material_cost(request, job_id):
    """Add a material cost (with optional receipt) to a job from the job detail page."""
    from jobs.models import Job
    job = get_object_or_404(Job, id=job_id, property__customer__business=getattr(request.user, "business", None))
    business = job.property.customer.business
    form = ReceiptForm(request.POST, request.FILES, business=business, for_job=job)
    if form.is_valid():
        receipt = form.save(commit=False)
        receipt.business = business
        receipt.job = job
        receipt.uploaded_by = request.user
        receipt.save()
        messages.success(request, "Material cost added.")
    else:
        for _list in form.errors.values():
            for msg in _list:
                messages.error(request, msg)
    return redirect("job_detail", job_id=job.id)


@role_required("owner")
def receipt_download(request, receipt_id):
    """Serve the receipt file for view/download."""
    business = _get_business(request)
    if not business:
        raise Http404
    receipt = get_object_or_404(Receipt, id=receipt_id, business=business)
    if not receipt.file:
        raise Http404
    try:
        return FileResponse(receipt.file.open("rb"), as_attachment=True, filename=receipt.file.name.split("/")[-1])
    except Exception:
        raise Http404


@role_required("owner")
@require_POST
def receipt_delete(request, receipt_id):
    """Delete a receipt (and its file)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    receipt = get_object_or_404(Receipt, id=receipt_id, business=business)
    if receipt.file:
        receipt.file.delete(save=False)
    receipt.delete()
    messages.success(request, "Receipt deleted.")
    return redirect("financials:receipt_list")

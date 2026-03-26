from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Sum, Q, F, Count
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from .models import Receipt, RevenueCategory
from .forms import ReceiptForm, PayScheduleForm
from .receipt_parser import parse_receipt_image


@role_required("owner")
def financials_dashboard(request):
    """Full company financials: KPIs, charts, overdue aging, drafts."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view financials.")
        return redirect("/")

    today = timezone.localdate()
    year_start = today.replace(month=1, day=1)
    year_end = today.replace(year=today.year + 1, month=1, day=1)
    month_start = today.replace(day=1)

    from billing.models import Invoice
    from jobs.models import JobServiceItem
    from time_tracking.models import TimeEntry
    from .models import OverheadExpense, EquipmentAsset, VehicleAsset
    import calendar as cal_mod
    from django.db.models import DecimalField
    from django.db.models.functions import Coalesce

    inv_qs = Invoice.objects.filter(business=business, status="paid")

    # --- KPI: Revenue this month ---
    revenue_month = inv_qs.filter(
        issue_date__gte=month_start
    ).aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"]

    # --- KPI: Revenue last month (for comparison) ---
    if today.month == 1:
        last_month_start = today.replace(year=today.year - 1, month=12, day=1)
    else:
        last_month_start = today.replace(month=today.month - 1, day=1)
    last_month_end = month_start - timedelta(days=1)
    revenue_last_month = inv_qs.filter(
        issue_date__gte=last_month_start, issue_date__lte=last_month_end
    ).aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"]

    # --- KPI: Revenue this year ---
    revenue_year = inv_qs.filter(
        issue_date__gte=year_start, issue_date__lt=year_end
    ).aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"]

    # --- KPI: Expenses this month ---
    expenses_month = Receipt.objects.filter(
        business=business, receipt_date__gte=month_start
    ).aggregate(total=Coalesce(Sum("amount"), Decimal("0"), output_field=DecimalField()))["total"]

    # Labor cost this month
    month_entries = TimeEntry.objects.filter(
        user__business=business, clock_out__isnull=False,
        clock_in__date__gte=month_start
    ).select_related("user")
    labor_month = Decimal("0")
    for e in month_entries:
        rate = e.user.hourly_rate or Decimal("0")
        mins = e.duration_minutes or 0
        labor_month += Decimal(str(mins)) / Decimal("60") * rate
    total_costs_month = expenses_month + labor_month

    # --- KPI: Profit this month ---
    profit_month = revenue_month - total_costs_month

    # --- KPI: Outstanding AR ---
    ar_outstanding = Invoice.objects.filter(
        business=business, status="sent"
    ).aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField())
    )["total"]

    # --- KPI: Overdue ---
    overdue_qs = Invoice.objects.filter(
        business=business, status="sent", due_date__isnull=False, due_date__lt=today
    )
    overdue_count = overdue_qs.count()
    overdue_total = overdue_qs.aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField())
    )["total"]

    # --- Overdue aging ---
    day_30 = today - timedelta(days=30)
    day_60 = today - timedelta(days=60)
    aging_0_30 = Invoice.objects.filter(business=business, status="sent", due_date__isnull=False, due_date__gte=day_30, due_date__lt=today).aggregate(count=Count("id"), total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField()))
    aging_30_60 = Invoice.objects.filter(business=business, status="sent", due_date__isnull=False, due_date__gte=day_60, due_date__lt=day_30).aggregate(count=Count("id"), total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField()))
    aging_60_plus = Invoice.objects.filter(business=business, status="sent", due_date__isnull=False, due_date__lt=day_60).aggregate(count=Count("id"), total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField()))

    # --- Chart: Monthly Revenue & Profit (last 6 months) ---
    monthly_labels = []
    monthly_revenue = []
    monthly_profit = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        monthly_labels.append(cal_mod.month_abbr[m])
        first_day = today.replace(year=y, month=m, day=1)
        if m == 12:
            last_day = today.replace(year=y + 1, month=1, day=1)
        else:
            last_day = today.replace(year=y, month=m + 1, day=1)
        rev = inv_qs.filter(issue_date__gte=first_day, issue_date__lt=last_day).aggregate(
            total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField())
        )["total"]
        exp = Receipt.objects.filter(business=business, receipt_date__gte=first_day, receipt_date__lt=last_day).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0"), output_field=DecimalField())
        )["total"]
        monthly_revenue.append(float(rev))
        monthly_profit.append(float(rev - exp))

    # --- Chart: Expense breakdown ---
    overhead_annual = sum(e.annual_cost for e in OverheadExpense.objects.filter(business=business, active=True))
    equipment_annual = sum(eq.annual_cost for eq in EquipmentAsset.objects.filter(business=business, active=True))
    vehicle_annual = sum(v.annual_cost for v in VehicleAsset.objects.filter(business=business, active=True))
    labor_year = Receipt.objects.filter(business=business, category="labor", receipt_date__year=today.year).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0"), output_field=DecimalField())
    )["total"]
    # Add timesheet labor
    year_entries = TimeEntry.objects.filter(
        user__business=business, clock_out__isnull=False,
        clock_in__date__gte=year_start, clock_in__date__lt=year_end
    ).select_related("user")
    for e in year_entries:
        rate = e.user.hourly_rate or Decimal("0")
        mins = e.duration_minutes or 0
        labor_year += Decimal(str(mins)) / Decimal("60") * rate
    expense_labels = ['Overhead', 'Equipment', 'Vehicles', 'Labor']
    expense_values = [float(overhead_annual), float(equipment_annual), float(vehicle_annual), float(labor_year)]

    # --- Drafts to send ---
    drafts = Invoice.objects.filter(business=business, status="draft").select_related("customer").order_by("issue_date")[:8]
    drafts_count = Invoice.objects.filter(business=business, status="draft").count()
    drafts_total = Invoice.objects.filter(business=business, status="draft").aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DecimalField())
    )["total"]

    # --- Overdue invoices list ---
    overdue_invoices = overdue_qs.select_related("customer").order_by("due_date")[:8]

    # Revenue trend indicator
    if revenue_last_month and revenue_last_month > 0:
        revenue_change_pct = round(((revenue_month - revenue_last_month) / revenue_last_month) * 100, 1)
    else:
        revenue_change_pct = 0

    return render(request, "financials/dashboard.html", {
        "today": today,
        "revenue_month": revenue_month,
        "revenue_last_month": revenue_last_month,
        "revenue_year": revenue_year,
        "revenue_change_pct": revenue_change_pct,
        "profit_month": profit_month,
        "ar_outstanding": ar_outstanding,
        "overdue_count": overdue_count,
        "overdue_total": overdue_total,
        "aging_0_30": aging_0_30,
        "aging_30_60": aging_30_60,
        "aging_60_plus": aging_60_plus,
        "overdue_invoices": overdue_invoices,
        "drafts": drafts,
        "drafts_count": drafts_count,
        "drafts_total": drafts_total,
        "monthly_labels": monthly_labels,
        "monthly_revenue": monthly_revenue,
        "monthly_profit": monthly_profit,
        "expense_labels": expense_labels,
        "expense_values": expense_values,
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


@role_required("owner", "manager", "crew")
@require_POST
def job_add_material_cost(request, job_id):
    """Add a material cost (with optional receipt) to a job from the job detail page."""
    from jobs.models import Job
    job = get_object_or_404(Job, id=job_id, property__customer__business=getattr(request.user, "business", None))
    # Crew must be assigned to this job to add material costs
    if request.user.role == "crew":
        is_assigned = (
            job.assigned_to == request.user
            or (job.assigned_crew and (
                job.assigned_crew.crew_leader == request.user
                or job.assigned_crew.members.filter(id=request.user.id).exists()
            ))
        )
        if not is_assigned:
            messages.error(request, "You can only add costs to jobs you're assigned to.")
            return redirect("crew_today")
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
@require_http_methods(["GET", "POST"])
def receipt_edit(request, receipt_id):
    """Edit an existing receipt."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    receipt = get_object_or_404(Receipt, id=receipt_id, business=business)
    if request.method == "POST":
        form = ReceiptForm(request.POST, request.FILES, instance=receipt, business=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Receipt updated.")
            return redirect("financials:receipt_list")
    else:
        form = ReceiptForm(instance=receipt, business=business)
    return render(request, "financials/receipt_upload.html", {
        "form": form,
        "editing": True,
        "receipt": receipt,
    })


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


# ═══════════════════════════════════════════════
# Overhead & Business Cost Tracking
# ═══════════════════════════════════════════════

@role_required("owner", "manager")
def overhead_hub(request):
    """Main overhead tracking page: expenses, equipment, vehicles, labor burden, break-even."""
    business = _get_business(request)
    if not business:
        return redirect("/")

    from .models import OverheadExpense, EquipmentAsset, VehicleAsset, LaborBurdenConfig
    from accounts.models import User
    from decimal import Decimal

    expenses = OverheadExpense.objects.filter(business=business, active=True)
    equipment = EquipmentAsset.objects.filter(business=business, active=True)
    vehicles = VehicleAsset.objects.filter(business=business, active=True)
    burden, _ = LaborBurdenConfig.objects.get_or_create(business=business)

    # Totals
    total_overhead_annual = sum(e.annual_cost for e in expenses)
    total_equipment_annual = sum(eq.annual_cost for eq in equipment)
    total_vehicle_annual = sum(v.annual_cost for v in vehicles)
    grand_total_annual = total_overhead_annual + total_equipment_annual + total_vehicle_annual

    # Break-even calculation
    crew_employees = User.objects.filter(business=business, role="crew", is_active=True)
    crew_count = crew_employees.count()
    avg_wage = Decimal("0")
    if crew_count:
        wages = [e.hourly_rate for e in crew_employees if e.hourly_rate]
        avg_wage = sum(wages) / len(wages) if wages else Decimal("0")

    # Working assumptions (configurable later)
    weeks_per_year = 30  # typical mowing season
    hours_per_week = 40
    utilization_rate = Decimal("0.55")  # 55% billable

    total_paid_hours = crew_count * weeks_per_year * hours_per_week if crew_count else 0
    total_billable_hours = int(total_paid_hours * utilization_rate) if total_paid_hours else 0

    burden_pct = burden.total_burden_pct() / 100 if burden.total_burden_pct() else Decimal("0")
    burdened_wage = avg_wage * (1 + burden_pct)
    overhead_per_hour = Decimal(str(grand_total_annual)) / total_billable_hours if total_billable_hours else Decimal("0")
    breakeven_rate = burdened_wage + overhead_per_hour
    billing_rate_15 = breakeven_rate / Decimal("0.85") if breakeven_rate else Decimal("0")  # 15% profit
    billing_rate_20 = breakeven_rate / Decimal("0.80") if breakeven_rate else Decimal("0")  # 20% profit

    tab = request.GET.get("tab", "overview")

    return render(request, "financials/overhead_hub.html", {
        "expenses": expenses,
        "equipment": equipment,
        "vehicles": vehicles,
        "burden": burden,
        "total_overhead_annual": total_overhead_annual,
        "total_equipment_annual": total_equipment_annual,
        "total_vehicle_annual": total_vehicle_annual,
        "grand_total_annual": grand_total_annual,
        "grand_total_monthly": grand_total_annual / 12 if grand_total_annual else 0,
        "crew_count": crew_count,
        "avg_wage": avg_wage,
        "burdened_wage": burdened_wage,
        "burden_pct_display": burden.total_burden_pct(),
        "total_billable_hours": total_billable_hours,
        "overhead_per_hour": overhead_per_hour,
        "breakeven_rate": breakeven_rate,
        "billing_rate_15": billing_rate_15,
        "billing_rate_20": billing_rate_20,
        "weeks_per_year": weeks_per_year,
        "utilization_rate": int(utilization_rate * 100),
        "tab": tab,
        "expense_categories": OverheadExpense.CATEGORY_CHOICES,
        "expense_frequencies": OverheadExpense.FREQUENCY_CHOICES,
    })


@require_POST
@role_required("owner", "manager")
def overhead_expense_save(request):
    business = _get_business(request)
    if not business:
        return redirect("/")
    from .models import OverheadExpense
    pk = request.POST.get("pk")
    if pk:
        obj = get_object_or_404(OverheadExpense, id=pk, business=business)
    else:
        obj = OverheadExpense(business=business)
    obj.name = request.POST.get("name", "").strip()
    obj.category = request.POST.get("category", "other")
    obj.amount = request.POST.get("amount") or 0
    obj.frequency = request.POST.get("frequency", "monthly")
    obj.notes = request.POST.get("notes", "")
    obj.save()
    messages.success(request, f"Expense '{obj.name}' saved.")
    return redirect("financials:overhead_hub")


@require_POST
@role_required("owner", "manager")
def overhead_expense_delete(request, pk):
    business = _get_business(request)
    obj = get_object_or_404(OverheadExpense, id=pk, business=business)
    obj.delete()
    messages.success(request, "Expense deleted.")
    return redirect("financials:overhead_hub")


@require_POST
@role_required("owner", "manager")
def equipment_save(request):
    business = _get_business(request)
    if not business:
        return redirect("/")
    from .models import EquipmentAsset
    pk = request.POST.get("pk")
    if pk:
        obj = get_object_or_404(EquipmentAsset, id=pk, business=business)
    else:
        obj = EquipmentAsset(business=business)
    obj.name = request.POST.get("name", "").strip()
    obj.purchase_price = request.POST.get("purchase_price") or 0
    obj.salvage_value = request.POST.get("salvage_value") or 0
    obj.useful_life_hours = request.POST.get("useful_life_hours") or 2500
    obj.annual_maintenance = request.POST.get("annual_maintenance") or 0
    obj.annual_insurance = request.POST.get("annual_insurance") or 0
    obj.fuel_cost_per_hour = request.POST.get("fuel_cost_per_hour") or 0
    obj.hours_per_year = request.POST.get("hours_per_year") or 1000
    obj.notes = request.POST.get("notes", "")
    obj.save()
    messages.success(request, f"Equipment '{obj.name}' saved.")
    return redirect("financials:overhead_hub")


@require_POST
@role_required("owner", "manager")
def equipment_delete(request, pk):
    business = _get_business(request)
    obj = get_object_or_404(EquipmentAsset, id=pk, business=business)
    obj.delete()
    messages.success(request, "Equipment deleted.")
    return redirect("financials:overhead_hub")


@require_POST
@role_required("owner", "manager")
def vehicle_save(request):
    business = _get_business(request)
    if not business:
        return redirect("/")
    from .models import VehicleAsset
    pk = request.POST.get("pk")
    if pk:
        obj = get_object_or_404(VehicleAsset, id=pk, business=business)
    else:
        obj = VehicleAsset(business=business)
    obj.name = request.POST.get("name", "").strip()
    obj.monthly_payment = request.POST.get("monthly_payment") or 0
    obj.annual_insurance = request.POST.get("annual_insurance") or 0
    obj.annual_registration = request.POST.get("annual_registration") or 0
    obj.avg_mpg = request.POST.get("avg_mpg") or 15
    obj.fuel_price_per_gallon = request.POST.get("fuel_price_per_gallon") or 3.50
    obj.estimated_annual_miles = request.POST.get("estimated_annual_miles") or 20000
    obj.annual_maintenance = request.POST.get("annual_maintenance") or 0
    obj.notes = request.POST.get("notes", "")
    obj.save()
    messages.success(request, f"Vehicle '{obj.name}' saved.")
    return redirect("financials:overhead_hub")


@require_POST
@role_required("owner", "manager")
def vehicle_delete(request, pk):
    business = _get_business(request)
    obj = get_object_or_404(VehicleAsset, id=pk, business=business)
    obj.delete()
    messages.success(request, "Vehicle deleted.")
    return redirect("financials:overhead_hub")


@require_POST
@role_required("owner", "manager")
def burden_save(request):
    business = _get_business(request)
    if not business:
        return redirect("/")
    from .models import LaborBurdenConfig
    burden, _ = LaborBurdenConfig.objects.get_or_create(business=business)
    # Only save fields that have values — leave the rest null
    for field in ['fica_rate', 'futa_rate', 'suta_rate', 'workers_comp_rate',
                  'pto_rate', 'other_burden_rate']:
        val = request.POST.get(field, "").strip()
        setattr(burden, field, val if val else None)
    hi = request.POST.get("health_insurance_per_employee", "").strip()
    burden.health_insurance_per_employee = hi if hi else None
    burden.save()
    messages.success(request, "Labor burden updated.")
    return redirect("financials:overhead_hub")

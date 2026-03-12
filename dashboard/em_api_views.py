"""Employee Management hub AJAX endpoints.

All views return JsonResponse. Used by the modal system on /employee-management/.
"""
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from accounts.decorators import role_required
from accounts.forms import EmployeeCreateForm, EmployeeForm, EmployeePaymentForm
from accounts.models import EmployeePayment
from accounts.utils import get_business as _get_business
from jobs.crew_forms import CrewForm
from jobs.models import Crew
from time_tracking.models import TimeEntry

User = get_user_model()


def _biz_or_403(request):
    """Return business or 403 JsonResponse."""
    biz = _get_business(request)
    if not biz:
        return None, JsonResponse({"error": "No business"}, status=403)
    return biz, None


def _form_errors_json(form):
    """Convert Django form errors to a flat dict for the frontend."""
    errors = {}
    for field, error_list in form.errors.items():
        errors[field] = error_list[0] if error_list else ""
    return errors


# ── Employee endpoints ──────────────────────────────────────────────

@require_GET
@role_required("owner", "manager")
def em_employee_detail(request, user_id):
    """Return employee data as JSON for the edit modal."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    emp = get_object_or_404(User, id=user_id, business=biz)
    return JsonResponse({
        "id": emp.id,
        "username": emp.username,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "email": emp.email,
        "phone": emp.phone,
        "role": emp.role,
        "hourly_rate": str(emp.hourly_rate or ""),
        "color": emp.color or "",
        "is_active": emp.is_active,
        "address_line1": emp.address_line1,
        "address_line2": emp.address_line2,
        "city": emp.city,
        "state": emp.state,
        "postal_code": emp.postal_code,
    })


@require_POST
@role_required("owner", "manager")
def em_employee_add(request):
    """Create a new employee. Returns JSON {ok: true} or {errors: {...}}."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    form = EmployeeCreateForm(request.POST)
    if form.is_valid():
        user = form.save(commit=False)
        user.business = biz
        user.save()
        return JsonResponse({"ok": True, "id": user.id, "name": user.get_full_name() or user.username})
    return JsonResponse({"errors": _form_errors_json(form)}, status=400)


@require_POST
@role_required("owner", "manager")
def em_employee_edit(request, user_id):
    """Update employee profile. Returns JSON {ok: true} or {errors: {...}}."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    emp = get_object_or_404(User, id=user_id, business=biz)
    form = EmployeeForm(request.POST, instance=emp)
    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True})
    return JsonResponse({"errors": _form_errors_json(form)}, status=400)


@require_POST
@role_required("owner", "manager")
def em_employee_toggle_active(request, user_id):
    """Toggle employee is_active status."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    emp = get_object_or_404(User, id=user_id, business=biz)
    if emp.id == request.user.id:
        return JsonResponse({"error": "Cannot deactivate yourself"}, status=400)
    emp.is_active = not emp.is_active
    emp.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": emp.is_active})


@require_POST
@role_required("owner")
def em_employee_password(request, user_id):
    """Reset employee password."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    emp = get_object_or_404(User, id=user_id, business=biz)
    p1 = request.POST.get("new_password1", "").strip()
    p2 = request.POST.get("new_password2", "").strip()
    if not p1 or len(p1) < 8:
        return JsonResponse({"errors": {"new_password1": "Password must be at least 8 characters."}}, status=400)
    if p1 != p2:
        return JsonResponse({"errors": {"new_password2": "Passwords don't match."}}, status=400)
    emp.set_password(p1)
    emp.save()
    return JsonResponse({"ok": True})


# ── Crew endpoints ──────────────────────────────────────────────────

@require_GET
@role_required("owner", "manager")
def em_crew_detail(request, crew_id):
    """Return crew data as JSON for the edit modal."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    crew = get_object_or_404(Crew.objects.prefetch_related("members"), id=crew_id, business=biz)
    return JsonResponse({
        "id": crew.id,
        "name": crew.name,
        "color": crew.color or "#22c55e",
        "crew_leader": crew.crew_leader_id,
        "members": list(crew.members.values_list("id", flat=True)),
    })


@require_POST
@role_required("owner", "manager")
def em_crew_add(request):
    """Create a new crew."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    form = CrewForm(request.POST, business=biz)
    if form.is_valid():
        crew = form.save(commit=False)
        crew.business = biz
        crew.save()
        form.save_m2m()
        return JsonResponse({"ok": True, "id": crew.id, "name": crew.name})
    return JsonResponse({"errors": _form_errors_json(form)}, status=400)


@require_POST
@role_required("owner", "manager")
def em_crew_edit(request, crew_id):
    """Update a crew."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    crew = get_object_or_404(Crew, id=crew_id, business=biz)
    form = CrewForm(request.POST, instance=crew, business=biz)
    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True})
    return JsonResponse({"errors": _form_errors_json(form)}, status=400)


@require_POST
@role_required("owner", "manager")
def em_crew_delete(request, crew_id):
    """Delete a crew (only if no active jobs assigned)."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    crew = get_object_or_404(Crew, id=crew_id, business=biz)
    from jobs.models import Job
    active_jobs = Job.objects.filter(assigned_crew=crew).exclude(status__in=["completed", "cancelled"]).count()
    if active_jobs:
        return JsonResponse({"error": f"Cannot delete: {active_jobs} active job(s) assigned to this crew."}, status=400)
    crew.delete()
    return JsonResponse({"ok": True})


# ── Payroll endpoints ───────────────────────────────────────────────

@require_POST
@role_required("owner", "manager")
def em_payment_record(request):
    """Record a payment for a selected employee."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    employee_id = request.POST.get("employee")
    if not employee_id:
        return JsonResponse({"errors": {"employee": "Select an employee."}}, status=400)
    emp = get_object_or_404(User, id=employee_id, business=biz)
    form = EmployeePaymentForm(request.POST)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.employee = emp
        payment.business = biz
        payment.save()
        return JsonResponse({
            "ok": True,
            "id": payment.id,
            "amount": str(payment.amount),
            "employee_name": emp.get_full_name() or emp.username,
        })
    return JsonResponse({"errors": _form_errors_json(form)}, status=400)


@require_GET
@role_required("owner", "manager")
def em_payment_calculate(request):
    """Calculate pay for employee over a date range (approved hours * rate)."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    employee_id = request.GET.get("employee_id")
    start = request.GET.get("start")
    end = request.GET.get("end")
    if not employee_id or not start or not end:
        return JsonResponse({"error": "employee_id, start, and end are required"}, status=400)
    emp = get_object_or_404(User, id=employee_id, business=biz)
    rate = emp.hourly_rate or Decimal("0")
    entries = TimeEntry.objects.filter(
        user=emp, status="approved", clock_out__isnull=False,
        clock_in__date__gte=start, clock_in__date__lte=end,
    )
    total_minutes = sum(e.duration_minutes or 0 for e in entries)
    hours = Decimal(str(total_minutes)) / Decimal("60")
    amount = (hours * rate).quantize(Decimal("0.01"))
    return JsonResponse({
        "employee_name": emp.get_full_name() or emp.username,
        "hours": str(hours.quantize(Decimal("0.01"))),
        "rate": str(rate),
        "amount": str(amount),
    })


# ── Time entry endpoints ───────────────────────────────────────────

@require_GET
@role_required("owner", "manager")
def em_time_entries(request):
    """Return time entries as JSON (filtered by employee and date range)."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    employee_id = request.GET.get("employee_id")
    start = request.GET.get("start")
    end = request.GET.get("end")

    qs = TimeEntry.objects.filter(
        user__business_id=biz.id,
        clock_out__isnull=False,
    ).select_related("user").order_by("-clock_in")

    if employee_id:
        qs = qs.filter(user_id=employee_id)
    if start:
        qs = qs.filter(clock_in__date__gte=start)
    if end:
        qs = qs.filter(clock_in__date__lte=end)

    entries = []
    for e in qs[:200]:
        entries.append({
            "id": e.id,
            "user_id": e.user_id,
            "user_name": e.user.get_full_name() or e.user.username,
            "clock_in": e.clock_in.isoformat() if e.clock_in else None,
            "clock_out": e.clock_out.isoformat() if e.clock_out else None,
            "duration": e.duration_display,
            "duration_minutes": e.duration_minutes,
            "status": e.status,
        })
    return JsonResponse({"entries": entries})


@require_POST
@role_required("owner", "manager")
def em_time_entry_edit(request, entry_id):
    """Edit clock-in / clock-out on a time entry."""
    biz, err = _biz_or_403(request)
    if err:
        return err
    entry = get_object_or_404(
        TimeEntry.objects.filter(user__business_id=biz.id),
        id=entry_id,
    )
    clock_in_date = request.POST.get("clock_in_date")
    clock_in_time = request.POST.get("clock_in_time")
    clock_out_date = request.POST.get("clock_out_date")
    clock_out_time = request.POST.get("clock_out_time")

    errors = {}
    new_clock_in = None
    new_clock_out = None

    if clock_in_date and clock_in_time:
        try:
            new_clock_in = timezone.make_aware(
                datetime.strptime(f"{clock_in_date} {clock_in_time}", "%Y-%m-%d %H:%M")
            )
        except ValueError:
            errors["clock_in_date"] = "Invalid date/time format."
    else:
        errors["clock_in_date"] = "Clock-in date and time are required."

    if clock_out_date and clock_out_time:
        try:
            new_clock_out = timezone.make_aware(
                datetime.strptime(f"{clock_out_date} {clock_out_time}", "%Y-%m-%d %H:%M")
            )
        except ValueError:
            errors["clock_out_date"] = "Invalid date/time format."

    if new_clock_in and new_clock_out and new_clock_out <= new_clock_in:
        errors["clock_out_date"] = "Clock-out must be after clock-in."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    entry.clock_in = new_clock_in
    entry.clock_out = new_clock_out
    entry.save()
    return JsonResponse({"ok": True, "duration": entry.duration_display})

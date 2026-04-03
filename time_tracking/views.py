from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET

from accounts.decorators import role_required
from accounts.models import User
from .models import TimeEntry, TimeOffRequest, EmployeeSchedule, ScheduleChangeLog
from .forms import TimeOffRequestForm, EmployeeScheduleFormSet, TimeEntryEditForm


def _hours_from_minutes(minutes):
    """Convert minutes to decimal hours for cost calculation."""
    if minutes is None:
        return Decimal("0")
    return Decimal(str(minutes)) / Decimal("60")


@role_required("owner", "manager", "crew")
def clock_view(request):
    """Shows clock in/out status and allows punching."""
    user = request.user
    now = timezone.now()

    # Find the most recent open entry (clocked in, no clock_out)
    current_entry = TimeEntry.objects.filter(
        user=user, clock_out__isnull=True
    ).order_by('-clock_in').first()

    # Get today's entries for display
    today = now.date()
    today_entries = TimeEntry.objects.filter(
        user=user,
        clock_in__date=today,
    ).order_by('clock_in')

    today_minutes = sum(
        e.duration_minutes or 0
        for e in today_entries
    )
    today_hours_display = f"{today_minutes // 60}h {today_minutes % 60}m"

    return render(request, 'time_tracking/clock.html', {
        'current_entry': current_entry,
        'today_entries': today_entries,
        'today_minutes': today_minutes,
        'today_hours_display': today_hours_display,
    })


@require_POST
@role_required("owner", "manager", "crew")
def clock_in(request):
    kwargs = {"user": request.user, "clock_in": timezone.now()}
    # Capture GPS location if provided
    lat = request.POST.get("latitude", "").strip()
    lng = request.POST.get("longitude", "").strip()
    if lat and lng:
        try:
            kwargs["clock_in_latitude"] = float(lat)
            kwargs["clock_in_longitude"] = float(lng)
        except (ValueError, TypeError):
            pass
    TimeEntry.objects.create(**kwargs)

    # Notify owner(s) and managers
    try:
        from accounts.models import Notification
        from accounts.utils import get_business
        business = get_business(request)
        if business and request.user.role == "crew":
            now = timezone.localtime(timezone.now())
            hour = now.hour % 12 or 12
            ampm = "AM" if now.hour < 12 else "PM"
            time_str = f"{hour}:{now.minute:02d} {ampm}"
            name = request.user.get_full_name() or request.user.username
            loc_str = ""
            if lat and lng:
                loc_str = f" (GPS: {lat[:8]}, {lng[:9]})"
            msg = f"{name} clocked in at {time_str}{loc_str}"
            owners_managers = User.objects.filter(
                business=business, role__in=["owner", "manager"]
            ).exclude(id=request.user.id)
            for om in owners_managers:
                Notification.objects.create(
                    business=business,
                    from_user=request.user,
                    to_user=om,
                    message=msg,
                )
    except Exception:
        pass  # Don't let notification failure block clock-in

    messages.success(request, 'Clocked in successfully.')
    return redirect('time_clock')


@require_POST
@role_required("owner", "manager", "crew")
def clock_out(request):
    entry = TimeEntry.objects.filter(
        user=request.user, clock_out__isnull=True
    ).order_by('-clock_in').first()

    if entry:
        entry.clock_out = timezone.now()
        # Capture GPS location on clock out
        lat = request.POST.get("latitude", "").strip()
        lng = request.POST.get("longitude", "").strip()
        if lat and lng:
            try:
                entry.clock_out_latitude = float(lat)
                entry.clock_out_longitude = float(lng)
            except (ValueError, TypeError):
                pass
        entry.save()

        # Notify owner(s) and managers
        try:
            from accounts.models import Notification
            from accounts.utils import get_business
            business = get_business(request)
            if business and request.user.role == "crew":
                now = timezone.localtime(timezone.now())
                hour = now.hour % 12 or 12
                ampm = "AM" if now.hour < 12 else "PM"
                time_str = f"{hour}:{now.minute:02d} {ampm}"
                name = request.user.get_full_name() or request.user.username
                # Calculate duration
                dur = ""
                if entry.clock_in:
                    mins = int((entry.clock_out - entry.clock_in).total_seconds() / 60)
                    if mins >= 60:
                        dur = f" ({mins // 60}h {mins % 60}m)"
                    else:
                        dur = f" ({mins}m)"
                msg = f"{name} clocked out at {time_str}{dur}"
                owners_managers = User.objects.filter(
                    business=business, role__in=["owner", "manager"]
                ).exclude(id=request.user.id)
                for om in owners_managers:
                    Notification.objects.create(
                        business=business,
                        from_user=request.user,
                        to_user=om,
                        message=msg,
                    )
        except Exception:
            pass

        messages.success(request, 'Clocked out successfully.')
    else:
        messages.warning(request, 'No active clock-in found.')

    return redirect('time_clock')


@role_required("owner", "manager")
def timesheets_view(request):
    """Owner view: all employees' timesheets with weekly and yearly costs."""
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    year_start = today.replace(month=1, day=1)
    year_end = today.replace(year=today.year + 1, month=1, day=1)

    # Get all crew members (employees) - filter by business if owner has one
    crew_users = User.objects.filter(role='crew').order_by('username')
    if request.user.business_id:
        crew_users = crew_users.filter(business_id=request.user.business_id)

    employee_stats = []
    for user in crew_users:
        rate = user.hourly_rate or Decimal("0")

        # Week: only approved entries count for payroll
        week_entries = TimeEntry.objects.filter(
            user=user,
            status="approved",
            clock_out__isnull=False,
            clock_in__date__gte=week_start,
            clock_in__date__lt=week_end,
        )
        week_minutes = sum(e.duration_minutes or 0 for e in week_entries)
        week_hours = _hours_from_minutes(week_minutes)
        week_cost = week_hours * rate

        # Year: same logic
        year_entries = TimeEntry.objects.filter(
            user=user,
            status="approved",
            clock_out__isnull=False,
            clock_in__date__gte=year_start,
            clock_in__date__lt=year_end,
        )
        year_minutes = sum(e.duration_minutes or 0 for e in year_entries)
        year_hours = _hours_from_minutes(year_minutes)
        year_cost = year_hours * rate

        week_display = f"{week_minutes // 60}h {week_minutes % 60}m"
        year_display = f"{year_minutes // 60}h {year_minutes % 60}m"

        employee_stats.append({
            'user': user,
            'hourly_rate': rate,
            'week_minutes': week_minutes,
            'week_hours': week_hours,
            'week_display': week_display,
            'week_cost': week_cost,
            'year_minutes': year_minutes,
            'year_hours': year_hours,
            'year_display': year_display,
            'year_cost': year_cost,
        })

    total_week_cost = sum(s['week_cost'] for s in employee_stats)
    total_year_cost = sum(s['year_cost'] for s in employee_stats)

    # Count pending time entries (complete entries awaiting approval)
    pending_count = 0
    if request.user.business_id:
        pending_count = TimeEntry.objects.filter(
            user__business_id=request.user.business_id,
            status="pending_approval",
            clock_out__isnull=False,
        ).count()

    return render(request, 'time_tracking/timesheets.html', {
        'employee_stats': employee_stats,
        'week_start': week_start,
        'week_end': week_end,
        'year_start': year_start,
        'year_end': year_end,
        'total_week_cost': total_week_cost,
        'total_year_cost': total_year_cost,
        'pending_count': pending_count,
    })


@role_required("owner", "manager")
def time_entries_pending(request):
    """Owner: list time entries pending approval (complete punch pairs)."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    entries = (
        TimeEntry.objects.filter(
            user__business_id=business.id,
            status="pending_approval",
            clock_out__isnull=False,
        )
        .select_related("user")
        .order_by("-clock_in")
    )
    return render(request, "time_tracking/time_entries_pending.html", {
        "entries": entries,
    })


@require_POST
@role_required("owner", "manager")
def time_entry_approve(request, entry_id):
    """Owner approves a time entry so it counts for payroll."""
    business = _get_business(request)
    entry = get_object_or_404(
        TimeEntry.objects.filter(user__business_id=business.id),
        id=entry_id,
        status="pending_approval",
    )
    entry.status = "approved"
    entry.approved_at = timezone.now()
    entry.approved_by = request.user
    entry.save()
    messages.success(request, "Time entry approved.")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        from django.http import JsonResponse
        return JsonResponse({"status": "ok"})
    return redirect("time_entries_pending")


@require_POST
@role_required("owner", "manager")
def time_entry_reject(request, entry_id):
    """Owner rejects a time entry; it will not count for payroll."""
    business = _get_business(request)
    entry = get_object_or_404(
        TimeEntry.objects.filter(user__business_id=business.id),
        id=entry_id,
        status="pending_approval",
    )
    entry.status = "rejected"
    entry.approved_at = timezone.now()
    entry.approved_by = request.user
    entry.save()
    messages.success(request, "Time entry rejected.")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        from django.http import JsonResponse
        return JsonResponse({"status": "ok"})
    return redirect("time_entries_pending")


@role_required("owner", "manager")
def time_entry_edit(request, entry_id):
    """Owner manually adjusts clock-in/clock-out for a time entry."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    entry = get_object_or_404(
        TimeEntry.objects.filter(user__business_id=business.id).select_related("user"),
        id=entry_id,
    )
    if request.method == "POST":
        form = TimeEntryEditForm(request.POST, entry=entry)
        if form.is_valid():
            entry.clock_in = form.cleaned_data["_clock_in"]
            if form.cleaned_data.get("_clock_out") is not None:
                entry.clock_out = form.cleaned_data["_clock_out"]
            else:
                entry.clock_out = None
            entry.save()
            messages.success(request, "Time entry updated.")
            return redirect("time_entries_list")
    else:
        form = TimeEntryEditForm(entry=entry)
    return render(request, "time_tracking/time_entry_edit.html", {
        "form": form,
        "entry": entry,
    })


@role_required("owner", "manager")
def time_entries_list(request):
    """Owner: list time entries with filters, totals, and quick presets."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    from django.utils import timezone
    today = timezone.localdate()

    employees = User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name", "last_name", "username")
    employee_id = request.GET.get("employee_id")

    # Quick filter presets
    preset = request.GET.get("preset", "").strip()
    if preset == "this_week":
        start_date = today - timedelta(days=today.weekday())  # Monday
        end_date = today
    elif preset == "last_week":
        monday = today - timedelta(days=today.weekday())
        start_date = monday - timedelta(days=7)
        end_date = monday - timedelta(days=1)
    elif preset == "this_month":
        start_date = today.replace(day=1)
        end_date = today
    elif preset == "last_month":
        first_this_month = today.replace(day=1)
        end_date = first_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif preset == "all":
        start_date = None
        end_date = None
    else:
        # Custom date range from form, or default to this week
        start_str = request.GET.get("start", "")
        end_str = request.GET.get("end", "")
        from django.utils.dateparse import parse_date
        default_start = today - timedelta(days=today.weekday())  # Monday of this week
        if start_str:
            start_date = parse_date(start_str) or default_start
        else:
            start_date = default_start
        if end_str:
            end_date = parse_date(end_str) or today
        else:
            end_date = today
        if not start_str and not end_str:
            preset = "this_week"  # Show as active preset

    if employee_id:
        entries_qs = TimeEntry.objects.filter(user_id=employee_id, user__business_id=business.id)
    else:
        entries_qs = TimeEntry.objects.filter(user__business_id=business.id)
    entries_qs = entries_qs.select_related("user").order_by("-clock_in")

    if start_date:
        entries_qs = entries_qs.filter(clock_in__date__gte=start_date)
    if end_date:
        entries_qs = entries_qs.filter(clock_in__date__lte=end_date)

    # Calculate totals from ALL matching entries (not truncated)
    all_entries = list(entries_qs)
    entries = all_entries  # Show all — no artificial limit

    # Calculate period totals
    total_minutes = 0
    total_cost = Decimal("0")
    approved_minutes = 0
    approved_cost = Decimal("0")
    for e in all_entries:
        mins = e.duration_minutes or 0
        rate = e.user.hourly_rate or Decimal("0")
        cost = Decimal(str(mins)) / Decimal("60") * rate
        total_minutes += mins
        total_cost += cost
        if e.status == "approved":
            approved_minutes += mins
            approved_cost += cost

    total_hrs = total_minutes // 60
    total_mins_rem = total_minutes % 60
    total_display = f"{total_hrs}h {total_mins_rem}m" if total_hrs else f"{total_mins_rem}m"
    approved_hrs = approved_minutes // 60
    approved_mins_rem = approved_minutes % 60
    approved_display = f"{approved_hrs}h {approved_mins_rem}m" if approved_hrs else f"{approved_mins_rem}m"

    selected_employee = None
    if employee_id:
        try:
            selected_employee = User.objects.get(pk=employee_id, business=business)
        except User.DoesNotExist:
            selected_employee = None

    return render(request, "time_tracking/time_entries_list.html", {
        "entries": entries,
        "employees": employees,
        "selected_employee": selected_employee,
        "start_date": start_date,
        "end_date": end_date,
        "preset": preset,
        "total_display": total_display,
        "total_cost": total_cost.quantize(Decimal("0.01")),
        "approved_display": approved_display,
        "approved_cost": approved_cost.quantize(Decimal("0.01")),
        "entry_count": len(entries),
    })


@role_required("owner", "manager")
def time_entry_add(request):
    """Owner manually adds a time entry for an employee who forgot to clock in."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    employees = User.objects.filter(business=business, role__in=["crew", "owner"]).order_by("first_name")

    if request.method == "POST":
        employee_id = request.POST.get("employee_id")
        date_str = request.POST.get("date", "").strip()
        clock_in_str = request.POST.get("clock_in_time", "").strip()
        clock_out_str = request.POST.get("clock_out_time", "").strip()
        notes = request.POST.get("notes", "").strip()

        if not employee_id or not date_str or not clock_in_str:
            messages.error(request, "Employee, date, and clock-in time are required.")
            return redirect("time_entry_add")

        from datetime import datetime as dt, date as dt_date, time as dt_time
        try:
            entry_date = dt_date.fromisoformat(date_str)
            ci_parts = clock_in_str.split(":")
            ci_time = dt_time(int(ci_parts[0]), int(ci_parts[1]))
            clock_in_dt = timezone.make_aware(dt.combine(entry_date, ci_time))

            clock_out_dt = None
            if clock_out_str:
                co_parts = clock_out_str.split(":")
                co_time = dt_time(int(co_parts[0]), int(co_parts[1]))
                clock_out_dt = timezone.make_aware(dt.combine(entry_date, co_time))
        except (ValueError, TypeError, IndexError):
            messages.error(request, "Invalid date or time format.")
            return redirect("time_entry_add")

        employee = get_object_or_404(User, id=employee_id, business=business)
        entry = TimeEntry.objects.create(
            user=employee,
            clock_in=clock_in_dt,
            clock_out=clock_out_dt,
            status="approved",
            approved_at=timezone.now(),
            approved_by=request.user,
        )
        dur = entry.duration_display if entry.clock_out else "open"
        messages.success(request, f"Time entry added for {employee.get_full_name() or employee.username} ({dur}).")
        return redirect("time_entries_list")

    return render(request, "time_tracking/time_entry_add.html", {
        "employees": employees,
    })


@role_required("owner", "manager")
def pay_period_view(request):
    """View current pay period timesheets with totals, edit/delete actions."""
    business = _get_business(request)
    if not business:
        return redirect("/")

    from datetime import date as dt_date
    today = timezone.localdate()

    # Determine pay period dates
    pay_freq = business.pay_frequency or "biweekly"
    if pay_freq == "weekly":
        period_start = today - timedelta(days=today.weekday())  # Monday
        period_end = period_start + timedelta(days=6)
    elif pay_freq == "biweekly":
        if business.next_pay_date:
            # Work backwards from next pay date
            period_end = business.next_pay_date - timedelta(days=1)
            period_start = period_end - timedelta(days=13)
        else:
            period_start = today - timedelta(days=today.weekday())
            period_end = period_start + timedelta(days=13)
    elif pay_freq in ("semimonthly", "custom_dates"):
        days = business.pay_specific_days or [1, 15]
        sorted_days = sorted(days)
        # Find the current period
        for i, d in enumerate(sorted_days):
            if today.day < d:
                period_end = today.replace(day=d) - timedelta(days=1)
                if i == 0:
                    prev_month = today.month - 1 or 12
                    prev_year = today.year if today.month > 1 else today.year - 1
                    from calendar import monthrange
                    last_day = monthrange(prev_year, prev_month)[1]
                    period_start = dt_date(prev_year, prev_month, min(sorted_days[-1], last_day))
                else:
                    period_start = today.replace(day=sorted_days[i - 1])
                break
        else:
            period_start = today.replace(day=sorted_days[-1])
            if today.month == 12:
                period_end = dt_date(today.year + 1, 1, min(sorted_days[0], 28)) - timedelta(days=1)
            else:
                period_end = today.replace(month=today.month + 1, day=min(sorted_days[0], 28)) - timedelta(days=1)
    elif pay_freq == "monthly":
        period_start = today.replace(day=1)
        if today.month == 12:
            period_end = dt_date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    else:
        period_start = today - timedelta(days=today.weekday())
        period_end = period_start + timedelta(days=6)

    # Get all entries for this period
    entries = TimeEntry.objects.filter(
        user__business=business,
        clock_in__date__gte=period_start,
        clock_in__date__lte=period_end,
        clock_out__isnull=False,
    ).select_related("user").order_by("user__first_name", "clock_in")

    # Group by employee
    from collections import OrderedDict
    employee_data = OrderedDict()
    for entry in entries:
        uid = entry.user_id
        if uid not in employee_data:
            employee_data[uid] = {
                "employee": entry.user,
                "entries": [],
                "total_minutes": 0,
                "total_cost": Decimal("0"),
            }
        mins = entry.duration_minutes or 0
        rate = entry.user.hourly_rate or Decimal("0")
        cost = Decimal(str(mins)) / Decimal("60") * rate
        employee_data[uid]["entries"].append(entry)
        if entry.status == "approved":
            employee_data[uid]["total_minutes"] += mins
            employee_data[uid]["total_cost"] += cost

    # Format totals
    for data in employee_data.values():
        hrs = data["total_minutes"] // 60
        mins = data["total_minutes"] % 60
        data["total_display"] = f"{hrs}h {mins}m" if hrs else f"{mins}m"
        data["total_cost"] = data["total_cost"].quantize(Decimal("0.01"))

    grand_total_minutes = sum(d["total_minutes"] for d in employee_data.values())
    grand_total_cost = sum(d["total_cost"] for d in employee_data.values())
    grand_hrs = grand_total_minutes // 60
    grand_mins = grand_total_minutes % 60

    return render(request, "time_tracking/pay_period.html", {
        "period_start": period_start,
        "period_end": period_end,
        "pay_frequency": business.get_pay_frequency_display() if hasattr(business, 'get_pay_frequency_display') else pay_freq,
        "next_pay_date": business.next_pay_date,
        "employee_data": employee_data.values(),
        "grand_total_display": f"{grand_hrs}h {grand_mins}m" if grand_hrs else f"{grand_mins}m",
        "grand_total_cost": grand_total_cost,
    })


@require_POST
@role_required("owner", "manager")
def time_entry_delete(request, entry_id):
    """Owner deletes a time entry."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    entry = get_object_or_404(TimeEntry, id=entry_id, user__business=business)
    entry.delete()
    messages.success(request, "Time entry deleted.")
    return redirect("time_entries_list")


def _get_business(request):
    """Business for current context (owner's business or platform-selected)."""
    user = request.user
    if user.business_id:
        return user.business
    from businesses.models import Business
    bid = request.session.get("platform_business_id")
    if bid:
        return Business.objects.filter(pk=bid).first()
    return None


@role_required("owner", "manager", "crew")
def time_off_list(request):
    """List time off requests: crew sees own, owner sees all for business."""
    business = _get_business(request)
    if not business and request.user.role in ("owner", "manager"):
        return redirect("/")
    if request.user.role == "crew":
        requests_qs = TimeOffRequest.objects.filter(user=request.user).select_related("reviewed_by")
        employees = None
    else:
        requests_qs = TimeOffRequest.objects.filter(business=business).select_related("user", "reviewed_by")
        employees = User.objects.filter(business=business, role="crew").order_by("first_name", "last_name", "username")
    requests_qs = requests_qs.order_by("-start_date", "-created_at")
    return render(request, "time_tracking/time_off_list.html", {
        "time_off_requests": requests_qs,
        "is_owner": request.user.role in ("owner", "manager"),
        "employees": employees or [],
    })


@role_required("owner", "manager", "crew")
def time_off_create(request):
    """Submit a new time off request (crew) or for selected employee (owner)."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    # Owner can submit on behalf of employee via ?user_id=
    target_user = request.user
    if request.user.role in ("owner", "manager") and request.GET.get("user_id"):
        target_user = get_object_or_404(User, pk=request.GET["user_id"], business=business, role="crew")
    if request.method == "POST":
        form = TimeOffRequestForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.business = business
            obj.user = target_user
            obj.save()
            messages.success(request, "Time off request submitted.")
            from django.urls import reverse
            return redirect(reverse("employee_management") + "#timeoff")
    else:
        form = TimeOffRequestForm()
    return render(request, "time_tracking/time_off_form.html", {
        "form": form,
        "target_user": target_user,
        "is_owner_submitting": request.user != target_user,
    })


@require_POST
@role_required("owner", "manager")
def time_off_approve(request, pk):
    """Approve a time off request."""
    req = get_object_or_404(TimeOffRequest, pk=pk, business=_get_business(request))
    req.status = "approved"
    req.reviewed_at = timezone.now()
    req.reviewed_by = request.user
    req.save()
    messages.success(request, "Time off request approved.")
    from django.urls import reverse
    return redirect(reverse("employee_management") + "#timeoff")


@require_POST
@role_required("owner", "manager")
def time_off_deny(request, pk):
    """Deny a time off request."""
    req = get_object_or_404(TimeOffRequest, pk=pk, business=_get_business(request))
    req.status = "denied"
    req.reviewed_at = timezone.now()
    req.reviewed_by = request.user
    req.save()
    messages.success(request, "Time off request denied.")
    from django.urls import reverse
    return redirect(reverse("employee_management") + "#timeoff")


@role_required("owner", "manager", "crew")
def schedule_view(request):
    """View schedule: crew sees own, owner sees dropdown to pick employee or overview."""
    business = _get_business(request)
    if not business and request.user.role in ("owner", "manager"):
        return redirect("/")
    employees = User.objects.filter(business=business, role="crew").order_by("first_name", "last_name", "username")
    selected_id = request.GET.get("user_id")
    if request.user.role == "crew":
        selected_user = request.user
    elif selected_id:
        selected_user = get_object_or_404(User, pk=selected_id, business=business, role="crew")
    else:
        selected_user = employees.first()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule_rows = []
    if selected_user:
        slots = {s.day_of_week: s for s in EmployeeSchedule.objects.filter(user=selected_user)}
        for i in range(7):
            schedule_rows.append((day_names[i], slots.get(i)))
    else:
        for i in range(7):
            schedule_rows.append((day_names[i], None))
    return render(request, "time_tracking/schedule_view.html", {
        "employees": employees,
        "selected_user": selected_user,
        "schedule_rows": schedule_rows,
        "is_owner": request.user.role in ("owner", "manager"),
    })


def _ensure_schedule_slots(user):
    """Ensure user has exactly 7 EmployeeSchedule rows (one per day). Returns queryset ordered by day."""
    existing = set(
        EmployeeSchedule.objects.filter(user=user).values_list("day_of_week", flat=True)
    )
    for day in range(7):
        if day not in existing:
            EmployeeSchedule.objects.create(user=user, day_of_week=day)
    return EmployeeSchedule.objects.filter(user=user).order_by("day_of_week")


@role_required("owner", "manager")
def schedule_edit(request):
    """Edit weekly schedule (owner only). Owners set each employee's schedule."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    target_user = request.user
    if request.GET.get("user_id"):
        target_user = get_object_or_404(User, pk=request.GET["user_id"], business=business, role="crew")
    queryset = _ensure_schedule_slots(target_user)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if request.method == "POST":
        formset = EmployeeScheduleFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            for form in formset:
                if form.cleaned_data:
                    obj = form.save(commit=False)
                    obj.user = target_user
                    obj.save()
            formset.save()
            ScheduleChangeLog.objects.create(
                business=business,
                user=request.user,
                target_user_id=target_user.id if target_user else None,
                details=f"Weekly schedule updated for {target_user.get_full_name() or target_user.username}",
            )
            messages.success(request, "Schedule updated.")
            from django.urls import reverse
            edit_url = reverse("employee_management") + "#schedule"
            if target_user and target_user.role == "crew":
                edit_url = reverse("employee_management") + "?schedule_user_id=" + str(target_user.id) + "#schedule"
            return redirect(edit_url)
    else:
        formset = EmployeeScheduleFormSet(queryset=queryset)
    rows = list(zip(formset, day_names))
    return render(request, "time_tracking/schedule_edit.html", {
        "target_user": target_user,
        "formset": formset,
        "rows": rows,
    })

from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from .models import TimeEntry


def _hours_from_minutes(minutes):
    """Convert minutes to decimal hours for cost calculation."""
    if minutes is None:
        return Decimal("0")
    return Decimal(str(minutes)) / Decimal("60")


@role_required("owner", "crew")
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
@role_required("owner", "crew")
def clock_in(request):
    TimeEntry.objects.create(user=request.user, clock_in=timezone.now())
    messages.success(request, 'Clocked in successfully.')
    return redirect('time_clock')


@require_POST
@role_required("owner", "crew")
def clock_out(request):
    entry = TimeEntry.objects.filter(
        user=request.user, clock_out__isnull=True
    ).order_by('-clock_in').first()

    if entry:
        entry.clock_out = timezone.now()
        entry.save()
        messages.success(request, 'Clocked out successfully.')
    else:
        messages.warning(request, 'No active clock-in found.')

    return redirect('time_clock')


@role_required("owner")
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

        # Week: entries where clock_in date falls in the week (attribute shift to clock-in day)
        week_entries = TimeEntry.objects.filter(
            user=user,
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

    return render(request, 'time_tracking/timesheets.html', {
        'employee_stats': employee_stats,
        'week_start': week_start,
        'week_end': week_end,
        'year_start': year_start,
        'year_end': year_end,
        'total_week_cost': total_week_cost,
        'total_year_cost': total_year_cost,
    })

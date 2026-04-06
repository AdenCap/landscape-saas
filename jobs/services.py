from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from accounts.timezone_utils import business_today as _biz_today
from .models import RecurringJob, Job, JobServiceItem
from pricing.models import ServiceTemplate


def _next_date(current_date, rj):
    from calendar import monthrange
    if rj.frequency == "weekly":
        return current_date + timedelta(weeks=1)
    if rj.frequency == "biweekly":
        return current_date + timedelta(weeks=2)
    if rj.frequency == "monthly":
        y, m = current_date.year, current_date.month
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        last = monthrange(y, m)[1]
        day = min(current_date.day, last)
        return date(y, m, day)
    if rj.frequency == "custom" and rj.custom_interval_days:
        return current_date + timedelta(days=rj.custom_interval_days)
    return current_date + timedelta(weeks=1)


def _add_service_items_to_job(job, service_snapshot):
    """Create JobServiceItems from RecurringJob.service_snapshot."""
    if not service_snapshot:
        return
    for item in service_snapshot:
        service_id = item.get("service_id")
        if not service_id:
            continue
        try:
            service = ServiceTemplate.objects.get(pk=service_id)
        except ServiceTemplate.DoesNotExist:
            continue
        quantity = Decimal(str(item.get("quantity", 1)))
        unit = item.get("unit") or getattr(service, "default_unit", None) or "visit"
        unit_price = Decimal(str(item.get("unit_price", 0)))
        JobServiceItem.objects.create(
            job=job,
            service=service,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
        )


def generate_jobs(days_ahead=14):
    today = _biz_today()
    end_date = today + timedelta(days=days_ahead)
    recurring_jobs = RecurringJob.objects.filter(active=True).select_related("property", "assigned_to", "assigned_crew")

    for rj in recurring_jobs:
        current_date = rj.start_date
        while current_date <= end_date:
            if current_date >= today:
                job, created = Job.objects.get_or_create(
                    property=rj.property,
                    scheduled_date=current_date,
                    recurring_job=rj,
                    defaults={
                        "assigned_to": rj.assigned_to,
                        "assigned_crew": rj.assigned_crew,
                        "notes": rj.notes or "",
                        "status": "scheduled",
                    },
                )
                if created and rj.service_snapshot:
                    _add_service_items_to_job(job, rj.service_snapshot)
            current_date = _next_date(current_date, rj)

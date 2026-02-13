from datetime import date
from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceLineItem


@transaction.atomic
def generate_monthly_invoice_for_customer(customer, year, month):
    # Import here to avoid circular import problems
    from jobs.models import Job, JobServiceItem

    period_start = date(year, month, 1)
    period_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    invoice, _ = Invoice.objects.get_or_create(
        business=customer.business,
        customer=customer,
        period_start=period_start,
        period_end=period_end,
        defaults={"status": "draft"},
    )

    completed_jobs = Job.objects.filter(
        property__customer=customer,
        status="completed",
        scheduled_date__gte=period_start,
        scheduled_date__lt=period_end,
    )

    items = JobServiceItem.objects.filter(
        job__in=completed_jobs,
        billed_invoice__isnull=True,
    ).select_related("service", "job", "job__property")

    for item in items:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=f"{item.service.name} - {item.job.property.address} ({item.job.scheduled_date})",
            quantity=item.quantity,
            unit_price=item.unit_price,
        )

        item.billed_invoice = invoice
        item.billed_at = timezone.now()
        item.save(update_fields=["billed_invoice", "billed_at"])

    return invoice

from datetime import date
from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceLineItem, InvoiceAuditLog
from .services import get_invoice_due_date


@transaction.atomic
def generate_monthly_invoice_for_customer(customer, year, month, include_job=None):
    """
    Add completed job(s) to the customer's monthly invoice for this period.
    If the existing monthly invoice for this period was already sent/paid, we create
    a new draft invoice for the same period (so later services get a separate invoice).
    """
    from django.db.models import Q
    from jobs.models import Job, JobServiceItem

    period_start = date(year, month, 1)
    period_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    # Only add to a DRAFT monthly invoice for this period. If the current one was sent/paid,
    # create a new draft so we don't add to an already-sent invoice.
    invoice = Invoice.objects.filter(
        business=customer.business,
        customer=customer,
        period_start=period_start,
        period_end=period_end,
        job__isnull=True,
        status="draft",
    ).first()

    if not invoice:
        issue_date = timezone.localdate()
        due_date = get_invoice_due_date(issue_date, customer.business, customer)
        invoice = Invoice.objects.create(
            business=customer.business,
            customer=customer,
            period_start=period_start,
            period_end=period_end,
            issue_date=issue_date,
            due_date=due_date,
            status="draft",
        )
        InvoiceAuditLog.objects.create(
            invoice=invoice,
            action="created",
            user=None,
            details={"source": "monthly", "period": f"{year}-{month:02d}"},
        )

    base_filter = Q(property__customer=customer, status="completed")
    date_filter = Q(scheduled_date__gte=period_start, scheduled_date__lt=period_end)
    if include_job:
        completed_jobs = Job.objects.filter((base_filter & date_filter) | Q(id=include_job.id))
    else:
        completed_jobs = Job.objects.filter(base_filter & date_filter)

    items = JobServiceItem.objects.filter(
        job__in=completed_jobs,
        billed_invoice__isnull=True,
    ).select_related("service", "job", "job__property")

    for item in items:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=f"{item.service.name} - {item.job.property.address}" + (f" ({item.job.scheduled_date})" if item.job.scheduled_date else ""),
            quantity=item.quantity,
            unit_price=item.unit_price,
            labor_cost=item.quantity * item.unit_price,
            revenue_category=getattr(item.service, "revenue_category", None),
        )

        item.billed_invoice = invoice
        item.billed_at = timezone.now()
        item.save(update_fields=["billed_invoice", "billed_at"])

    invoice.recompute_totals()
    return invoice

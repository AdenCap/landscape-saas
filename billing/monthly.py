from datetime import date
from django.db import transaction
from django.utils import timezone
from accounts.timezone_utils import business_today as _biz_today

from .models import Invoice, InvoiceLineItem, InvoiceAuditLog
from .services import get_invoice_due_date
from jobs.service_labels import clean_service_label


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
        issue_date = _biz_today(customer.business)
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
        service_label = clean_service_label(item.description, item.service)
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=f"{service_label} - {item.job.property.address}" + (f" ({item.job.scheduled_date})" if item.job.scheduled_date else ""),
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


def build_missing_monthly_invoices_for_period(business, year, month):
    """
    Sweep completed, unbilled service items into draft monthly invoices.

    This is intentionally idempotent: only JobServiceItem rows without a
    billed_invoice are collected, so re-running it will not duplicate invoice
    lines that have already been attached to an invoice.
    """
    from django.db.models import Q
    from customers.models import Customer
    from jobs.models import JobServiceItem

    period_start = date(year, month, 1)
    period_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    uses_monthly_default = getattr(business, "default_invoice_automation_mode", "") == "monthly"
    monthly_customer_filter = Q(invoice_frequency="monthly")
    if uses_monthly_default:
        monthly_customer_filter |= Q(invoice_frequency="")

    customers = (
        Customer.objects.filter(business=business)
        .filter(monthly_customer_filter)
        .filter(
            properties__jobs__status="completed",
            properties__jobs__scheduled_date__gte=period_start,
            properties__jobs__scheduled_date__lt=period_end,
            properties__jobs__service_items__billed_invoice__isnull=True,
        )
        .distinct()
        .order_by("name", "id")
    )

    invoices = []
    items_added = 0
    for customer in customers:
        pending_count = JobServiceItem.objects.filter(
            job__property__customer=customer,
            job__status="completed",
            job__scheduled_date__gte=period_start,
            job__scheduled_date__lt=period_end,
            billed_invoice__isnull=True,
        ).count()
        if not pending_count:
            continue
        invoice = generate_monthly_invoice_for_customer(customer, year, month)
        invoices.append(invoice)
        items_added += pending_count

    return {
        "period_start": period_start,
        "period_end": period_end,
        "invoices": invoices,
        "invoice_count": len(invoices),
        "items_added": items_added,
    }

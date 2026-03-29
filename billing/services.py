from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from .models import Invoice, InvoiceLineItem, InvoiceAuditLog
from jobs.models import JobServiceItem


def get_invoice_due_date(issue_date, business, customer=None):
    """
    Return due date for an invoice: issue_date + N days.
    N = customer.invoice_due_days if set, else business.default_invoice_due_days.
    Returns None if neither is set.
    """
    days = None
    if customer is not None and getattr(customer, "invoice_due_days", None) is not None:
        days = customer.invoice_due_days
    elif business is not None and getattr(business, "default_invoice_due_days", None) is not None:
        days = business.default_invoice_due_days
    if days is None:
        return None
    return issue_date + timedelta(days=days)


def _get_business_from_job(job):
    if hasattr(job, "property") and job.property and hasattr(job.property, "business"):
        return job.property.business

    if hasattr(job, "customer") and job.customer and hasattr(job.customer, "business"):
        return job.customer.business

    if hasattr(job, "property") and job.property and hasattr(job.property, "customer") and job.property.customer:
        if hasattr(job.property.customer, "business"):
            return job.property.customer.business

    raise ImproperlyConfigured(
        "Could not determine Business for job. Add job.business or adjust _get_business_from_job()."
    )


def _get_customer_from_job(job):
    if hasattr(job, "customer") and job.customer:
        return job.customer
    if hasattr(job, "property") and job.property and hasattr(job.property, "customer"):
        return job.property.customer
    return None


def _decimal(val, default="0.00"):
    if val is None:
        return Decimal(default)
    return Decimal(str(val))


@transaction.atomic
def create_and_send_invoice_for_job(job, send=True):
    """
    Create invoice for job, add line items from JobServiceItems, optionally mark as sent.
    Use for immediate billing when job is completed.
    """
    invoice = create_draft_invoice_for_job(job)
    if send and invoice.status == "draft":
        invoice.status = "sent"
        invoice.save(update_fields=["status"])
    return invoice


@transaction.atomic
def create_invoice_for_job(job):
    # derive business/customer from your existing relationships
    business = getattr(job.property, "business", None)
    if business is None and hasattr(job.property, "customer") and hasattr(job.property.customer, "business"):
        business = job.property.customer.business

    customer = getattr(job.property, "customer", None)
    issue_date = timezone.localdate()
    due_date = get_invoice_due_date(issue_date, business, customer)

    invoice, _ = Invoice.objects.get_or_create(
        job=job,
        defaults={
            "business": business,
            "customer": customer,
            "due_date": due_date,
            "status": "draft",
        },
    )

    if invoice.line_items.exists():
        return invoice

    if job.service_items.exists():
        for item in job.service_items.select_related("service").all():
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=item.service.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                labor_cost=item.quantity * item.unit_price,
            )
        invoice.recompute_totals()

    return invoice

@transaction.atomic
def create_draft_invoice_for_job(job):
    """
    Creates a DRAFT invoice for this job if one doesn't exist.
    Pulls line items from JobServiceItem.
    Does NOT send the invoice.
    Skips if customer has a prepaid agreement covering this service.
    """
    business = job.property.customer.business
    customer = job.property.customer

    # Check for prepaid agreements — skip invoicing if all services are covered
    try:
        from service_agreements.models import ServiceAgreement, AgreementLineItem
        prepaid_agreements = ServiceAgreement.objects.filter(
            customer=customer, business=business, status="active", prepaid=True
        ).prefetch_related("line_items")
        if prepaid_agreements.exists():
            # Get service names from the job
            job_service_names = set(
                si.service.name.lower() for si in job.service_items.select_related("service").all() if si.service
            )
            # Get service names covered by prepaid agreements
            covered_names = set()
            for ag in prepaid_agreements:
                if ag.is_active:
                    for li in ag.line_items.all():
                        covered_names.add(li.service_name.lower())
            # If ALL job services are covered by prepaid agreements, skip invoicing
            if job_service_names and job_service_names.issubset(covered_names):
                import logging
                logging.getLogger(__name__).info(
                    "Skipping invoice for job %s — all services covered by prepaid agreement", job.id
                )
                return None
    except Exception:
        pass
    issue_date = timezone.localdate()
    due_date = get_invoice_due_date(issue_date, business, customer) or issue_date

    invoice, created = Invoice.objects.get_or_create(
        job=job,
        defaults={
            "business": business,
            "customer": customer,
            "issue_date": issue_date,
            "due_date": due_date,
            "period_start": job.scheduled_date,
            "period_end": job.scheduled_date,
            "status": "draft",
        }
    )

    if not created:
        # already exists; don't duplicate
        return invoice

    InvoiceAuditLog.objects.create(invoice=invoice, action="created", user=None, details={"source": "job", "job_id": job.id})

    # Copy job service items into invoice line items
    job_items = JobServiceItem.objects.filter(job=job).select_related("service")

    for ji in job_items:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=getattr(ji.service, "name", "Service"),
            quantity=ji.quantity,
            unit_price=ji.unit_price,
            labor_cost=ji.quantity * ji.unit_price,
            revenue_category=getattr(ji.service, "revenue_category", None),
        )

    return invoice
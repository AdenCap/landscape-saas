from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from .models import Invoice, InvoiceLineItem
from billing.models import Invoice, InvoiceLineItem
from jobs.models import JobServiceItem


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

    invoice, _ = Invoice.objects.get_or_create(
        job=job,
        defaults={"business": business, "customer": customer, "status": "draft"},
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

    return invoice

@transaction.atomic
def create_draft_invoice_for_job(job):
    """
    Creates a DRAFT invoice for this job if one doesn't exist.
    Pulls line items from JobServiceItem.
    Does NOT send the invoice.
    """
    # If your Invoice has a FK to job (your choices list shows invoice.job exists)
    invoice, created = Invoice.objects.get_or_create(
        job=job,
        defaults={
            "business": job.property.customer.business,
            "customer": job.property.customer,
            "issue_date": timezone.localdate(),
            "due_date": timezone.localdate(),  # adjust if you want net-15/net-30
            "period_start": job.scheduled_date,
            "period_end": job.scheduled_date,
            "status": "draft",
        }
    )

    if not created:
        # already exists; don't duplicate
        return invoice

    # Copy job service items into invoice line items
    job_items = JobServiceItem.objects.filter(job=job).select_related("service")

    for ji in job_items:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=getattr(ji.service, "name", "Service"),
            quantity=ji.quantity,
            unit_price=ji.unit_price,
            labor_cost=ji.quantity * ji.unit_price,
        )

    # If your Invoice model has subtotal/tax/total fields stored:
    # recompute from line items (simple example)
    subtotal = sum(item.line_total for item in invoice.line_items.all())
    invoice.subtotal = subtotal
    invoice.tax = 0
    invoice.total = subtotal
    invoice.save(update_fields=["subtotal", "tax", "total"])

    return invoice
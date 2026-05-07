from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.conf import settings
import stripe
from accounts.timezone_utils import business_today as _biz_today
from .models import Invoice, InvoiceLineItem, InvoiceAuditLog
from jobs.models import JobServiceItem
from jobs.service_labels import clean_service_label


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


def invoice_card_payment_default(business):
    """Return the business default for whether new invoices allow card checkout."""
    return bool(getattr(business, "default_invoice_card_payments_enabled", True))


@transaction.atomic
def combine_customer_invoices(*, business, target_invoice_id, invoice_ids, user=None):
    """Move open same-customer invoices into one invoice and void the emptied sources."""
    if not target_invoice_id or not str(target_invoice_id).isdigit():
        raise ValueError("Choose which invoice should keep the combined line items.")
    target_id = int(target_invoice_id)
    ids = {int(invoice_id) for invoice_id in invoice_ids if str(invoice_id).isdigit()}
    ids.add(target_id)
    if len(ids) < 2:
        raise ValueError("Choose at least two invoices to combine.")

    invoices = list(
        Invoice.objects.select_for_update()
        .filter(business=business, id__in=ids)
        .select_related("customer", "job")
        .prefetch_related("jobs")
        .order_by("id")
    )
    if len(invoices) != len(ids):
        raise ValueError("One or more invoices could not be found.")

    allowed_statuses = {"draft", "sent"}
    if any(invoice.status not in allowed_statuses for invoice in invoices):
        raise ValueError("Only draft or sent invoices can be combined.")

    customer_ids = {invoice.customer_id for invoice in invoices}
    if len(customer_ids) != 1:
        raise ValueError("Invoices can only be combined for the same client.")

    target = next((invoice for invoice in invoices if invoice.id == target_id), None)
    if target is None:
        raise ValueError("Choose which invoice should keep the combined line items.")

    any_sent = any(invoice.status == "sent" for invoice in invoices)
    source_ids = [invoice.id for invoice in invoices if invoice.id != target.id]

    if target.job_id:
        target.jobs.add(target.job)
    for invoice in invoices:
        if invoice.job_id:
            target.jobs.add(invoice.job)
        for job in invoice.jobs.all():
            target.jobs.add(job)
        JobServiceItem.objects.filter(billed_invoice=invoice).update(
            billed_invoice=target,
            billed_at=timezone.now(),
        )

    InvoiceLineItem.objects.filter(invoice_id__in=source_ids).update(invoice=target)

    for source in invoices:
        if source.id == target.id:
            continue
        source.job = None
        source.status = "void"
        source.subtotal = Decimal("0.00")
        source.tax = Decimal("0.00")
        source.total = Decimal("0.00")
        source.payment_token = None
        source.save(update_fields=["job", "status", "subtotal", "tax", "total", "payment_token"])
        InvoiceAuditLog.objects.create(
            invoice=source,
            action="void",
            user=user,
            details={"source": "combined_into_invoice", "target_invoice_id": target.id},
        )

    if any_sent and target.status != "sent":
        target.status = "sent"
        target.save(update_fields=["status"])
    target.recompute_totals()
    InvoiceAuditLog.objects.create(
        invoice=target,
        action="line_items_edited",
        user=user,
        details={"source": "combine_invoices", "combined_invoice_ids": source_ids},
    )
    return target


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


def auto_charge_invoice_card(invoice, user=None, source="manual"):
    """
    Charge an invoice using the customer's saved card when the customer preference allows it.
    Returns (charged: bool, message: str). Failures are logged but do not block invoice sending.
    """
    business = invoice.business
    customer = invoice.customer
    if invoice.status == "paid":
        return False, "Invoice already paid."
    if not getattr(business, "client_saved_cards_enabled", True):
        return False, "Saved-card charging is turned off in business settings."
    if not getattr(business, "can_accept_stripe_payments", lambda: False)():
        return False, "Card payments are not ready for this business."
    if not customer.should_auto_charge_invoice(invoice):
        return False, "Auto-charge is not enabled for this invoice type."

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        invoice.recompute_totals()
        amount_cents = int(invoice.total * 100)
        if amount_cents < 50:
            return False, "Invoice total is below the card charge minimum."
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=customer.stripe_customer_id,
            payment_method=customer.stripe_payment_method_id,
            off_session=True,
            confirm=True,
            description=f"Invoice #{invoice.id} from {business.name}",
            metadata={"invoice_id": invoice.id, "business_id": business.id, "source": source},
            stripe_account=business.stripe_connect_account_id,
        )
    except Exception as exc:
        InvoiceAuditLog.objects.create(
            invoice=invoice,
            action="auto_charge_failed",
            user=user,
            details={"source": source, "error": str(exc)[:500]},
        )
        return False, "Auto-charge failed. The invoice was still sent."

    if payment_intent.status != "succeeded":
        InvoiceAuditLog.objects.create(
            invoice=invoice,
            action="auto_charge_failed",
            user=user,
            details={"source": source, "status": payment_intent.status},
        )
        return False, "Auto-charge did not complete. The invoice was still sent."

    invoice.status = "paid"
    invoice.payment_method = "card"
    invoice.paid_at = timezone.now()
    invoice.stripe_payment_intent_id = payment_intent.id
    if getattr(payment_intent, "latest_charge", None):
        invoice.stripe_charge_id = payment_intent.latest_charge
    invoice.save(update_fields=["status", "payment_method", "paid_at", "stripe_payment_intent_id", "stripe_charge_id"])
    invoice.line_items.filter(is_paid=False).update(is_paid=True, paid_at=invoice.paid_at, paid_by=user, payment_method="card")
    InvoiceAuditLog.objects.create(
        invoice=invoice,
        action="auto_charged",
        user=user,
        details={
            "source": source,
            "stripe_pi": payment_intent.id,
            "amount": amount_cents,
            "card": customer.card_last4,
        },
    )
    return True, f"Card ({customer.card_brand} ****{customer.card_last4}) charged."


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


def _copy_job_item_to_invoice(invoice, job_item):
    InvoiceLineItem.objects.create(
        invoice=invoice,
        description=clean_service_label(job_item.description, job_item.service),
        detail_description=getattr(job_item, "detail_description", "") or "",
        quantity=job_item.quantity,
        unit_price=job_item.unit_price,
        labor_cost=job_item.quantity * job_item.unit_price,
        revenue_category=getattr(job_item.service, "revenue_category", None),
    )
    job_item.billed_invoice = invoice
    job_item.billed_at = timezone.now()
    job_item.save(update_fields=["billed_invoice", "billed_at"])


@transaction.atomic
def create_invoice_for_job(job):
    # derive business/customer from your existing relationships
    business = getattr(job.property, "business", None)
    if business is None and hasattr(job.property, "customer") and hasattr(job.property.customer, "business"):
        business = job.property.customer.business

    customer = getattr(job.property, "customer", None)
    issue_date = _biz_today(business)
    due_date = get_invoice_due_date(issue_date, business, customer)

    invoice, _ = Invoice.objects.get_or_create(
        job=job,
        defaults={
            "business": business,
            "customer": customer,
            "due_date": due_date,
            "status": "draft",
            "enable_card_payment": invoice_card_payment_default(business),
        },
    )

    if invoice.line_items.exists():
        return invoice

    if job.service_items.exists():
        for item in job.service_items.select_related("service").all():
            _copy_job_item_to_invoice(invoice, item)
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
    issue_date = _biz_today(business)
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
            "enable_card_payment": invoice_card_payment_default(business),
        }
    )

    if not created:
        if invoice.line_items.exists():
            job_items = JobServiceItem.objects.filter(
                job=job,
                billed_invoice__isnull=True,
            ).select_related("service")
        else:
            job_items = JobServiceItem.objects.filter(job=job).select_related("service")
        for ji in job_items:
            _copy_job_item_to_invoice(invoice, ji)
        if job_items:
            invoice.recompute_totals()
        return invoice

    InvoiceAuditLog.objects.create(invoice=invoice, action="created", user=None, details={"source": "job", "job_id": job.id})

    # Copy job service items into invoice line items
    job_items = JobServiceItem.objects.filter(job=job).select_related("service")

    for ji in job_items:
        _copy_job_item_to_invoice(invoice, ji)

    return invoice

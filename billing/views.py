import hashlib
import secrets
import stripe
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.http import FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from customers.models import Customer, ClientMessage


def _email_template_vars(s, **kwargs):
    """Replace {{key}} placeholders in string s with values from kwargs."""
    if not s:
        return s
    out = s
    for key, val in kwargs.items():
        out = out.replace("{{" + key + "}}", str(val or ""))
    return out
from .models import (
    Invoice,
    InvoiceAuditLog,
    InvoiceLineItem,
    Estimate,
    EstimateLineItem,
    EstimateImage,
    DocumentTemplate,
    FertilizerProduct,
    FertilizerApplication,
)
from .forms import (
    EstimateForm,
    EstimateLineItemForm,
    EstimateLineItemFormSet,
    EstimateImageForm,
    InvoiceLineItemFormSet,
    DocumentTemplateForm,
    _compute_fertilizing,
    _compute_mulch,
)

def invoice_list_view(request):
    invoices = Invoice.objects.all().order_by('-issue_date')
    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices
    })


@role_required("owner", "manager")
def invoice_list(request):
    business = getattr(request.user, "business", None)
    qs = Invoice.objects.select_related("customer")
    if business:
        qs = qs.filter(business=business)
    invoices = qs.order_by("-issue_date", "-id")[:100]
    return render(request, "billing/invoice_list.html", {"invoices": invoices})


@role_required("owner", "manager")
def invoice_create(request):
    """Create a new blank draft invoice for a selected customer, then redirect to line-item editor."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("billing:invoice_list")

    customers = Customer.objects.filter(business=business).order_by("name")

    if request.method == "POST":
        customer_id = request.POST.get("customer")
        if not customer_id:
            messages.error(request, "Please select a customer.")
            return render(request, "billing/invoice_create.html", {"customers": customers})

        customer = get_object_or_404(Customer, id=customer_id, business=business)
        invoice = Invoice.objects.create(
            business=business,
            customer=customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        _log_invoice_audit(invoice, "created", request=request, details={"method": "manual"})
        messages.success(request, f"Draft invoice #{invoice.id} created. Add your line items below.")
        return redirect("billing:invoice_edit_line_items", invoice_id=invoice.id)

    return render(request, "billing/invoice_create.html", {"customers": customers})


@role_required("owner", "manager")
def monthly_invoice_list(request):
    """List monthly invoices (period-based), including drafts being built during the month."""
    business = getattr(request.user, "business", None)
    if not business:
        messages.error(request, "You must be associated with a business to view invoices.")
        return redirect("/")
    # Monthly invoices: no single job, have period
    monthly = (
        Invoice.objects.filter(business=business, job__isnull=True, period_start__isnull=False)
        .select_related("customer")
        .order_by("-period_start", "-id")
    )
    # Optional year filter
    year_param = request.GET.get("year", "").strip()
    year_int = int(year_param) if year_param.isdigit() else None
    if year_int:
        monthly = monthly.filter(period_start__year=year_int)
    from datetime import date as date_type
    from django.utils import timezone as tz
    today = tz.localdate()
    years = [today.year, today.year - 1, today.year - 2]
    # Build list with "send on" date for each invoice (when customer has monthly_invoice_send_day)
    rows = []
    for inv in monthly[:100]:
        send_on = None
        customer_day = getattr(inv.customer, "monthly_invoice_send_day", None)
        business_day = getattr(inv.business, "default_monthly_invoice_send_day", None)
        send_day = customer_day or business_day
        if inv.status == "draft" and inv.period_start and send_day:
            day = min(send_day, 28)
            try:
                send_on = date_type(inv.period_start.year, inv.period_start.month, day)
            except (ValueError, TypeError):
                pass
        rows.append({"invoice": inv, "send_on": send_on})
    return render(request, "billing/monthly_invoice_list.html", {
        "rows": rows,
        "year_param": year_param,
        "year_int": year_int,
        "years": years,
    })


@role_required("owner", "manager")
def outstanding_invoices(request):
    """Outstanding invoice dashboard: sent/unpaid with aging (0-30, 31-60, 61+ days overdue)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    today = timezone.localdate()
    from datetime import timedelta
    day_30 = today - timedelta(days=30)
    day_60 = today - timedelta(days=60)

    # Sent, unpaid — annotate days_overdue for display
    base_qs = Invoice.objects.filter(business=business, status="sent").select_related("customer")
    outstanding_list = list(base_qs.order_by("due_date", "id"))
    for inv in outstanding_list:
        if inv.due_date and inv.due_date < today:
            inv.days_overdue = (today - inv.due_date).days
        else:
            inv.days_overdue = None
    total_outstanding = sum(inv.total for inv in outstanding_list)

    # Aging: overdue only (due_date < today)
    overdue_0_30 = [i for i in outstanding_list if i.due_date and day_30 <= i.due_date < today]
    overdue_31_60 = [i for i in outstanding_list if i.due_date and day_60 <= i.due_date < day_30]
    overdue_61_plus = [i for i in outstanding_list if i.due_date and i.due_date < day_60]
    total_0_30 = sum(i.total for i in overdue_0_30)
    total_30_60 = sum(i.total for i in overdue_31_60)
    total_60_plus = sum(i.total for i in overdue_61_plus)

    # Not yet due (due_date >= today or null)
    not_due = [i for i in outstanding_list if not i.due_date or i.due_date >= today]
    total_not_due = sum(i.total for i in not_due)

    return render(request, "billing/outstanding_invoices.html", {
        "outstanding_list": outstanding_list,
        "total_outstanding": total_outstanding,
        "overdue_0_30": overdue_0_30,
        "overdue_31_60": overdue_31_60,
        "overdue_61_plus": overdue_61_plus,
        "total_0_30": total_0_30,
        "total_30_60": total_30_60,
        "total_60_plus": total_60_plus,
        "not_due": not_due,
        "total_not_due": total_not_due,
        "today": today,
    })


@role_required("owner", "manager")
def invoice_detail(request, invoice_id):
    business = getattr(request.user, "business", None)
    qs = Invoice.objects.select_related("business", "customer").filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)
    invoice.recompute_totals()
    items = invoice.line_items.all()
    is_monthly = bool(invoice.job_id is None and invoice.period_start)
    audit_logs = invoice.audit_logs.select_related("user")[:10]
    doc_template = DocumentTemplate.get_default_for_business(invoice.business, "invoice") if invoice.business_id else None
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "items": items,
        "is_monthly_invoice": is_monthly,
        "audit_logs": audit_logs,
        "doc_template": doc_template,
    })


@require_POST
@role_required("owner", "manager")
def invoice_update_dates(request, invoice_id):
    """Owner can change due date (and optionally issue date) on any invoice."""
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)

    due_date_str = (request.POST.get("due_date") or "").strip()
    if not due_date_str:
        messages.error(request, "Please enter a due date.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    try:
        from datetime import datetime
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Invalid due date. Use YYYY-MM-DD.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    update_fields = ["due_date"]
    invoice.due_date = due_date
    issue_date_str = (request.POST.get("issue_date") or "").strip()
    if issue_date_str:
        try:
            invoice.issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            update_fields.append("issue_date")
        except ValueError:
            pass
    invoice.save(update_fields=update_fields)
    _log_invoice_audit(invoice, "dates_updated", request=request, details={"due_date": due_date_str})
    messages.success(request, f"Due date set to {due_date}.")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@require_POST
@role_required("owner", "manager")
def invoice_edit_custom_fields(request, invoice_id):
    """Save custom field values for an invoice (from document template)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    invoice = get_object_or_404(Invoice, id=invoice_id, business=business)
    doc_template = DocumentTemplate.get_default_for_business(invoice.business, "invoice")
    if doc_template and doc_template.custom_fields:
        custom_values = dict(invoice.custom_field_values or {})
        for field_def in doc_template.custom_fields:
            key = field_def.get("key")
            if key:
                val = (request.POST.get(f"custom_value_{key}") or "").strip()
                if val:
                    custom_values[key] = val
                elif key in custom_values:
                    del custom_values[key]
        invoice.custom_field_values = custom_values
        invoice.save()
        messages.success(request, "Additional information saved.")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


def _log_invoice_audit(invoice, action, request=None, details=None):
    """Record an invoice audit log entry."""
    user = request.user if request and getattr(request, "user", None) else None
    InvoiceAuditLog.objects.create(
        invoice=invoice,
        action=action,
        user=user,
        details=details or {},
    )


@role_required("owner", "manager")
def invoice_edit_line_items(request, invoice_id):
    """Owner can add/edit/delete line items on a draft invoice."""
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id).prefetch_related("line_items")
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)

    if invoice.status != "draft":
        messages.error(request, "Only draft invoices can be edited.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    formset = InvoiceLineItemFormSet(request.POST or None, instance=invoice)
    if request.method == "POST" and formset.is_valid():
        for form in formset:
            if form in formset.deleted_forms:
                if form.instance.pk:
                    form.instance.delete()
                continue
            obj = form.save(commit=False)
            desc = (getattr(obj, "description", None) or "").strip()
            if not desc:
                if obj.pk:
                    obj.delete()
                continue
            obj.description = desc
            obj.quantity = obj.quantity or 1
            obj.unit_price = getattr(obj, "unit_price", None) or 0
            obj.save()
        invoice.recompute_totals()
        _log_invoice_audit(
            invoice,
            "line_items_edited",
            request=request,
            details={"line_count": invoice.line_items.count()},
        )
        messages.success(request, "Line items updated.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    return render(
        request,
        "billing/invoice_line_items_edit.html",
        {"invoice": invoice, "formset": formset},
    )


@require_POST
@role_required("owner", "manager")
def send_invoice(request, invoice_id):
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)

    # Only allow draft -> sent; owner approval required (never auto-send)
    if invoice.status == "draft":
        invoice.status = "sent"
        if not invoice.payment_token:
            invoice.payment_token = secrets.token_urlsafe(32)
        invoice.approved_at = timezone.now()
        invoice.approved_by = request.user
        invoice.save(update_fields=["status", "payment_token", "approved_at", "approved_by"])
        _log_invoice_audit(invoice, "approved_sent", request=request)
        messages.success(request, "Invoice approved and sent. Customer can pay via the link below.")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


def _business_has_payment_methods(business):
    return bool(
        (business.venmo_username or "").strip()
        or (business.zelle_email_or_phone or "").strip()
        or (business.cashapp_cashtag or "").strip()
    )


@require_http_methods(["GET"])
def invoice_pay_page(request, invoice_id, token):
    """Public page: customer sees how to pay (Venmo/Zelle/Cash App). Only the owner can mark the invoice as paid."""
    invoice = get_object_or_404(
        Invoice.objects.select_related("business", "customer"),
        id=invoice_id,
        payment_token=token,
    )
    invoice.recompute_totals()
    business = invoice.business
    has_payment_methods = _business_has_payment_methods(business)
    venmo_link = None
    if (business.venmo_username or "").strip():
        uname = (business.venmo_username or "").strip().lstrip("@")
        venmo_link = f"https://account.venmo.com/pay?recipient={uname}&amount={invoice.total}"
    cashapp_link = None
    if (business.cashapp_cashtag or "").strip():
        tag = (business.cashapp_cashtag or "").strip().lstrip("$")
        cashapp_link = f"https://cash.app/${tag}/{invoice.total}"
    can_accept_stripe = getattr(business, "can_accept_stripe_payments", lambda: False)()
    line_items = invoice.line_items.all()
    return render(request, "billing/invoice_pay_page.html", {
        "invoice": invoice,
        "business": business,
        "has_payment_methods": has_payment_methods,
        "venmo_link": venmo_link,
        "cashapp_link": cashapp_link,
        "can_accept_stripe": can_accept_stripe,
        "line_items": line_items,
    })


@require_POST
@role_required("owner", "manager")
def mark_invoice_paid(request, invoice_id):
    """Owner marks a sent invoice as paid (after customer has paid via Venmo/Zelle/Cash App)."""
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)
    if invoice.status == "sent":
        invoice.status = "paid"
        invoice.save(update_fields=["status"])
        _log_invoice_audit(invoice, "paid", request=request)
        messages.success(request, f"Invoice #{invoice.id} marked as paid.")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


# ----- Stripe Connect: business accepts card payments for invoices -----

def _stripe_connect_enabled():
    return bool(getattr(settings, "STRIPE_SECRET_KEY", None))


@role_required("owner", "manager")
@require_http_methods(["GET"])
def connect_onboarding(request):
    """Start or resume Stripe Connect Express onboarding; redirect to Stripe."""
    if not _stripe_connect_enabled():
        messages.info(
            request,
            "Stripe payment processing is not yet enabled on the platform. "
            "Please contact your administrator to enable credit card payments."
        )
        return redirect("business_settings")
    business = _get_business(request)
    if not business:
        return redirect("/")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    account_id = (business.stripe_connect_account_id or "").strip()
    if not account_id:
        try:
            acc = stripe.Account.create(
                type="express",
                country="US",
                email=getattr(request.user, "email", None) or "",
            )
            account_id = acc.id
            business.stripe_connect_account_id = account_id
            business.stripe_connect_charges_enabled = False
            business.save(update_fields=["stripe_connect_account_id", "stripe_connect_charges_enabled"])
        except stripe.StripeError as e:
            messages.error(request, f"Could not create Stripe account: {e.user_message or str(e)}")
            return redirect("business_settings")
    return_url = request.build_absolute_uri(reverse("billing:connect_return"))
    refresh_url = request.build_absolute_uri(reverse("billing:connect_onboarding"))
    try:
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return redirect(link.url)
    except stripe.StripeError as e:
        messages.error(request, f"Could not start onboarding: {e.user_message or str(e)}")
        return redirect("business_settings")


@role_required("owner", "manager")
@require_http_methods(["GET"])
def connect_return(request):
    """Stripe redirects here after Connect onboarding.

    Actively checks the Stripe account status instead of waiting for the
    webhook, so the settings page shows the correct status immediately.
    """
    business = _get_business(request)
    if business and business.stripe_connect_account_id:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            acc = stripe.Account.retrieve(business.stripe_connect_account_id)
            business.stripe_connect_charges_enabled = bool(acc.get("charges_enabled"))
            business.save(update_fields=["stripe_connect_charges_enabled"])
        except Exception:
            pass  # Webhook will update later as fallback
    messages.success(request, "Stripe setup complete. You can now accept card payments on invoices.")
    return redirect("business_settings")


@role_required("owner", "manager")
@require_http_methods(["GET"])
def connect_dashboard(request):
    """Redirect to Stripe Express Dashboard for the connected account."""
    if not _stripe_connect_enabled():
        messages.info(
            request,
            "Stripe payment processing is not yet enabled on the platform. "
            "Please contact your administrator to enable credit card payments."
        )
        return redirect("business_settings")
    business = _get_business(request)
    if not business or not business.stripe_connect_account_id:
        messages.error(request, "Connect your Stripe account first in Settings.")
        return redirect("business_settings")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.Account.create_login_link(business.stripe_connect_account_id)
        return redirect(session.url)
    except stripe.StripeError as e:
        messages.error(request, f"Could not open dashboard: {e.user_message or str(e)}")
        return redirect("business_settings")


@require_POST
@require_http_methods(["POST"])
def create_invoice_checkout_session(request, invoice_id, token):
    """Public: create Stripe Checkout Session for paying an invoice (Connect). Redirects to Stripe."""
    invoice = get_object_or_404(
        Invoice.objects.select_related("business", "customer"),
        id=invoice_id,
        payment_token=token,
    )
    if invoice.status != "sent":
        messages.error(request, "This invoice is not available for payment.")
        return redirect("billing:invoice_pay_page", invoice_id=invoice.id, token=token)
    business = invoice.business
    if not getattr(business, "can_accept_stripe_payments", lambda: False)():
        messages.error(request, "Card payment is not available for this invoice.")
        return redirect("billing:invoice_pay_page", invoice_id=invoice.id, token=token)
    if not _stripe_connect_enabled():
        messages.info(request, "Credit card payment is not available. Please use another payment method.")
        return redirect("billing:invoice_pay_page", invoice_id=invoice.id, token=token)
    stripe.api_key = settings.STRIPE_SECRET_KEY
    invoice.recompute_totals()
    amount_cents = int(invoice.total * 100)
    if amount_cents < 50:
        messages.error(request, "Minimum payment is $0.50.")
        return redirect("billing:invoice_pay_page", invoice_id=invoice.id, token=token)
    success_url = request.build_absolute_uri(
        reverse("billing:invoice_pay_page", args=[invoice.id, token]) + "?paid=1"
    )
    cancel_url = request.build_absolute_uri(
        reverse("billing:invoice_pay_page", args=[invoice.id, token])
    )
    # Per-business fee if set, else global default (for future use)
    fee_percent = getattr(business, "stripe_connect_application_fee_percent", None)
    if fee_percent is not None:
        fee_percent = float(fee_percent)
    if fee_percent is None:
        fee_percent = getattr(settings, "STRIPE_CONNECT_APPLICATION_FEE_PERCENT", 0) or 0
    
    # Use idempotency key to prevent duplicate sessions
    idempotency_key = f"invoice:{invoice.id}:checkout:{hashlib.md5(str(invoice.id).encode()).hexdigest()[:8]}"
    
    # Create checkout session in the CONNECTED ACCOUNT context (merchant-of-record)
    # Funds go directly to the connected account, not the platform
    try:
        # Use stripeAccount parameter to make the connected account the merchant
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": f"Invoice #{invoice.id}",
                        "description": f"Payment for invoice from {business.name}",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "invoice_id": str(invoice.id),
                "business_id": str(business.id),
                "platform_user_id": str(business.id),
            },
            # Optional: Add application fee if we enable platform fees later
            # For now, fee_percent is 0, so no fee is applied
            payment_intent_data={
                "application_fee_amount": int(amount_cents * fee_percent / 100) if fee_percent > 0 else None,
            } if fee_percent > 0 else {},
            # CRITICAL: Use stripeAccount to make connected account the merchant-of-record
            stripe_account=business.stripe_connect_account_id,
            idempotency_key=idempotency_key,
        )
        # Store checkout session ID on invoice
        invoice.stripe_checkout_session_id = session.id
        invoice.save(update_fields=["stripe_checkout_session_id"])
        return redirect(session.url)
    except stripe.StripeError as e:
        messages.error(request, f"Could not start payment: {e.user_message or str(e)}")
        return redirect("billing:invoice_pay_page", invoice_id=invoice.id, token=token)


def _fmt_currency(val):
    """Format decimal as currency, trimming trailing zeros. 150.00 -> $150, 150.50 -> $150.50"""
    if val is None:
        return "$0"
    s = f"{float(val):.2f}".rstrip("0").rstrip(".")
    return f"${s}" if s else "$0"


def _get_reportlab():
    """Lazy import to avoid PIL/reportlab load at startup (Pillow may fail on Mac if venv from Windows)."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas
    return canvas, LETTER


def _draw_pdf_logo(p, business, x=50, y_top=770, max_height=48, max_width=160, page_width=None):
    """Draw business logo on ReportLab canvas if present. Use page_width and x=None to align right."""
    if not business or not business.logo:
        return
    try:
        path = business.logo.path
        if not path:
            return
        if page_width is not None and x is None:
            x = page_width - 50 - max_width
        p.drawImage(path, x, y_top - max_height, width=max_width, height=max_height)
    except Exception:
        pass


# Theme colors for PDFs (match base.html: primary #22c55e, dark #171717, muted #a3a3a3)
_PDF_GREEN = (34 / 255, 197 / 255, 94 / 255)
_PDF_DARK = (0.09, 0.09, 0.09)
_PDF_MUTED = (0.64, 0.64, 0.64)
_PDF_BORDER = (0.15, 0.15, 0.15)


def _hex_to_rgb(hex_str):
    """Convert #RRGGBB to (r, g, b) floats 0-1. Returns _PDF_GREEN if invalid."""
    if not hex_str or not hex_str.startswith("#") or len(hex_str) != 7:
        return _PDF_GREEN
    try:
        r = int(hex_str[1:3], 16) / 255
        g = int(hex_str[3:5], 16) / 255
        b = int(hex_str[5:7], 16) / 255
        return (r, g, b)
    except ValueError:
        return _PDF_GREEN


def _build_invoice_pdf(invoice, request):
    """Build invoice PDF bytes (for download or email). Uses document template if set."""
    canvas, LETTER = _get_reportlab()
    items = invoice.line_items.all()
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    business = invoice.business
    doc_template = DocumentTemplate.get_default_for_business(business, "invoice") if business else None
    accent_rgb = _hex_to_rgb(doc_template.primary_color) if doc_template and getattr(doc_template, "primary_color", None) else _PDF_GREEN

    # Accent bar at top
    p.setFillColorRGB(*accent_rgb)
    p.rect(0, height - 12, width, 12, fill=True, stroke=False)

    y = height - 44
    p.setFillColorRGB(*_PDF_DARK)
    if doc_template and doc_template.header_text:
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in (doc_template.header_text or "").replace("\r", "").split("\n")[:4]:
            if line.strip():
                p.drawString(50, y, line.strip()[:90])
                y -= 12
        y -= 8
        p.setFillColorRGB(*_PDF_DARK)
    if business and business.logo:
        _draw_pdf_logo(p, business, x=None, y_top=y + 10, max_height=44, max_width=140, page_width=width)
        p.setFont("Helvetica-Bold", 20)
        p.setFillColorRGB(*accent_rgb)
        p.drawString(50, y - 28, f"Invoice #{invoice.id}")
        p.setFillColorRGB(*_PDF_DARK)
        y -= 50
    else:
        p.setFont("Helvetica-Bold", 20)
        p.setFillColorRGB(*accent_rgb)
        p.drawString(50, y, f"Invoice #{invoice.id}")
        p.setFillColorRGB(*_PDF_DARK)
        y -= 28

    p.setFont("Helvetica", 10)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawString(50, y, f"Issue date: {invoice.issue_date}")
    y -= 14
    p.drawString(50, y, f"Due date: {invoice.due_date or '—'}")
    y -= 14
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(50, y, f"Bill to: {invoice.customer.name}")
    y -= 14
    if invoice.customer.full_address:
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(50, y, invoice.customer.full_address[:60])
        y -= 12
    p.setFont("Helvetica", 10)
    y -= 12

    # Table header
    p.setFillColorRGB(*_PDF_DARK)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(450, y, "Total")
    y -= 4
    p.setFillColorRGB(*accent_rgb)
    p.setLineWidth(1.5)
    p.line(50, y, 560, y)
    y -= 16

    p.setFillColorRGB(*_PDF_DARK)
    p.setFont("Helvetica", 10)
    computed_total = Decimal("0.00")
    for item in items:
        lt = item.line_total
        computed_total += lt
        p.drawString(50, y, str(item.description)[:50])
        p.drawRightString(560, y, _fmt_currency(lt))
        y -= 16
        if y < 100:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 10)
            p.setFillColorRGB(*_PDF_DARK)

    y -= 6
    p.setFillColorRGB(*accent_rgb)
    p.line(450, y + 4, 560, y + 4)
    y -= 4
    p.setFont("Helvetica-Bold", 12)
    total_to_show = getattr(invoice, "total", None) or computed_total
    p.drawRightString(560, y, f"Total: {_fmt_currency(total_to_show)}")

    if doc_template and doc_template.custom_fields and invoice.custom_field_values:
        y -= 20
        p.setFont("Helvetica-Bold", 9)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(50, y, "Additional information")
        y -= 12
        p.setFont("Helvetica", 9)
        for field_def in doc_template.custom_fields:
            key = field_def.get("key")
            val = (invoice.custom_field_values or {}).get(key)
            if key and val:
                p.drawString(50, y, f"{field_def.get('label', key)}: {str(val)[:70]}")
                y -= 12
                if y < 100:
                    break
        y -= 8
    if doc_template and doc_template.terms_and_conditions:
        y -= 16
        p.setFont("Helvetica-Bold", 9)
        p.setFillColorRGB(*_PDF_DARK)
        p.drawString(50, y, "Terms & conditions")
        y -= 10
        p.setFont("Helvetica", 8)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in (doc_template.terms_and_conditions or "").replace("\r", "").split("\n")[:12]:
            if line.strip():
                p.drawString(50, y, line.strip()[:90])
                y -= 10
                if y < 60:
                    break
    if doc_template and doc_template.footer_text:
        y -= 12
        p.setFont("Helvetica", 8)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in (doc_template.footer_text or "").replace("\r", "").split("\n")[:3]:
            if line.strip():
                p.drawString(50, y, line.strip()[:90])
                y -= 10
                if y < 50:
                    break
    y -= 12

    _has_payment = business and (
        (business.venmo_username or "").strip()
        or (business.zelle_email_or_phone or "").strip()
        or (business.cashapp_cashtag or "").strip()
    )
    if _has_payment and y > 140:
        y -= 28
        p.setFillColorRGB(*_PDF_DARK)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, y, "How to pay")
        y -= 18
        icon_size = 14
        for label, handle, r, g, b in [
            ("Venmo", (business.venmo_username or "").strip(), 0, 0.55, 1),
            ("Zelle", (business.zelle_email_or_phone or "").strip(), 0.43, 0.12, 0.83),
            ("Cash App", (business.cashapp_cashtag or "").strip(), 0, 0.84, 0.29),
        ]:
            if not handle:
                continue
            icon_y = y + 10
            p.setFillColorRGB(r, g, b)
            p.roundRect(50, icon_y - icon_size, icon_size, icon_size, 3, fill=True, stroke=False)
            p.setFillColorRGB(1, 1, 1)
            p.setFont("Helvetica-Bold", 9)
            p.drawString(53, icon_y - icon_size + 3, label[0])
            p.setFillColorRGB(*_PDF_DARK)
            p.setFont("Helvetica", 10)
            p.drawString(50 + icon_size + 8, icon_y - 10, f"{label}: {handle[:40]}")
            y -= 22

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.read()


@role_required("owner", "manager")
def invoice_pdf(request, invoice_id):
    business = _get_business(request)
    qs = Invoice.objects.select_related("business", "customer").filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)
    invoice.recompute_totals()
    pdf_bytes = _build_invoice_pdf(invoice, request)
    return FileResponse(BytesIO(pdf_bytes), as_attachment=True, filename=f"invoice_{invoice.id}.pdf")


@require_POST
@role_required("owner", "manager")
def resend_invoice(request, invoice_id):
    """Resend the invoice by email to the customer (PDF + pay link). Can be used any number of times for sent/paid invoices."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    qs = Invoice.objects.select_related("business", "customer").filter(id=invoice_id)
    qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)

    if invoice.status not in ("sent", "paid"):
        messages.error(request, "Only sent or paid invoices can be resent. Mark the invoice as Sent first.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    if not invoice.customer.email:
        messages.error(request, f"{invoice.customer.name} has no email address. Add one in Clients.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    connection = business.get_smtp_connection()
    if not connection:
        messages.error(
            request,
            "Connect your Gmail in Settings to send invoices. Add your Gmail address and App Password.",
        )
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    invoice.recompute_totals()
    pay_url = ""
    if invoice.payment_token:
        pay_url = request.build_absolute_uri(
            reverse("billing:invoice_pay_page", args=[invoice.id, invoice.payment_token])
        )

    from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fieldops.local")
    reply_to = [business.contact_email] if business.contact_email else None
    subject = (
        _email_template_vars(
            (business.invoice_email_subject or "").strip(),
            invoice_id=invoice.id,
            customer_name=invoice.customer.name,
            business_name=business.name,
        )
        or f"Invoice #{invoice.id} from {business.name}"
    )
    intro = _email_template_vars(
        (business.invoice_email_intro or "").strip()
        or f"Hi {invoice.customer.name}, please find your invoice below.",
        customer_name=invoice.customer.name,
        business_name=business.name,
        invoice_id=invoice.id,
    )
    closing = _email_template_vars(
        (business.invoice_email_closing or "").strip() or "Thank you for your business.",
        customer_name=invoice.customer.name,
        business_name=business.name,
    )
    body_text = intro + "\n\n"
    body_text += f"Invoice #{invoice.id} · Total: ${invoice.total}\n\n"
    if pay_url:
        body_text += f"Pay online: {pay_url}\n\n"
    body_text += closing + "\n\n" + business.name

    logo_url = request.build_absolute_uri(business.logo.url) if business.logo else None
    doc_template = DocumentTemplate.get_default_for_business(business, "invoice")
    accent_color = doc_template.primary_color if doc_template and getattr(doc_template, "primary_color", None) else "#22c55e"
    html_content = render_to_string("billing/invoice_email.html", {
        "invoice": invoice,
        "business": business,
        "pay_url": pay_url,
        "logo_url": logo_url,
        "email_intro": intro,
        "email_closing": closing,
        "accent_color": accent_color,
    })

    msg = EmailMultiAlternatives(
        subject,
        body_text,
        from_email,
        [invoice.customer.email],
        reply_to=reply_to,
        connection=connection,
    )
    msg.attach_alternative(html_content, "text/html")

    pdf_bytes = _build_invoice_pdf(invoice, request)
    msg.attach(f"Invoice_{invoice.id}.pdf", pdf_bytes, "application/pdf")

    try:
        msg.send()
        messages.success(request, f"Invoice #{invoice.id} resent to {invoice.customer.email}.")
    except Exception as e:
        messages.error(request, f"Could not send email: {e}")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


# --- Estimates ---


@role_required("owner", "manager")
def estimate_list(request):
    from datetime import timedelta
    
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    estimates = Estimate.objects.filter(business=business).select_related("customer").order_by("-created_at")

    status_filter = request.GET.get("status") or "pending"
    if status_filter == "accepted":
        estimates = estimates.filter(status="accepted")
    elif status_filter == "pending":
        estimates = estimates.exclude(status="accepted")
    else:
        status_filter = "all"

    stale_cutoff = timezone.now() - timedelta(days=5)
    stuck_quotes = Estimate.objects.filter(
        business=business,
        status__in=["draft", "sent"],
        created_at__lt=stale_cutoff,
    ).select_related("customer").order_by("created_at")[:6]

    return render(request, "billing/estimate_list.html", {
        "estimates": estimates,
        "status_filter": status_filter,
        "stuck_quotes": stuck_quotes,
    })


@role_required("owner", "manager")
def leads_followups(request):
    """Leads & Follow-ups: View for tracking quotes that were sent but never converted."""
    from datetime import timedelta
    
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    
    now = timezone.now()
    
    # Get all sent estimates that haven't been accepted or declined
    leads = Estimate.objects.filter(
        business=business,
        status__in=["sent", "draft"],  # Include drafts that were created but maybe not sent
    ).select_related("customer").order_by("-sent_at", "-created_at")
    
    # Filter by age (days since sent/created)
    age_filter = request.GET.get("age", "all")
    if age_filter == "7":
        cutoff = now - timedelta(days=7)
        leads = leads.filter(sent_at__lt=cutoff) if leads.filter(sent_at__isnull=False).exists() else leads.filter(created_at__lt=cutoff)
    elif age_filter == "14":
        cutoff = now - timedelta(days=14)
        leads = leads.filter(sent_at__lt=cutoff) if leads.filter(sent_at__isnull=False).exists() else leads.filter(created_at__lt=cutoff)
    elif age_filter == "30":
        cutoff = now - timedelta(days=30)
        leads = leads.filter(sent_at__lt=cutoff) if leads.filter(sent_at__isnull=False).exists() else leads.filter(created_at__lt=cutoff)
    elif age_filter == "60":
        cutoff = now - timedelta(days=60)
        leads = leads.filter(sent_at__lt=cutoff) if leads.filter(sent_at__isnull=False).exists() else leads.filter(created_at__lt=cutoff)
    
    # Calculate days since sent/created and last follow-up for each lead
    leads_with_metrics = []
    for lead in leads:
        # Days since sent (or created if never sent)
        sent_date = lead.sent_at.date() if lead.sent_at else lead.created_at.date()
        days_since_sent = (now.date() - sent_date).days
        
        # Days since last follow-up (or None if never followed up)
        days_since_followup = None
        if lead.last_follow_up_at:
            days_since_followup = (now.date() - lead.last_follow_up_at.date()).days
        
        # Check if this estimate was converted to a job
        has_job = False
        if hasattr(lead, 'job') and lead.job:
            has_job = True
        else:
            # Check if customer has any jobs related to this estimate
            from jobs.models import Job
            has_job = Job.objects.filter(
                customer=lead.customer,
                property__in=lead.customer.properties.all()
            ).exists()
        
        leads_with_metrics.append({
            'estimate': lead,
            'days_since_sent': days_since_sent,
            'days_since_followup': days_since_followup,
            'has_job': has_job,
            'sent_date': sent_date,
        })
    
    # Sort by days since sent (oldest first)
    leads_with_metrics.sort(key=lambda x: x['days_since_sent'], reverse=True)
    
    return render(request, "billing/leads_followups.html", {
        "leads": leads_with_metrics,
        "age_filter": age_filter,
    })


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def estimate_create(request):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    if request.method == "POST":
        form = EstimateForm(request.POST, business=business)
        if form.is_valid():
            estimate = form.save(commit=False)
            estimate.business = business
            estimate.save()
            messages.success(request, f"Estimate created for {estimate.customer.name}.")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect("billing:estimate_edit", estimate_id=estimate.id)
    else:
        form = EstimateForm(business=business)
        customer_id = request.GET.get("customer")
        if customer_id:
            try:
                cust = Customer.objects.get(id=customer_id, business=business)
                form.initial["customer"] = cust
            except (Customer.DoesNotExist, ValueError):
                pass

    return render(request, "billing/estimate_form.html", {"form": form, "title": "Create Estimate", "next_value": request.GET.get("next", "")})


@role_required("owner", "manager")
@require_POST
def estimate_create_from_fertilizer(request):
    """Create an estimate with one fertilizing line item from calculator data (POST from estimator)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    try:
        customer_id = request.POST.get("customer_id")
        customer = Customer.objects.get(id=customer_id, business=business)
    except (Customer.DoesNotExist, TypeError, ValueError):
        messages.error(request, "Please select a valid customer.")
        return redirect("fertilizer_calculator")
    
    # Get product if product_id is provided
    product = None
    product_id = request.POST.get("product_id")
    if product_id:
        try:
            product = FertilizerProduct.objects.get(id=product_id, business=business)
        except FertilizerProduct.DoesNotExist:
            pass
    
    config = {
        "lbs_per_1000": request.POST.get("lbs_per_1000"),
        "total_sqft": request.POST.get("total_sqft"),
        "product": request.POST.get("product") or (product.name if product else "Fertilizer"),
        "pricing_type": request.POST.get("pricing_type") or (product.pricing_type if product else "per_pound"),
        "cost_per_pound": request.POST.get("cost_per_pound") or (str(product.cost_per_pound) if product and product.cost_per_pound else None),
        "cost_per_bag": request.POST.get("cost_per_bag") or (str(product.cost_per_bag) if product and product.cost_per_bag else None),
        "lbs_per_bag": request.POST.get("lbs_per_bag") or (str(product.lbs_per_bag) if product and product.lbs_per_bag else None),
    }
    
    # If product is selected, use its pricing
    if product:
        if product.pricing_type == 'per_pound' and product.cost_per_pound:
            config['cost_per_pound'] = str(product.cost_per_pound)
            config['pricing_type'] = 'per_pound'
        elif product.pricing_type == 'per_bag' and product.cost_per_bag and product.lbs_per_bag:
            config['cost_per_bag'] = str(product.cost_per_bag)
            config['lbs_per_bag'] = str(product.lbs_per_bag)
            config['pricing_type'] = 'per_bag'
        config['product'] = product.name
    
    desc, material_cost = _compute_fertilizing(config)
    if not desc:
        messages.error(request, "Invalid calculator inputs.")
        return redirect("fertilizer_calculator")
    
    # Calculate pounds used
    rate = Decimal(str(config.get('lbs_per_1000') or 0))
    sqft = Decimal(str(config.get('total_sqft') or 0))
    total_pounds = (rate / 1000) * sqft
    
    estimate = Estimate.objects.create(
        business=business,
        customer=customer,
        title=request.POST.get("title") or "Tradevo Service Estimate",
    )
    
    line_item = EstimateLineItem.objects.create(
        estimate=estimate,
        item_type="fertilizing",
        fertilizing_config=config,
        mulch_config=None,
        mowing_config=None,
        description=desc,
        quantity=Decimal("1"),
        unit="application",
        material_cost=material_cost,
        labor_cost=Decimal("0"),
        order=0,
    )
    
    # Create FertilizerApplication record if product is selected and property exists
    property_id = request.POST.get("property_id")
    if product and property_id:
        try:
            from customers.models import Property
            property_obj = Property.objects.get(id=property_id, customer=customer, customer__business=business)
            FertilizerApplication.objects.create(
                business=business,
                property=property_obj,
                product=product,
                estimate=estimate,
                application_date=timezone.now().date(),
                pounds_used=total_pounds,
                square_feet=sqft,
                lbs_per_1000_sqft=rate,
                material_cost=material_cost,
                charge_amount=None,  # Will be set when estimate is accepted/invoiced
            )
        except (Property.DoesNotExist, ValueError, TypeError):
            pass  # Property not found, skip application record
    elif product:
        # Product selected but no property - still create application record if we can find property
        # Try to get first property for customer
        try:
            from customers.models import Property
            property_obj = Property.objects.filter(customer=customer, customer__business=business).first()
            if property_obj:
                FertilizerApplication.objects.create(
                    business=business,
                    property=property_obj,
                    product=product,
                    estimate=estimate,
                    application_date=timezone.now().date(),
                    pounds_used=total_pounds,
                    square_feet=sqft,
                    lbs_per_1000_sqft=rate,
                    material_cost=material_cost,
                    charge_amount=None,
                )
        except Exception:
            pass
    
    messages.success(request, f"Estimate created for {customer.name}. Add labor or more line items below.")
    return redirect("billing:estimate_edit", estimate_id=estimate.id)


@role_required("owner", "manager")
@require_POST
def estimate_create_from_mulch(request):
    """Create an estimate with one mulch/rock line item from calculator data (POST from estimator)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    try:
        customer_id = request.POST.get("customer_id")
        customer = Customer.objects.get(id=customer_id, business=business)
    except (Customer.DoesNotExist, TypeError, ValueError):
        messages.error(request, "Please select a valid customer.")
        return redirect("mulch_rock_calculator")
    config = {
        "total_sqft": request.POST.get("total_sqft"),
        "depth_inches": request.POST.get("depth_inches") or 3,
        "product": request.POST.get("product") or "Mulch",
        "pricing_type": request.POST.get("pricing_type") or "per_bag",
        "cost_per_bag": request.POST.get("cost_per_bag"),
        "cf_per_bag": request.POST.get("cf_per_bag") or 2,
        "cost_per_cy": request.POST.get("cost_per_cy"),
    }
    desc, material_cost = _compute_mulch(config)
    if not desc:
        messages.error(request, "Invalid calculator inputs.")
        return redirect("mulch_rock_calculator")
    estimate = Estimate.objects.create(
        business=business,
        customer=customer,
        title=request.POST.get("title") or "Tradevo Service Estimate",
    )
    EstimateLineItem.objects.create(
        estimate=estimate,
        item_type="mulch",
        fertilizing_config=None,
        mulch_config=config,
        mowing_config=None,
        description=desc,
        quantity=Decimal("1"),
        unit="application",
        material_cost=material_cost,
        labor_cost=Decimal("0"),
        order=0,
    )
    messages.success(request, f"Estimate created for {customer.name}. Add labor or more line items below.")
    return redirect("billing:estimate_edit", estimate_id=estimate.id)


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def estimate_edit(request, estimate_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    doc_template = DocumentTemplate.get_default_for_business(business, "estimate")

    if request.method == "POST":
        form = EstimateForm(request.POST, instance=estimate, business=business)
        formset = EstimateLineItemFormSet(request.POST, instance=estimate)
        if form.is_valid() and formset.is_valid():
            form.save()
            saved = formset.save()
            # Save custom field values from template
            if doc_template and doc_template.custom_fields:
                custom_values = dict(estimate.custom_field_values or {})
                for field_def in doc_template.custom_fields:
                    key = field_def.get("key")
                    if key:
                        val = (request.POST.get(f"custom_value_{key}") or "").strip()
                        if val:
                            custom_values[key] = val
                        elif key in custom_values:
                            del custom_values[key]
                estimate.custom_field_values = custom_values
                estimate.save()
            if saved:
                messages.success(request, "Line item added. Add another below or go to View & send when done.")
            return redirect("billing:estimate_edit", estimate_id=estimate.id)
        else:
            if not form.is_valid():
                messages.error(request, "Please fix the errors in the details section.")
            if not formset.is_valid():
                messages.error(request, "Please fix the errors in the line items.")
    else:
        form = EstimateForm(instance=estimate, business=business)
        formset = EstimateLineItemFormSet(instance=estimate)

    return render(request, "billing/estimate_edit.html", {
        "form": form, "formset": formset, "estimate": estimate, "doc_template": doc_template,
    })


@role_required("owner", "manager")
def estimate_detail(request, estimate_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(
        Estimate.objects.select_related("business", "customer"),
        id=estimate_id,
        business=business,
    )
    doc_template = DocumentTemplate.get_default_for_business(business, "estimate")
    
    # Get fertilizer applications for this estimate
    fertilizer_apps = FertilizerApplication.objects.filter(
        estimate=estimate
    ).select_related('product', 'property')
    
    # Calculate totals for profit analysis
    from decimal import Decimal
    total_material_cost = sum(Decimal(str(app.material_cost)) for app in fertilizer_apps)
    total_charged = sum(Decimal(str(app.charge_amount)) for app in fertilizer_apps if app.charge_amount) or None
    total_profit = (total_charged - total_material_cost) if total_charged else None
    
    return render(request, "billing/estimate_detail.html", {
        "estimate": estimate,
        "doc_template": doc_template,
        "fertilizer_applications": fertilizer_apps,
        "total_material_cost": total_material_cost,
        "total_charged": total_charged,
        "total_profit": total_profit,
    })


def _build_estimate_pdf(estimate, business):
    """Build estimate PDF bytes (with logo if business has one). Uses document template if set."""
    canvas, LETTER = _get_reportlab()
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    doc_template = DocumentTemplate.get_default_for_business(business, "estimate") if business else None
    accent_rgb = _hex_to_rgb(doc_template.primary_color) if doc_template and getattr(doc_template, "primary_color", None) else _PDF_GREEN

    # Accent bar at top
    p.setFillColorRGB(*accent_rgb)
    p.rect(0, height - 12, width, 12, fill=True, stroke=False)

    y = height - 44
    p.setFillColorRGB(*_PDF_DARK)
    if doc_template and doc_template.header_text:
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in (doc_template.header_text or "").replace("\r", "").split("\n")[:4]:
            if line.strip():
                p.drawString(50, y, line.strip()[:90])
                y -= 12
        y -= 8
        p.setFillColorRGB(*_PDF_DARK)
    if business and business.logo:
        _draw_pdf_logo(p, business, x=None, y_top=y + 10, max_height=44, max_width=140, page_width=width)
        p.setFont("Helvetica-Bold", 18)
        p.setFillColorRGB(*accent_rgb)
        p.drawString(50, y - 28, estimate.title)
        p.setFillColorRGB(*_PDF_DARK)
        y -= 50
    else:
        p.setFont("Helvetica-Bold", 18)
        p.setFillColorRGB(*accent_rgb)
        p.drawString(50, y, estimate.title)
        p.setFillColorRGB(*_PDF_DARK)
        y -= 28

    p.setFont("Helvetica", 10)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawString(50, y, f"Estimate #{estimate.id}")
    y -= 14
    p.drawString(50, y, f"Prepared for: {estimate.customer.name}")
    y -= 14
    if estimate.customer.email:
        p.drawString(50, y, f"Email: {estimate.customer.email}")
        y -= 14
    if estimate.valid_until:
        p.drawString(50, y, f"Valid until: {estimate.valid_until}")
        y -= 14
    p.setFillColorRGB(*_PDF_DARK)
    y -= 12

    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(450, y, "Total")
    y -= 4
    p.setFillColorRGB(*accent_rgb)
    p.setLineWidth(1.5)
    p.line(50, y, 560, y)
    y -= 16

    p.setFillColorRGB(*_PDF_DARK)
    p.setFont("Helvetica", 10)
    base_items = estimate.line_items.filter(is_addon=False)
    addon_items = estimate.line_items.filter(is_addon=True)

    for item in base_items:
        p.drawString(50, y, str(item.description)[:50])
        p.drawRightString(560, y, _fmt_currency(item.line_total))
        y -= 16
        if y < 100:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 10)
            p.setFillColorRGB(*_PDF_DARK)

    if addon_items.exists():
        y -= 6
        p.setFont("Helvetica-Oblique", 10)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(50, y, "Optional items:")
        y -= 16
        p.setFont("Helvetica", 10)
        p.setFillColorRGB(*_PDF_DARK)
        for item in addon_items:
            p.drawString(50, y, str(item.description)[:50])
            p.drawRightString(560, y, _fmt_currency(item.line_total))
            y -= 16
            if y < 100:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 10)
                p.setFillColorRGB(*_PDF_DARK)

    y -= 6
    p.setFillColorRGB(*accent_rgb)
    p.line(450, y + 4, 560, y + 4)
    y -= 4
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(560, y, f"Total: {_fmt_currency(estimate.total())}")

    if doc_template and doc_template.custom_fields and estimate.custom_field_values:
        y -= 20
        p.setFont("Helvetica-Bold", 9)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(50, y, "Additional information")
        y -= 12
        p.setFont("Helvetica", 9)
        for field_def in doc_template.custom_fields:
            key = field_def.get("key")
            val = (estimate.custom_field_values or {}).get(key)
            if key and val:
                p.drawString(50, y, f"{field_def.get('label', key)}: {str(val)[:70]}")
                y -= 12
                if y < 100:
                    break
        y -= 8
    if estimate.notes:
        y -= 16
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in estimate.notes.split("\n")[:8]:
            p.drawString(50, y, line[:80])
            y -= 12
            if y < 80:
                break
    if doc_template and doc_template.terms_and_conditions:
        y -= 16
        p.setFont("Helvetica-Bold", 9)
        p.setFillColorRGB(*_PDF_DARK)
        p.drawString(50, y, "Terms & conditions")
        y -= 10
        p.setFont("Helvetica", 8)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in (doc_template.terms_and_conditions or "").replace("\r", "").split("\n")[:12]:
            if line.strip():
                p.drawString(50, y, line.strip()[:90])
                y -= 10
                if y < 60:
                    break
    if doc_template and doc_template.footer_text:
        y -= 12
        p.setFont("Helvetica", 8)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in (doc_template.footer_text or "").replace("\r", "").split("\n")[:3]:
            if line.strip():
                p.drawString(50, y, line.strip()[:90])
                y -= 10
                if y < 50:
                    break

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.read()


@role_required("owner", "manager")
def estimate_pdf(request, estimate_id):
    business = _get_business(request)
    if not business:
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    pdf_bytes = _build_estimate_pdf(estimate, business)
    return FileResponse(BytesIO(pdf_bytes), as_attachment=True, filename=f"estimate_{estimate.id}.pdf")


@require_POST
@role_required("owner", "manager")
def estimate_send(request, estimate_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    customer = estimate.customer

    if not customer.email:
        messages.error(request, f"{customer.name} has no email address. Add one in Clients.")
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    if not estimate.line_items.exists():
        messages.error(request, "Add at least one line item before sending.")
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    # Set view token before sending so we can include the link in the email
    if not estimate.view_token:
        estimate.view_token = secrets.token_urlsafe(32)
        estimate.save(update_fields=["view_token"])

    view_url = request.build_absolute_uri(
        reverse("billing:estimate_client_view", args=[estimate.id, estimate.view_token])
    )

    connection = business.get_smtp_connection()
    if not connection:
        messages.error(
            request,
            "Connect your Gmail in Settings to send estimates. Go to Settings and add your Gmail address and App Password.",
        )
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    logo_url = request.build_absolute_uri(business.logo.url) if business.logo else None
    subject = (
        _email_template_vars(
            (business.estimate_email_subject or "").strip(),
            title=estimate.title,
            customer_name=customer.name,
            business_name=business.name,
        )
        or f"{estimate.title} – {business.name}"
    )
    intro = _email_template_vars(
        (business.estimate_email_intro or "").strip()
        or f"Hi {customer.name}, please find your estimate from {business.name} below.",
        customer_name=customer.name,
        business_name=business.name,
        title=estimate.title,
    )
    closing = _email_template_vars(
        (business.estimate_email_closing or "").strip()
        or "We look forward to working with you.",
        customer_name=customer.name,
        business_name=business.name,
    )
    doc_template = DocumentTemplate.get_default_for_business(business, "estimate")
    accent_color = doc_template.primary_color if doc_template and getattr(doc_template, "primary_color", None) else "#22c55e"
    html_content = render_to_string("billing/estimate_email.html", {
        "estimate": estimate,
        "customer": customer,
        "business": business,
        "request": request,
        "view_url": view_url,
        "logo_url": logo_url,
        "email_intro": intro,
        "email_closing": closing,
        "accent_color": accent_color,
    })

    from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fieldops.local")
    reply_to = [business.contact_email] if business.contact_email else None
    plain_body = intro + "\n\nView and accept your estimate: " + (view_url or "") + "\n\n" + closing + "\n\n" + business.name
    msg = EmailMultiAlternatives(
        subject,
        plain_body,
        from_email,
        [customer.email],
        reply_to=reply_to,
        connection=connection,
    )
    msg.attach_alternative(html_content, "text/html")

    pdf_bytes = _build_estimate_pdf(estimate, business)
    msg.attach(f"estimate_{estimate.id}.pdf", pdf_bytes, "application/pdf")

    try:
        msg.send()
        estimate.status = "sent"
        estimate.sent_at = timezone.now()
        estimate.save(update_fields=["status", "sent_at"])
        ClientMessage.objects.create(
            customer=customer,
            channel=ClientMessage.CHANNEL_EMAIL,
            direction=ClientMessage.DIRECTION_SENT,
            subject=subject,
            body=f"Estimate «{estimate.title}» sent to client. View estimate #{estimate.id} in Billing.",
            to_address=customer.email,
            created_by=request.user,
        )
        messages.success(request, f"Estimate sent to {customer.email}")
    except Exception as e:
        messages.error(request, f"Failed to send: {str(e)}")

    return redirect("billing:estimate_detail", estimate_id=estimate.id)


@require_POST
@role_required("owner", "manager")
def estimate_send_followup(request, estimate_id):
    """Send a follow-up / reminder email for an estimate awaiting response."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    customer = estimate.customer

    if estimate.status == "accepted":
        messages.info(request, "This estimate has already been accepted.")
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    if not customer.email:
        messages.error(request, f"{customer.name} has no email address.")
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    if not estimate.view_token:
        estimate.view_token = secrets.token_urlsafe(32)
        estimate.save(update_fields=["view_token"])

    view_url = request.build_absolute_uri(
        reverse("billing:estimate_client_view", args=[estimate.id, estimate.view_token])
    )

    connection = business.get_smtp_connection()
    if not connection:
        messages.error(request, "Connect your Gmail in Settings to send follow-ups.")
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    logo_url = request.build_absolute_uri(business.logo.url) if business.logo else None
    subject = (
        _email_template_vars(
            (business.estimate_followup_email_subject or "").strip(),
            title=estimate.title,
            customer_name=customer.name,
            business_name=business.name,
        )
        or f"Reminder: {estimate.title} – {business.name}"
    )
    intro = _email_template_vars(
        (business.estimate_followup_email_intro or "").strip()
        or f"Hi {customer.name}, we wanted to follow up on the estimate we sent you from {business.name}.",
        customer_name=customer.name,
        business_name=business.name,
        title=estimate.title,
    )
    doc_template = DocumentTemplate.get_default_for_business(business, "estimate")
    accent_color = doc_template.primary_color if doc_template and getattr(doc_template, "primary_color", None) else "#22c55e"
    html_content = render_to_string("billing/estimate_followup_email.html", {
        "estimate": estimate,
        "customer": customer,
        "business": business,
        "view_url": view_url,
        "logo_url": logo_url,
        "email_intro": intro,
        "accent_color": accent_color,
    })

    from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fieldops.local")
    reply_to = [business.contact_email] if business.contact_email else None
    plain_body = intro + "\n\nView your estimate: " + view_url
    msg = EmailMultiAlternatives(
        subject,
        plain_body,
        from_email,
        [customer.email],
        reply_to=reply_to,
        connection=connection,
    )
    msg.attach_alternative(html_content, "text/html")

    pdf_bytes = _build_estimate_pdf(estimate, business)
    msg.attach(f"estimate_{estimate.id}.pdf", pdf_bytes, "application/pdf")

    try:
        msg.send()
        estimate.last_follow_up_at = timezone.now()
        estimate.save(update_fields=["last_follow_up_at"])
        ClientMessage.objects.create(
            customer=customer,
            channel=ClientMessage.CHANNEL_EMAIL,
            direction=ClientMessage.DIRECTION_SENT,
            subject=subject,
            body=f"Estimate follow-up «{estimate.title}» sent to client.",
            to_address=customer.email,
            created_by=request.user,
        )
        messages.success(request, f"Follow-up sent to {customer.email}")
    except Exception as e:
        messages.error(request, f"Failed to send: {str(e)}")

    return redirect("billing:estimate_detail", estimate_id=estimate.id)


def estimate_client_view(request, estimate_id, token):
    """Public page for clients to view estimate and select optional items. No login required."""
    estimate = get_object_or_404(
        Estimate.objects.select_related("business", "customer"),
        id=estimate_id,
        view_token=token,
        status="sent",
    )
    base_items = list(estimate.line_items.filter(is_addon=False))
    optional_items = list(estimate.line_items.filter(is_addon=True))
    base_total = sum(item.line_total for item in base_items)
    doc_template = DocumentTemplate.get_default_for_business(estimate.business, "estimate")
    return render(request, "billing/estimate_client_view.html", {
        "estimate": estimate,
        "base_items": base_items,
        "optional_items": optional_items,
        "base_total": base_total,
        "token": token,
        "doc_template": doc_template,
        "images": estimate.images.all(),
    })


@require_POST
def estimate_client_accept(request, estimate_id, token):
    """Client accepts estimate with selected optional items."""
    estimate = get_object_or_404(
        Estimate.objects.select_related("business", "customer"),
        id=estimate_id,
        view_token=token,
        status="sent",
    )
    selected_ids = [int(x) for x in request.POST.getlist("optional_items") if str(x).isdigit()]
    base_total = sum(item.line_total for item in estimate.line_items.filter(is_addon=False))
    optional_total = sum(
        item.line_total for item in estimate.line_items.filter(is_addon=True, id__in=selected_ids)
    )
    total = base_total + optional_total
    estimate.status = "accepted"
    estimate.accepted_at = timezone.now()
    estimate.accepted_total = total
    estimate.save()
    
    # Update FertilizerApplication records with charge amount
    if estimate.accepted_total:
        for app in estimate.fertilizer_applications.all():
            app.charge_amount = estimate.accepted_total
            app.save(update_fields=['charge_amount', 'updated_at'])
    return render(request, "billing/estimate_client_accepted.html", {
        "estimate": estimate,
        "accepted_total": total,
    })


@require_POST
@role_required("owner", "manager")
def estimate_add_image(request, estimate_id):
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    caption = request.POST.get("caption", "").strip()

    files = request.FILES.getlist("images")
    if not files:
        messages.error(request, "No images selected.")
        return redirect("billing:estimate_edit", estimate_id=estimate.id)

    added = 0
    next_order = estimate.images.count()
    for uploaded in files:
        if uploaded.content_type not in ALLOWED_IMAGE_TYPES:
            messages.warning(request, f"Skipped {uploaded.name}: invalid file type.")
            continue
        if uploaded.size > MAX_UPLOAD_SIZE:
            messages.warning(request, f"Skipped {uploaded.name}: file too large (max 10 MB).")
            continue
        EstimateImage.objects.create(
            estimate=estimate,
            image=uploaded,
            caption=caption,
            order=next_order,
        )
        next_order += 1
        added += 1

    if added:
        messages.success(request, f"{added} image{'s' if added != 1 else ''} added.")
    return redirect("billing:estimate_edit", estimate_id=estimate.id)


@require_POST
@role_required("owner", "manager")
def estimate_delete_image(request, estimate_id, image_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    image = get_object_or_404(EstimateImage, id=image_id, estimate=estimate)
    image.image.delete(save=False)
    image.delete()
    messages.success(request, "Image removed.")
    return redirect("billing:estimate_edit", estimate_id=estimate.id)


# --- Document templates (customizable forms for estimates & invoices) ---

@role_required("owner", "manager")
def document_templates_list(request):
    """List document template types (estimate, invoice) with links to customize."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    estimate_template = DocumentTemplate.get_default_for_business(business, "estimate")
    invoice_template = DocumentTemplate.get_default_for_business(business, "invoice")
    return render(request, "billing/document_template_list.html", {
        "estimate_template": estimate_template,
        "invoice_template": invoice_template,
    })


@role_required("owner", "manager")
def document_template_edit(request, doc_type):
    """Edit the default template for estimates or invoices: style, colors, header/footer/terms, custom fields."""
    if doc_type not in ("estimate", "invoice"):
        return redirect("billing:document_templates_list")
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    template_obj = DocumentTemplate.get_or_create_default(business, doc_type)

    if request.method == "POST":
        form = DocumentTemplateForm(request.POST, instance=template_obj)
        if form.is_valid():
            template_obj = form.save(commit=False)
            if form.cleaned_data.get("template_key"):
                template_obj.template_key = form.cleaned_data["template_key"]
            template_obj.save()

            # Parse custom fields from POST (using indexed checkbox names to avoid misalignment)
            keys = request.POST.getlist("custom_field_key")
            labels = request.POST.getlist("custom_field_label")
            types = request.POST.getlist("custom_field_type")
            custom_fields = []
            seen_keys = set()
            for i in range(len(keys)):
                key = (keys[i] or "").strip().lower().replace(" ", "_") or None
                label = (labels[i] or "").strip() if i < len(labels) else ""
                field_type = (types[i] or "text") if i < len(types) else "text"
                if field_type not in ("text", "number", "date", "textarea"):
                    field_type = "text"
                required = request.POST.get(f"custom_field_required_{i}") == "on"
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    custom_fields.append({"key": key, "label": label or key.replace("_", " ").title(), "type": field_type, "required": bool(required)})
            template_obj.custom_fields = custom_fields
            template_obj.save()
            messages.success(request, f"{doc_type.title()} template saved.")
            return redirect("billing:document_templates_list")
    else:
        form = DocumentTemplateForm(instance=template_obj, initial={"template_key": template_obj.template_key or "professional"})

    return render(request, "billing/document_template_edit.html", {
        "form": form,
        "doc_type": doc_type,
        "template_obj": template_obj,
    })


# Fertilizer Product Management
@role_required("owner", "manager")
def fertilizer_products_list(request):
    """List all fertilizer products for the business."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    
    products = FertilizerProduct.objects.filter(business=business).order_by('name')
    return render(request, "billing/fertilizer_products_list.html", {
        "products": products,
    })


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def fertilizer_product_create(request):
    """Create a new fertilizer product."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Product name is required.")
            return redirect("billing:fertilizer_products_list")
        
        pricing_type = request.POST.get("pricing_type", "per_pound")
        cost_per_pound = request.POST.get("cost_per_pound") or None
        cost_per_bag = request.POST.get("cost_per_bag") or None
        lbs_per_bag = request.POST.get("lbs_per_bag") or None
        notes = request.POST.get("notes", "").strip()
        
        try:
            product = FertilizerProduct.objects.create(
                business=business,
                name=name,
                pricing_type=pricing_type,
                cost_per_pound=Decimal(cost_per_pound) if cost_per_pound else None,
                cost_per_bag=Decimal(cost_per_bag) if cost_per_bag else None,
                lbs_per_bag=Decimal(lbs_per_bag) if lbs_per_bag else None,
                notes=notes,
            )
            messages.success(request, f"Product '{product.name}' created.")
            return redirect("billing:fertilizer_products_list")
        except Exception as e:
            messages.error(request, f"Error creating product: {str(e)}")
            return redirect("billing:fertilizer_products_list")
    
    return render(request, "billing/fertilizer_product_form.html", {
        "product": None,
    })


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def fertilizer_product_edit(request, product_id):
    """Edit an existing fertilizer product."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    
    product = get_object_or_404(FertilizerProduct, id=product_id, business=business)
    
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Product name is required.")
            return redirect("billing:fertilizer_product_edit", product_id=product_id)
        
        pricing_type = request.POST.get("pricing_type", "per_pound")
        cost_per_pound = request.POST.get("cost_per_pound") or None
        cost_per_bag = request.POST.get("cost_per_bag") or None
        lbs_per_bag = request.POST.get("lbs_per_bag") or None
        active = request.POST.get("active") == "on"
        notes = request.POST.get("notes", "").strip()
        
        try:
            product.name = name
            product.pricing_type = pricing_type
            product.cost_per_pound = Decimal(cost_per_pound) if cost_per_pound else None
            product.cost_per_bag = Decimal(cost_per_bag) if cost_per_bag else None
            product.lbs_per_bag = Decimal(lbs_per_bag) if lbs_per_bag else None
            product.active = active
            product.notes = notes
            product.save()
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect("billing:fertilizer_products_list")
        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")
            return redirect("billing:fertilizer_product_edit", product_id=product_id)
    
    return render(request, "billing/fertilizer_product_form.html", {
        "product": product,
    })


@role_required("owner", "manager")
@require_POST
def fertilizer_product_delete(request, product_id):
    """Delete a fertilizer product."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    
    product = get_object_or_404(FertilizerProduct, id=product_id, business=business)
    product_name = product.name
    product.delete()
    messages.success(request, f"Product '{product_name}' deleted.")
    return redirect("billing:fertilizer_products_list")


@role_required("owner", "manager")
def property_fertilizer_history(request, property_id):
    """View fertilizer application history for a property."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    
    from customers.models import Property
    property_obj = get_object_or_404(Property, id=property_id, customer__business=business)
    
    applications = FertilizerApplication.objects.filter(
        business=business,
        property=property_obj
    ).select_related('product', 'job', 'estimate').order_by('-application_date')
    
    # Calculate totals
    total_pounds = sum(app.pounds_used for app in applications)
    total_cost = sum(app.material_cost for app in applications)
    total_charged = sum(app.charge_amount for app in applications if app.charge_amount)
    total_profit = sum(app.profit for app in applications if app.profit is not None)
    
    return render(request, "billing/property_fertilizer_history.html", {
        "property": property_obj,
        "applications": applications,
        "total_pounds": total_pounds,
        "total_cost": total_cost,
        "total_charged": total_charged,
        "total_profit": total_profit,
    })


# ── Estimate Queue / Field Capture ──────────────────────────────────────


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def field_capture(request):
    """Quick mobile form: capture customer, title, notes, and photos during a site visit."""
    from .forms import FieldCaptureForm

    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    if request.method == "POST":
        form = FieldCaptureForm(request.POST, business=business)
        if form.is_valid():
            estimate = form.save(commit=False)
            estimate.business = business
            estimate.status = "draft"
            estimate.save()

            # Handle multi-photo upload
            ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
            MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
            files = request.FILES.getlist("photos")
            added = 0
            for i, uploaded in enumerate(files):
                if uploaded.content_type not in ALLOWED_IMAGE_TYPES:
                    messages.warning(request, f"Skipped {uploaded.name}: invalid file type.")
                    continue
                if uploaded.size > MAX_UPLOAD_SIZE:
                    messages.warning(request, f"Skipped {uploaded.name}: file too large (max 10 MB).")
                    continue
                EstimateImage.objects.create(
                    estimate=estimate,
                    image=uploaded,
                    caption="",
                    order=i,
                )
                added += 1

            photo_msg = f" with {added} photo{'s' if added != 1 else ''}" if added else ""
            messages.success(request, f"Field capture saved for {estimate.customer.name}{photo_msg}.")
            return redirect("billing:estimate_queue")
    else:
        initial = {"site_visit_date": timezone.localdate()}
        form = FieldCaptureForm(business=business, initial=initial)
        customer_id = request.GET.get("customer")
        if customer_id:
            try:
                cust = Customer.objects.get(id=customer_id, business=business)
                form.initial["customer"] = cust.id
            except (Customer.DoesNotExist, ValueError):
                pass

    return render(request, "billing/field_capture.html", {"form": form})


@role_required("owner", "manager")
def estimate_queue(request):
    """List draft estimates with zero line items — quotes that need completing."""
    from django.db.models import Count

    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    queue = (
        Estimate.objects.filter(business=business, status="draft")
        .annotate(line_count=Count("line_items"))
        .filter(line_count=0)
        .select_related("customer")
        .prefetch_related("images")
        .order_by("-created_at")
    )

    return render(request, "billing/estimate_queue.html", {
        "queue": queue,
        "today": timezone.localdate(),
    })


@role_required("owner", "manager")
@require_POST
def estimate_queue_discard(request, estimate_id):
    """Delete a draft estimate from the queue."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business, status="draft")
    customer_name = estimate.customer.name
    estimate.delete()
    messages.success(request, f"Discarded draft for {customer_name}.")
    return redirect("billing:estimate_queue")
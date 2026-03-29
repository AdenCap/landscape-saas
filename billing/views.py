import hashlib
import secrets
import stripe
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from customers.models import Customer, ClientMessage, Property


def _email_template_vars(s, **kwargs):
    """Replace {{key}} placeholders in string s with values from kwargs."""
    if not s:
        return s
    out = s
    for key, val in kwargs.items():
        out = out.replace("{{" + key + "}}", str(val or ""))
    return out


def _get_logo_url(business, request=None):
    """Get logo URL that works in emails. Uses the app's logo proxy to ensure
    the image is served as PNG from our domain (avoids Supabase WebP/CORS issues)."""
    if not business or not business.logo:
        return None
    try:
        # Use the proxy endpoint — always serves PNG from our domain
        if request:
            return request.build_absolute_uri(f"/settings/logo/{business.id}.png")
        # Fallback: direct URL
        url = business.logo.url
        if url and url.startswith("http"):
            return url
        return None
    except Exception:
        return None
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

@role_required("owner", "manager")
def invoice_list_view(request):
    """Legacy invoice list view — redirects to the proper filtered endpoint."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    invoices = Invoice.objects.filter(business=business).order_by('-issue_date')[:100]
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
    can_accept_stripe = getattr(invoice.business, "can_accept_stripe_payments", lambda: False)() if invoice.business else False
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "items": items,
        "is_monthly_invoice": is_monthly,
        "audit_logs": audit_logs,
        "doc_template": doc_template,
        "can_accept_stripe": can_accept_stripe,
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
    """Owner can add/edit/delete line items on draft or sent invoices."""
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id).prefetch_related("line_items")
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)

    if invoice.status not in ("draft", "sent"):
        messages.error(request, "Only draft or sent invoices can be edited.")
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

        # Auto-charge card on file if enabled
        customer = invoice.customer
        charged = False
        if (customer.auto_charge and customer.stripe_payment_method_id
                and customer.stripe_customer_id and business.stripe_connect_account_id):
            try:
                import stripe as _stripe
                _stripe.api_key = settings.STRIPE_SECRET_KEY
                invoice.recompute_totals()
                amount_cents = int(invoice.total * 100)
                if amount_cents >= 50:
                    pi = _stripe.PaymentIntent.create(
                        amount=amount_cents,
                        currency="usd",
                        customer=customer.stripe_customer_id,
                        payment_method=customer.stripe_payment_method_id,
                        off_session=True,
                        confirm=True,
                        description=f"Invoice #{invoice.id} from {business.name}",
                        metadata={"invoice_id": invoice.id, "business_id": business.id},
                        stripe_account=business.stripe_connect_account_id,
                    )
                    if pi.status == "succeeded":
                        invoice.status = "paid"
                        invoice.save(update_fields=["status"])
                        _log_invoice_audit(invoice, "auto_charged", request=request, details={
                            "stripe_pi": pi.id, "amount": amount_cents, "card": customer.card_last4
                        })
                        charged = True
            except Exception:
                pass  # auto-charge failure should not block invoice send

        if charged:
            messages.success(request, f"Invoice #{invoice.id} sent and auto-charged to {customer.card_brand} ****{customer.card_last4}.")
        else:
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
    # Track client view
    now = timezone.now()
    if not invoice.first_viewed_at:
        invoice.first_viewed_at = now
    invoice.last_viewed_at = now
    invoice.view_count = (invoice.view_count or 0) + 1
    invoice.save(update_fields=["first_viewed_at", "last_viewed_at", "view_count"])

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
    paypal_link = None
    if (getattr(business, "paypal_link", "") or "").strip():
        pl = business.paypal_link.strip()
        if "@" in pl:
            paypal_link = f"https://paypal.me/{pl}"
        elif pl.startswith("http"):
            paypal_link = pl
        else:
            paypal_link = f"https://paypal.me/{pl}"
    can_accept_stripe = getattr(business, "can_accept_stripe_payments", lambda: False)()
    # Include PayPal in has_payment_methods check
    has_payment_methods = has_payment_methods or bool(paypal_link)
    line_items = invoice.line_items.all()
    return render(request, "billing/invoice_pay_page.html", {
        "invoice": invoice,
        "business": business,
        "has_payment_methods": has_payment_methods,
        "venmo_link": venmo_link,
        "cashapp_link": cashapp_link,
        "paypal_link": paypal_link,
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


@require_POST
@role_required("owner", "manager")
def invoice_delete(request, invoice_id):
    """Delete an invoice (draft or sent). Paid invoices cannot be deleted."""
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)
    if invoice.status == "paid":
        messages.error(request, "Paid invoices cannot be deleted. Void it instead.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)
    inv_id = invoice.id
    invoice.delete()
    messages.success(request, f"Invoice #{inv_id} has been deleted.")
    return redirect("billing:invoice_list")


@require_POST
@role_required("owner", "manager")
def convert_estimate_to_invoice(request, estimate_id):
    """Convert an accepted estimate into a draft invoice with all line items."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)

    if estimate.status not in ("accepted", "sent"):
        messages.error(request, "Only accepted or sent estimates can be converted to invoices.")
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    # Create the invoice
    from datetime import timedelta
    due_days = getattr(business, "default_invoice_due_days", None) or 30
    invoice = Invoice.objects.create(
        business=business,
        customer=estimate.customer,
        status="draft",
        due_date=timezone.localdate() + timedelta(days=int(due_days)),
    )

    # Copy line items from estimate to invoice
    for line in estimate.line_items.filter(is_addon=False):
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=line.description,
            quantity=line.quantity or 1,
            unit_price=line.line_total,  # Use the line total as the unit price
        )

    # Also copy accepted add-ons if they were selected
    if estimate.accepted_total and estimate.accepted_total > sum(
        item.line_total for item in estimate.line_items.filter(is_addon=False)
    ):
        for line in estimate.line_items.filter(is_addon=True):
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"{line.description} (add-on)",
                quantity=line.quantity or 1,
                unit_price=line.line_total,
            )

    invoice.recompute_totals()

    messages.success(request, f"Invoice #{invoice.id} created from estimate #{estimate.id}. Review and send when ready.")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@require_POST
@role_required("owner", "manager")
def estimate_delete(request, estimate_id):
    """Delete an estimate."""
    business = _get_business(request)
    qs = Estimate.objects.filter(id=estimate_id)
    if business:
        qs = qs.filter(customer__business=business)
    estimate = get_object_or_404(qs)
    est_id = estimate.id
    estimate.delete()
    messages.success(request, f"Estimate #{est_id} has been deleted.")
    return redirect("billing:estimate_list")


@require_POST
def invoice_customer_paid_notify(request, invoice_id, token):
    """Customer clicks 'I Paid' — notifies the business owner to confirm payment."""
    invoice = get_object_or_404(
        Invoice.objects.select_related("business", "customer"),
        id=invoice_id,
        payment_token=token,
    )
    if invoice.status != "sent":
        return JsonResponse({"status": "already_processed"})

    # Create a notification for the business owner(s)
    try:
        from accounts.models import Notification, User
        owners = User.objects.filter(
            business=invoice.business,
            role__in=["owner", "manager"],
            is_active=True,
        )
        system_user = owners.first()
        if system_user:
            for owner in owners:
                Notification.objects.create(
                    business=invoice.business,
                    from_user=system_user,
                    to_user=owner,
                    message=f"{invoice.customer.name} says they paid ${invoice.total} for Invoice #{invoice.id}. Confirm at /billing/{invoice.id}/",
                )
    except Exception:
        pass

    # Log the customer's claim
    _log_invoice_audit(invoice, "customer_claimed_paid")

    return JsonResponse({"status": "ok", "message": "Owner notified"})


@require_POST
@role_required("owner", "manager")
def invoice_toggle_card_payment(request, invoice_id):
    """Toggle credit card payment on/off for a specific invoice."""
    business = _get_business(request)
    qs = Invoice.objects.filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)
    data = json.loads(request.body) if request.body else {}
    invoice.enable_card_payment = bool(data.get("enable", True))
    invoice.save(update_fields=["enable_card_payment"])
    return JsonResponse({"status": "ok", "enable_card_payment": invoice.enable_card_payment})


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
    """Draw business logo on ReportLab canvas if present. Supports both local files and URL-based storage."""
    if not business or not business.logo:
        return
    try:
        import requests as _requests
        from reportlab.lib.utils import ImageReader
        from PIL import Image as PILImage
        import io
        import logging
        logger = logging.getLogger(__name__)

        if page_width is not None and x is None:
            x = page_width - 50 - max_width

        # Try multiple ways to get the logo image data
        img_data = None

        # Method 1: Try business.logo.url (Supabase returns full URL)
        try:
            logo_url = business.logo.url
            if logo_url and logo_url.startswith("http"):
                resp = _requests.get(logo_url, timeout=10)
                resp.raise_for_status()
                img_data = io.BytesIO(resp.content)
                logger.info("PDF logo: downloaded from %s (%d bytes)", logo_url[:60], len(resp.content))
        except Exception as e:
            logger.warning("PDF logo: URL download failed: %s", e)

        # Method 2: Try business.logo.open() (Django storage API)
        if not img_data:
            try:
                f = business.logo.open("rb")
                img_data = io.BytesIO(f.read())
                f.close()
                logger.info("PDF logo: read via storage API")
            except Exception as e:
                logger.warning("PDF logo: storage open failed: %s", e)

        if not img_data:
            logger.error("PDF logo: all methods failed for business %s", business.id)
            return

        # Convert to PNG via PIL to handle any format (webp, heic, etc)
        pil_img = PILImage.open(img_data)
        if pil_img.mode in ("RGBA", "LA", "P"):
            pil_img = pil_img.convert("RGBA")
        else:
            pil_img = pil_img.convert("RGB")
        png_buf = io.BytesIO()
        pil_img.save(png_buf, format="PNG")
        png_buf.seek(0)

        img_reader = ImageReader(png_buf)
        p.drawImage(img_reader, x, y_top - max_height, width=max_width, height=max_height,
                    preserveAspectRatio=True, mask='auto')
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("PDF logo failed: %s", exc)


def _pdf_safe(text, max_len=200):
    """Strip characters that ReportLab's built-in fonts can't render (emoji, CJK, etc.)."""
    if not text:
        return ""
    import re
    # Keep basic Latin, extended Latin, punctuation, common symbols
    cleaned = re.sub(r'[^\x20-\x7E\xA0-\xFF\u2013\u2014\u2018\u2019\u201C\u201D\u2026\u00B7]', '', str(text))
    return cleaned[:max_len]


# Theme colors for PDFs
_PDF_GREEN = (34 / 255, 197 / 255, 94 / 255)
_PDF_DARK = (0.09, 0.09, 0.09)
_PDF_MUTED = (0.64, 0.64, 0.64)
_PDF_BORDER = (0.15, 0.15, 0.15)
_PDF_WHITE = (1, 1, 1)
_PDF_LIGHT_BG = (0.97, 0.97, 0.97)  # #f7f7f7


def _pdf_fonts(font_style):
    """Return (heading_font, body_font) based on font_style choice."""
    if font_style == "serif":
        return "Times-Bold", "Times-Roman"
    elif font_style == "bold":
        return "Helvetica-Bold", "Helvetica"
    return "Helvetica-Bold", "Helvetica"  # clean default


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
    """Build professional invoice PDF — QuickBooks-quality layout with clear hierarchy."""
    canvas, LETTER = _get_reportlab()
    items = invoice.line_items.all()
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    business = invoice.business
    doc_template = DocumentTemplate.get_default_for_business(business, "invoice") if business else None
    accent = _hex_to_rgb(doc_template.primary_color) if doc_template and getattr(doc_template, "primary_color", None) else _PDF_GREEN
    accent_light = tuple(min(1.0, c * 0.12 + 0.88) for c in accent)
    accent_lighter = tuple(min(1.0, c * 0.06 + 0.94) for c in accent)
    style = doc_template.template_key if doc_template else "modern_dark"
    font_style = doc_template.font_style if doc_template else "clean"
    h_font, b_font = _pdf_fonts(font_style)
    margin = 50
    right = width - margin

    # ── Accent bar at top ──
    p.setFillColorRGB(*accent)
    p.rect(0, height - 6, width, 6, fill=True, stroke=False)

    # ── Header: Logo left, INVOICE right ──
    y = height - 50
    if business and business.logo:
        _draw_pdf_logo(p, business, x=margin, y_top=y + 10, max_height=44, max_width=140)

    # INVOICE title — large, right-aligned
    p.setFillColorRGB(*_PDF_DARK)
    p.setFont(h_font, 28)
    p.drawRightString(right, y - 2, "INVOICE")

    # Invoice number and dates — right-aligned below title
    p.setFont(b_font, 9)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawRightString(right, y - 18, f"Invoice #{invoice.id}")
    p.drawRightString(right, y - 30, f"Date: {invoice.issue_date}")
    if invoice.due_date:
        p.drawRightString(right, y - 42, f"Due: {invoice.due_date}")
    y -= 60

    # ── Header text (tagline/license) ──
    if doc_template and doc_template.header_text:
        p.setFont(b_font, 8)
        p.setFillColorRGB(*_PDF_MUTED)
        for line in doc_template.header_text.split("\n")[:2]:
            if line.strip():
                p.drawString(margin, y, line.strip()[:80])
                y -= 10
        y -= 4

    # ── Separator ──
    p.setStrokeColorRGB(*accent)
    p.setLineWidth(1.5)
    p.line(margin, y, right, y)
    y -= 24

    # ── Two-column: From (business) + Bill To (customer) ──
    col2_x = width / 2 + 20
    p.setFont(h_font, 8)
    p.setFillColorRGB(*accent)
    p.drawString(margin, y, "FROM")
    p.drawString(col2_x, y, "BILL TO")
    y -= 14

    p.setFont(h_font, 11)
    p.setFillColorRGB(*_PDF_DARK)
    if business:
        p.drawString(margin, y, business.name)
    p.drawString(col2_x, y, invoice.customer.name)
    y -= 14

    p.setFont(b_font, 9)
    p.setFillColorRGB(*_PDF_MUTED)
    from_lines = []
    if business:
        if business.contact_email:
            from_lines.append(business.contact_email)
        if business.contact_phone:
            from_lines.append(business.contact_phone)
    to_lines = []
    if invoice.customer.email:
        to_lines.append(invoice.customer.email)
    if invoice.customer.phone:
        to_lines.append(invoice.customer.phone)
    if invoice.customer.full_address and invoice.customer.full_address != "---":
        to_lines.append(invoice.customer.full_address[:50])

    for i in range(max(len(from_lines), len(to_lines))):
        if i < len(from_lines):
            p.drawString(margin, y, from_lines[i])
        if i < len(to_lines):
            p.drawString(col2_x, y, to_lines[i])
        y -= 12
    y -= 16

    # ── Line items table ──
    # Table header — accent background, white text
    header_h = 20
    p.setFillColorRGB(*accent)
    p.rect(margin, y - 4, right - margin, header_h, fill=True, stroke=False)
    p.setFillColorRGB(1, 1, 1)
    p.setFont(h_font, 8)
    p.drawString(margin + 10, y + 2, "DESCRIPTION")
    p.drawString(350, y + 2, "QTY")
    p.drawString(405, y + 2, "RATE")
    p.drawRightString(right - 10, y + 2, "AMOUNT")
    y -= 22

    # Line items
    p.setFillColorRGB(*_PDF_DARK)
    p.setFont(b_font, 9)
    computed_total = Decimal("0.00")
    row_idx = 0
    for item in items:
        if y < 120:
            p.showPage()
            y = height - 50
            p.setFont(b_font, 9)
            p.setFillColorRGB(*_PDF_DARK)

        row_h = 18
        # Alternating row shading
        if row_idx % 2 == 1:
            p.setFillColorRGB(*accent_lighter)
            p.rect(margin, y - 5, right - margin, row_h, fill=True, stroke=False)
            p.setFillColorRGB(*_PDF_DARK)

        lt = item.line_total
        computed_total += lt
        p.setFont(b_font, 9)
        p.drawString(margin + 10, y, _pdf_safe(str(item.description)[:48]))
        p.drawString(350, y, str(item.quantity or 1))
        if lt:
            p.drawString(405, y, _fmt_currency(item.unit_price) if item.unit_price else "")
            p.setFont(h_font, 9)
            p.drawRightString(right - 10, y, _fmt_currency(lt))
        else:
            p.setFont(h_font, 9)
        y -= row_h
        row_idx += 1

        # Detail description (optional, shown as smaller text below)
        detail = getattr(item, 'detail_description', '') or ''
        if detail.strip():
            p.setFont(b_font, 7.5)
            p.setFillColorRGB(0.45, 0.45, 0.45)
            for desc_line in detail.strip().split('\n')[:3]:
                p.drawString(margin + 14, y, _pdf_safe(desc_line[:70]))
                y -= 10
            p.setFillColorRGB(*_PDF_DARK)

        # Thin row separator
        p.setStrokeColorRGB(0.90, 0.90, 0.90)
        p.setLineWidth(0.3)
        p.line(margin, y + 1, right, y + 1)

    # ── Totals box ──
    y -= 8
    totals_x = 340
    total_to_show = getattr(invoice, "total", None) or computed_total

    # Separator
    p.setStrokeColorRGB(0.88, 0.88, 0.88)
    p.setLineWidth(0.5)
    p.line(totals_x, y + 4, right, y + 4)
    y -= 6

    # Subtotal
    p.setFont(b_font, 9)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawString(totals_x, y, "Subtotal")
    p.setFillColorRGB(*_PDF_DARK)
    p.drawRightString(right - 10, y, _fmt_currency(computed_total))
    y -= 16

    # Tax (if applicable)
    tax = getattr(invoice, "tax", None) or Decimal("0")
    if tax and tax > 0:
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(totals_x, y, "Tax")
        p.setFillColorRGB(*_PDF_DARK)
        p.drawRightString(right - 10, y, _fmt_currency(tax))
        y -= 16

    # Total due — highlighted box
    y -= 8
    total_box_h = 28
    p.setFillColorRGB(*accent)
    p.rect(totals_x - 10, y - 6, right - totals_x + 10, total_box_h, fill=True, stroke=False)
    total_label = "PAID" if invoice.status == "paid" else "AMOUNT DUE"
    p.setFillColorRGB(1, 1, 1)
    p.setFont(h_font, 10)
    p.drawString(totals_x, y + 4, total_label)
    p.setFont(h_font, 14)
    p.drawRightString(right - 10, y + 2, _fmt_currency(total_to_show))
    y -= total_box_h + 8

    # ── PAID stamp overlay ──
    if invoice.status == "paid":
        p.saveState()
        p.setFillColorRGB(0.13, 0.77, 0.37, 0.12)
        p.setFont(h_font, 72)
        p.translate(width / 2, height / 2)
        p.rotate(30)
        p.drawCentredString(0, 0, "PAID")
        p.restoreState()

    # ── Payment methods ──
    _has_payment = business and (
        (business.venmo_username or "").strip()
        or (business.zelle_email_or_phone or "").strip()
        or (business.cashapp_cashtag or "").strip()
        or (business.paypal_link or "").strip()
    )
    if _has_payment and y > 140:
        p.setFont(h_font, 8)
        p.setFillColorRGB(*accent)
        p.drawString(margin, y, "PAYMENT METHODS")
        y -= 14
        p.setFont(b_font, 9)
        p.setFillColorRGB(*_PDF_DARK)
        for label, handle in [
            ("Venmo", (business.venmo_username or "").strip()),
            ("Zelle", (business.zelle_email_or_phone or "").strip()),
            ("Cash App", (business.cashapp_cashtag or "").strip()),
            ("PayPal", (business.paypal_link or "").strip()),
        ]:
            if handle:
                p.drawString(margin, y, f"{label}: {handle[:50]}")
                y -= 13
        y -= 6

    # ── Terms & conditions ──
    if doc_template and doc_template.terms_and_conditions and y > 100:
        p.setStrokeColorRGB(0.88, 0.88, 0.88)
        p.setLineWidth(0.5)
        p.line(margin, y + 2, right, y + 2)
        y -= 10
        p.setFont(h_font, 7)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(margin, y, "TERMS & CONDITIONS")
        y -= 10
        p.setFont(b_font, 7)
        for line in (doc_template.terms_and_conditions or "").replace("\r", "").split("\n")[:6]:
            if line.strip() and y > 50:
                p.drawString(margin, y, line.strip()[:100])
                y -= 9

    # ── Footer bar ──
    # Footer text from template
    if doc_template and doc_template.footer_text:
        p.setFont(b_font, 7)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawCentredString(width / 2, 42, _pdf_safe(doc_template.footer_text, 80))

    # Company info footer
    p.setFont(b_font, 7)
    p.setFillColorRGB(*_PDF_MUTED)
    footer_text = ""
    if business:
        parts = [business.name]
        if business.contact_email:
            parts.append(business.contact_email)
        if business.contact_phone:
            parts.append(business.contact_phone)
        footer_text = "  |  ".join(parts)
    p.drawCentredString(width / 2, 30, footer_text)

    # Bottom accent bar
    p.setFillColorRGB(*accent)
    p.rect(0, 0, width, 4, fill=True, stroke=False)

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
    inline = request.GET.get("inline") == "1"
    response = FileResponse(BytesIO(pdf_bytes), as_attachment=not inline, filename=f"invoice_{invoice.id}.pdf")
    if inline:
        response["Content-Type"] = "application/pdf"
    return response


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

    from businesses.email_sender import send_business_email, is_email_configured, email_diagnostic
    if not is_email_configured(business):
        diag = email_diagnostic(business)
        if "Gmail permission not granted" in diag.get("oauth_status", ""):
            msg = "Gmail is linked but needs send permission. Go to Settings → Email and click 'Connect Gmail' to grant access."
        elif "App Password is missing" in diag.get("smtp_status", ""):
            msg = "Gmail address is saved but the App Password is missing. Go to Settings → Email and re-enter your App Password."
        else:
            msg = "Email isn't set up yet. Go to Settings → Email tab and connect Gmail or enter your App Password."
        messages.error(request, msg)
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    invoice.recompute_totals()
    pay_url = ""
    if invoice.payment_token:
        pay_url = request.build_absolute_uri(
            reverse("billing:invoice_pay_page", args=[invoice.id, invoice.payment_token])
        )

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

    logo_url = _get_logo_url(business, request)
    doc_template = DocumentTemplate.get_default_for_business(business, "invoice")
    accent_color = doc_template.primary_color if doc_template and getattr(doc_template, "primary_color", None) else "#22c55e"
    template_style = doc_template.template_key if doc_template else "modern_dark"
    html_content = render_to_string("billing/invoice_email.html", {
        "invoice": invoice,
        "business": business,
        "pay_url": pay_url,
        "logo_url": logo_url,
        "email_intro": intro,
        "email_closing": closing,
        "accent_color": accent_color,
        "template_style": template_style,
        "header_text": doc_template.header_text if doc_template else "",
        "footer_text": doc_template.footer_text if doc_template else "",
        "terms_text": doc_template.terms_and_conditions if doc_template else "",
    })

    ok, detail = send_business_email(
        business=business,
        to=invoice.customer.email,
        subject=subject,
        body_text=body_text,
        body_html=html_content,
        reply_to=reply_to,
    )
    if ok:
        messages.success(request, f"Invoice #{invoice.id} resent to {invoice.customer.email}.")
    else:
        from businesses.email_sender import format_send_error
        messages.error(request, format_send_error(detail))
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@require_POST
@role_required("owner", "manager")
def send_reminder(request, invoice_id):
    """Send a payment reminder email for an outstanding invoice."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    invoice = get_object_or_404(
        Invoice.objects.select_related("business", "customer"),
        id=invoice_id, business=business,
    )
    if invoice.status != "sent":
        messages.error(request, "Reminders can only be sent for outstanding invoices.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)
    if not invoice.customer.email:
        messages.error(request, f"{invoice.customer.name} has no email address.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    from businesses.email_sender import send_business_email, is_email_configured
    if not is_email_configured(business):
        messages.error(request, "Email isn't set up. Go to Settings → Email.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)

    invoice.recompute_totals()
    pay_url = ""
    if invoice.payment_token:
        pay_url = request.build_absolute_uri(
            reverse("billing:invoice_pay_page", args=[invoice.id, invoice.payment_token])
        )

    days_overdue = ""
    if invoice.due_date:
        from django.utils import timezone as tz
        delta = (tz.now().date() - invoice.due_date).days
        if delta > 0:
            days_overdue = f" This invoice is {delta} day{'s' if delta != 1 else ''} past due."

    subject = f"Payment Reminder: Invoice #{invoice.id} from {business.name}"
    intro = f"Hi {invoice.customer.name}, this is a friendly reminder that Invoice #{invoice.id} for ${invoice.total} is still outstanding.{days_overdue}"
    closing = "Please arrange payment at your earliest convenience. Thank you!"

    body_text = intro + "\n\n"
    if pay_url:
        body_text += f"Pay online: {pay_url}\n\n"
    body_text += closing + "\n\n" + business.name

    logo_url = _get_logo_url(business, request)
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
        "template_style": doc_template.template_key if doc_template else "modern_dark",
        "header_text": doc_template.header_text if doc_template else "",
        "footer_text": doc_template.footer_text if doc_template else "",
        "terms_text": doc_template.terms_and_conditions if doc_template else "",
    })

    reply_to = [business.contact_email] if business.contact_email else None
    ok, detail = send_business_email(
        business=business,
        to=invoice.customer.email,
        subject=subject,
        body_text=body_text,
        body_html=html_content,
        reply_to=reply_to,
    )
    if ok:
        messages.success(request, f"Payment reminder sent to {invoice.customer.email}.")
    else:
        from businesses.email_sender import format_send_error
        messages.error(request, format_send_error(detail))
    return redirect("billing:invoice_list")


# --- Estimates ---


@role_required("owner", "manager")
def estimate_list(request):
    from datetime import timedelta
    from django.db.models import Count

    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    tab = request.GET.get("tab", "estimates")

    estimates = Estimate.objects.filter(business=business).select_related("customer").order_by("-created_at")

    status_filter = request.GET.get("status") or "all"
    if status_filter == "accepted":
        estimates = estimates.filter(status="accepted")
    elif status_filter == "pending":
        estimates = estimates.exclude(status="accepted")
    # else: "all" — show everything

    stale_cutoff = timezone.now() - timedelta(days=5)
    stuck_quotes = Estimate.objects.filter(
        business=business,
        status__in=["draft", "sent"],
        created_at__lt=stale_cutoff,
    ).select_related("customer").order_by("created_at")[:6]

    # Quote queue: draft estimates with zero line items
    queue = (
        Estimate.objects.filter(business=business, status="draft")
        .annotate(line_count=Count("line_items"))
        .filter(line_count=0)
        .select_related("customer")
        .prefetch_related("images")
        .order_by("-created_at")
    )

    return render(request, "billing/estimate_list.html", {
        "estimates": estimates,
        "status_filter": status_filter,
        "stuck_quotes": stuck_quotes,
        "tab": tab,
        "queue": queue,
        "queue_count": queue.count(),
        "today": timezone.localdate(),
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
def api_customer_properties(request, customer_id):
    """Return JSON list of properties for a customer (AJAX endpoint)."""
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    try:
        customer = Customer.objects.get(id=customer_id, business=business)
    except Customer.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)
    props = Property.objects.filter(customer=customer).order_by('address')
    return JsonResponse({
        "properties": [{"id": p.id, "address": p.address} for p in props]
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
        # Auto-set valid_until from business default
        from datetime import timedelta
        valid_days = getattr(business, "default_estimate_valid_days", 30) or 30
        initial = {"valid_until": timezone.localdate() + timedelta(days=valid_days)}
        form = EstimateForm(business=business, initial=initial)
        customer_id = request.GET.get("customer")
        if customer_id:
            try:
                cust = Customer.objects.get(id=customer_id, business=business)
                form.initial["customer"] = cust
                # Auto-select property if customer has exactly one
                props = Property.objects.filter(customer=cust)
                if props.count() == 1:
                    form.initial["property"] = props.first()
                # Update the property queryset so Django renders options
                form.fields['property'].queryset = props
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
    
    from datetime import timedelta as _td
    valid_days = getattr(business, "default_estimate_valid_days", 30) or 30
    estimate = Estimate.objects.create(
        business=business,
        customer=customer,
        title=request.POST.get("title") or "FieldLgx Service Estimate",
        valid_until=timezone.localdate() + _td(days=valid_days),
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
    from datetime import timedelta as _td2
    valid_days2 = getattr(business, "default_estimate_valid_days", 30) or 30
    estimate = Estimate.objects.create(
        business=business,
        customer=customer,
        title=request.POST.get("title") or "FieldLgx Service Estimate",
        valid_until=timezone.localdate() + _td2(days=valid_days2),
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

    # Service pricing suggestions for the estimate
    from pricing.models import ServiceTemplate
    import json as _json
    prop = estimate.property
    sqft = prop.yard_sqft if prop else 0
    service_prices = []
    for svc in ServiceTemplate.objects.filter(business=business, active=True).order_by('name'):
        sp = {
            "id": svc.id,
            "name": svc.name,
            "method": svc.pricing_method,
            "rate": float(svc.default_rate),
            "unit": svc.default_unit,
            "suggested": float(svc.suggested_price_for_property(prop)) if prop else float(svc.default_rate),
            "display": svc.pricing_display(),
        }
        service_prices.append(sp)

    return render(request, "billing/estimate_edit.html", {
        "form": form, "formset": formset, "estimate": estimate, "doc_template": doc_template,
        "service_prices_json": _json.dumps(service_prices),
        "property_sqft": sqft,
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


def _build_estimate_pdf(estimate, business, compact=False):
    """Build premium estimate PDF matching the FieldLgx mockup design.
    compact=True generates a single-page version for simple jobs like mowing."""
    canvas, LETTER = _get_reportlab()
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    doc_template = DocumentTemplate.get_default_for_business(business, "estimate") if business else None
    accent = _hex_to_rgb(doc_template.primary_color) if doc_template and getattr(doc_template, "primary_color", None) else _PDF_GREEN
    accent_light = tuple(min(1.0, c * 0.15 + 0.85) for c in accent)
    h_font, b_font = _pdf_fonts(doc_template.font_style if doc_template else "clean")
    margin = 50
    right = width - margin
    mid = width / 2

    base_items = list(estimate.line_items.filter(is_addon=False))
    addon_items = list(estimate.line_items.filter(is_addon=True))
    base_total = sum(item.line_total for item in base_items)
    customer = estimate.customer
    est_num = f"EST-{estimate.created_at.year}-{estimate.id:04d}" if estimate.created_at else f"EST-{estimate.id}"

    def _page_footer():
        """Draw footer + accent bar on every page."""
        p.setFont(b_font, 7)
        p.setFillColorRGB(*_PDF_MUTED)
        parts = [business.name] if business else []
        if business and business.contact_email:
            parts.append(business.contact_email)
        if business and business.contact_phone:
            parts.append(business.contact_phone)
        p.drawCentredString(mid, 24, "  |  ".join(parts))
        # Page number
        p.drawRightString(right, 24, f"Page {p.getPageNumber()}")
        # Accent bar at bottom
        p.setFillColorRGB(*accent)
        p.rect(0, 0, width, 4, fill=True, stroke=False)

    # ═══════════════════════════════════════════════════════════════
    # PAGE 1: Header, Contact Info, Line Items
    # ═══════════════════════════════════════════════════════════════

    # ── Logo + Company Name (top left) ──
    y = height - 40
    if business and business.logo:
        _draw_pdf_logo(p, business, x=margin, y_top=y + 6, max_height=36, max_width=36)
    p.setFont(h_font, 14)
    p.setFillColorRGB(*_PDF_DARK)
    logo_x = margin + 44 if (business and business.logo) else margin
    p.drawString(logo_x, y - 6, _pdf_safe(business.name if business else ""))
    if doc_template and doc_template.header_text:
        p.setFont(b_font, 7)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(logo_x, y - 18, _pdf_safe(doc_template.header_text.split("\n")[0], 60))

    # ── ESTIMATE label + number (top right) ──
    p.setFont(h_font, 12)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawRightString(right, y - 2, "ESTIMATE")
    p.setFont(b_font, 9)
    p.drawRightString(right, y - 14, f"# {est_num}")
    p.drawRightString(right, y - 26, f"Issued {estimate.created_at.strftime('%B %d, %Y') if estimate.created_at else '---'}")
    if estimate.valid_until:
        p.drawRightString(right, y - 38, f"Valid through {estimate.valid_until.strftime('%B %d, %Y') if hasattr(estimate.valid_until, 'strftime') else estimate.valid_until}")
    y -= 56

    # ── Accent banner with project title ──
    banner_h = 56
    p.setFillColorRGB(*accent)
    p.rect(margin, y - banner_h + 10, right - margin, banner_h, fill=True, stroke=False)
    p.setFillColorRGB(1, 1, 1)
    p.setFont(h_font, 20)
    title_text = _pdf_safe(estimate.title, 50)
    p.drawString(margin + 16, y - 14, title_text)
    if estimate.notes:
        p.setFont(b_font, 8)
        p.drawString(margin + 16, y - 30, _pdf_safe(estimate.notes.split("\n")[0], 80))
    y -= banner_h + 8

    # ── Prepared By / Prepared For (bordered box) ──
    box_h = 80
    box_top = y
    # Left box
    p.setStrokeColorRGB(0.85, 0.85, 0.85)
    p.setLineWidth(0.5)
    p.rect(margin, box_top - box_h, mid - margin - 5, box_h, stroke=True, fill=False)
    # Right box
    p.rect(mid + 5, box_top - box_h, right - mid - 5, box_h, stroke=True, fill=False)

    # Prepared By content
    bx = margin + 12
    by = box_top - 14
    p.setFont(h_font, 10)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(bx, by, "Prepared By")
    by -= 14
    p.setFont(h_font, 9)
    p.drawString(bx, by, _pdf_safe(business.name if business else ""))
    by -= 11
    p.setFont(b_font, 8)
    p.setFillColorRGB(*_PDF_MUTED)
    for line in [
        business.contact_phone if business else "",
        business.contact_email if business else "",
    ]:
        if line and line.strip():
            p.drawString(bx, by, _pdf_safe(line))
            by -= 10

    # Prepared For content
    fx = mid + 17
    fy = box_top - 14
    p.setFont(h_font, 10)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(fx, fy, "Prepared For")
    fy -= 14
    p.setFont(h_font, 9)
    p.drawString(fx, fy, _pdf_safe(customer.name))
    fy -= 11
    p.setFont(b_font, 8)
    p.setFillColorRGB(*_PDF_MUTED)
    if customer.phone:
        p.drawString(fx, fy, _pdf_safe(customer.phone))
        fy -= 10
    addr = getattr(customer, "full_address", None)
    if addr and addr != "---":
        p.drawString(fx, fy, _pdf_safe(addr, 40))
        fy -= 10
    if customer.email:
        p.drawString(fx, fy, _pdf_safe(customer.email))

    y = box_top - box_h - 16

    # ── Estimate Details heading ──
    p.setFont(h_font, 13)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(margin, y, "Estimate Details")
    y -= 18

    # ── Line items table ──
    # Table header with thin top/bottom borders
    p.setStrokeColorRGB(0.8, 0.8, 0.8)
    p.setLineWidth(0.5)
    p.line(margin, y + 12, right, y + 12)
    p.line(margin, y - 4, right, y - 4)
    p.setFont(h_font, 8)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawString(margin + 6, y, "Item")
    p.drawString(margin + 100, y, "Description")
    p.drawString(370, y, "Qty")
    p.drawString(420, y, "Unit")
    p.drawRightString(right - 6, y, "Total")
    y -= 18

    # Line items
    for item in base_items:
        if y < 100:
            _page_footer()
            p.showPage()
            y = height - 50
        desc = str(item.description or "")
        # Item name (bold) — first part before any dash or newline
        item_name = desc.split(" - ")[0].split("\n")[0][:25] if " - " in desc or "\n" in desc else desc[:25]
        item_desc = desc[len(item_name):].lstrip(" -\n")[:50] if len(desc) > 25 else ""

        row_h = 28 if item_desc else 18
        # Alternating row shading
        if base_items.index(item) % 2 == 1:
            p.setFillColorRGB(0.97, 0.97, 0.97)
            p.rect(margin, y - 6, right - margin, row_h, fill=True, stroke=False)

        p.setFillColorRGB(*_PDF_DARK)
        p.setFont(h_font, 9)
        p.drawString(margin + 6, y, _pdf_safe(item_name))
        p.setFont(b_font, 8)
        p.setFillColorRGB(*_PDF_MUTED)
        if item_desc:
            p.drawString(margin + 100, y, _pdf_safe(item_desc))
        p.setFillColorRGB(*_PDF_DARK)
        p.setFont(b_font, 9)
        p.drawString(370, y, str(item.quantity or 1))
        lt = item.line_total
        if lt:
            p.drawString(420, y, _fmt_currency(item.unit_price) if item.unit_price else "")
            p.setFont(h_font, 9)
            p.drawRightString(right - 6, y, _fmt_currency(lt))
        else:
            p.setFont(h_font, 9)
        y -= 18

        # Detail description (optional)
        detail = getattr(item, 'detail_description', '') or ''
        if detail.strip():
            p.setFont(b_font, 7.5)
            p.setFillColorRGB(0.45, 0.45, 0.45)
            for desc_line in detail.strip().split('\n')[:3]:
                p.drawString(margin + 10, y, _pdf_safe(desc_line[:70]))
                y -= 10
            p.setFillColorRGB(*_PDF_DARK)

        p.setStrokeColorRGB(0.90, 0.90, 0.90)
        p.setLineWidth(0.3)
        p.line(margin, y + 4, right, y + 4)

    # ── Notes & Totals side by side ──
    if not compact:
        y -= 14
        notes_present = bool(estimate.notes)

        if notes_present and y > 140:
            # Notes box (left)
            notes_box_x = margin
            notes_box_w = mid - margin - 10
            p.setStrokeColorRGB(0.85, 0.85, 0.85)
            p.setLineWidth(0.5)
            notes_lines = [l.strip() for l in estimate.notes.replace("\r", "").split("\n") if l.strip()][:6]
            notes_box_h = max(60, 20 + len(notes_lines) * 11)
            p.roundRect(notes_box_x, y - notes_box_h + 8, notes_box_w, notes_box_h, 4, stroke=True, fill=False)
            p.setFont(h_font, 9)
            p.setFillColorRGB(*_PDF_DARK)
            p.drawString(notes_box_x + 10, y - 4, "Notes & Inclusions")
            p.setFont(b_font, 7)
            p.setFillColorRGB(*_PDF_MUTED)
            ny = y - 18
            for nl in notes_lines:
                p.drawString(notes_box_x + 10, ny, _pdf_safe(nl, 45))
                ny -= 11

        # Totals (right side or full width if no notes)
        totals_x = mid + 10 if notes_present else 340
        p.setFont(b_font, 9)
        p.setFillColorRGB(*_PDF_MUTED)
        ty = y - 4
        p.drawString(totals_x, ty, "Subtotal")
        p.setFillColorRGB(*_PDF_DARK)
        p.drawRightString(right - 6, ty, _fmt_currency(base_total))
        ty -= 16

        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(totals_x, ty, "Tax")
        p.drawRightString(right - 6, ty, "$0.00")
        ty -= 16

        # Total estimate box
        p.setFont(h_font, 10)
        p.setFillColorRGB(*_PDF_DARK)
        p.drawString(totals_x, ty, "Total Estimate")
        p.setFont(h_font, 14)
        p.drawRightString(right - 6, ty - 2, _fmt_currency(base_total))
        ty -= 20

    # ── Optional Upgrades (add-ons) ──
    if addon_items and not compact:
        if y < 160:
            _page_footer()
            p.showPage()
            y = height - 50
        else:
            y = ty - 20

        p.setFont(h_font, 12)
        p.setFillColorRGB(*_PDF_DARK)
        p.drawString(margin, y, "Optional Upgrades")
        y -= 16

        # Header
        p.setStrokeColorRGB(0.85, 0.85, 0.85)
        p.setLineWidth(0.5)
        p.line(margin, y + 10, right, y + 10)
        p.line(margin, y - 4, right, y - 4)
        p.setFont(h_font, 8)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawString(margin + 6, y, "Option")
        p.drawString(margin + 140, y, "Description")
        p.drawRightString(right - 6, y, "Price")
        y -= 18

        for item in addon_items:
            p.setFont(h_font, 9)
            p.setFillColorRGB(*_PDF_DARK)
            p.drawString(margin + 6, y, _pdf_safe(str(item.description)[:25]))
            p.setFont(b_font, 8)
            p.setFillColorRGB(*_PDF_MUTED)
            p.drawRightString(right - 6, y, _fmt_currency(item.line_total))
            y -= 18
            p.setStrokeColorRGB(0.92, 0.92, 0.92)
            p.line(margin, y + 6, right, y + 6)

    # If compact, put totals inline and skip page 2
    if compact:
        y -= 14
        totals_x = 340
        p.setStrokeColorRGB(0.85, 0.85, 0.85)
        p.setLineWidth(0.5)
        p.line(totals_x, y + 8, right, y + 8)

        p.setFont(h_font, 11)
        p.setFillColorRGB(*_PDF_DARK)
        p.drawString(totals_x, y - 4, "Total")
        p.setFont(h_font, 14)
        p.setFillColorRGB(*accent)
        p.drawRightString(right - 6, y - 4, _fmt_currency(base_total))
        y -= 30

        # Compact terms
        if doc_template and doc_template.terms_and_conditions:
            p.setFont(h_font, 7)
            p.setFillColorRGB(*_PDF_MUTED)
            p.drawString(margin, y, "TERMS")
            y -= 10
            p.setFont(b_font, 7)
            for line in doc_template.terms_and_conditions.replace("\r", "").split("\n")[:4]:
                if line.strip() and y > 40:
                    p.drawString(margin, y, _pdf_safe(line, 90))
                    y -= 9

        _page_footer()
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.read()

    # ═══════════════════════════════════════════════════════════════
    # PAGE 2: Approval & Terms
    # ═══════════════════════════════════════════════════════════════
    _page_footer()
    p.showPage()
    y = height - 50

    p.setFont(h_font, 22)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(margin, y, "Approval & Terms")
    y -= 30

    # ── Projected Timeline / Payment Terms (two columns) ──
    col_w = (right - margin - 10) / 2
    box_h = 70
    p.setStrokeColorRGB(0.85, 0.85, 0.85)
    p.setLineWidth(0.5)
    p.rect(margin, y - box_h, col_w, box_h, stroke=True, fill=False)
    p.rect(margin + col_w + 10, y - box_h, col_w, box_h, stroke=True, fill=False)

    # Left: Timeline
    lx = margin + 10
    ly = y - 14
    p.setFont(h_font, 10)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(lx, ly, "Projected Timeline")
    ly -= 14
    p.setFont(b_font, 8)
    p.setFillColorRGB(*_PDF_MUTED)
    for tl in ["Start Window: Upon approval", "Crew Size: As needed"]:
        p.drawString(lx, ly, tl)
        ly -= 11

    # Right: Payment Terms
    rx = margin + col_w + 20
    ry = y - 14
    p.setFont(h_font, 10)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(rx, ry, "Payment Terms")
    ry -= 14
    p.setFont(b_font, 8)
    p.setFillColorRGB(*_PDF_MUTED)
    deposit_text = ""
    if estimate.deposit_required and estimate.deposit_amount:
        if estimate.deposit_type == "percent":
            deposit_text = f"Deposit: {estimate.deposit_amount:.0f}% due upon approval"
        else:
            deposit_text = f"Deposit: ${estimate.deposit_amount:.2f} due upon approval"
    for pt in [
        deposit_text or "Due upon completion",
        "Accepted: ACH, card, or check",
    ]:
        if pt:
            p.drawString(rx, ry, pt)
            ry -= 11
    y -= box_h + 20

    # ── Terms & Conditions (bordered box) ──
    if doc_template and doc_template.terms_and_conditions:
        terms_lines = [l.strip() for l in doc_template.terms_and_conditions.replace("\r", "").split("\n") if l.strip()][:8]
        tc_h = max(50, 18 + len(terms_lines) * 11)
        p.setStrokeColorRGB(0.85, 0.85, 0.85)
        p.setLineWidth(0.5)
        p.roundRect(margin, y - tc_h, right - margin, tc_h, 4, stroke=True, fill=False)
        p.setFont(h_font, 9)
        p.setFillColorRGB(*_PDF_DARK)
        p.drawString(margin + 10, y - 14, "Terms & Conditions")
        p.setFont(b_font, 7)
        p.setFillColorRGB(*_PDF_MUTED)
        tcy = y - 28
        for i, tl in enumerate(terms_lines):
            p.drawString(margin + 10, tcy, f"{i+1}. {_pdf_safe(tl, 90)}")
            tcy -= 11
        y -= tc_h + 20

    # ── Client Approval section ──
    p.setFont(h_font, 14)
    p.setFillColorRGB(*accent)
    p.drawString(margin, y, "Client Approval")
    y -= 8
    p.setStrokeColorRGB(*accent)
    p.setLineWidth(1)
    p.line(margin, y, right, y)
    y -= 16

    p.setFont(b_font, 8)
    p.setFillColorRGB(*_PDF_MUTED)
    p.drawString(margin, y, "By signing below, I approve the work described in this estimate and authorize the contractor to proceed.")
    y -= 24

    # Signature lines
    p.setFont(h_font, 8)
    p.setFillColorRGB(*_PDF_DARK)
    sig_w = (right - margin - 20) / 3
    p.drawString(margin, y, "Client Signature")
    p.drawString(margin + sig_w + 10, y, "Printed Name")
    p.drawString(margin + 2 * sig_w + 20, y, "Date")
    y -= 4
    p.setStrokeColorRGB(*_PDF_MUTED)
    p.setLineWidth(0.5)
    p.line(margin, y, margin + sig_w, y)
    p.line(margin + sig_w + 10, y, margin + 2 * sig_w + 10, y)
    p.line(margin + 2 * sig_w + 20, y, right, y)
    y -= 24

    # Contractor signature + totals
    p.setFont(h_font, 8)
    p.setFillColorRGB(*_PDF_DARK)
    p.drawString(margin, y, "Contractor Signature")
    p.drawString(margin + sig_w + 10, y, "Approved Total")
    p.drawString(margin + 2 * sig_w + 20, y, "Deposit Due")
    y -= 4
    p.line(margin, y, margin + sig_w, y)
    y -= 14
    p.setFont(h_font, 11)
    p.drawString(margin + sig_w + 10, y, _fmt_currency(base_total))
    if estimate.deposit_required and estimate.deposit_amount:
        dep = estimate.deposit_amount
        if estimate.deposit_type == "percent":
            dep = base_total * estimate.deposit_amount / 100
        p.drawString(margin + 2 * sig_w + 20, y, _fmt_currency(dep))

    # Footer
    if doc_template and doc_template.footer_text:
        p.setFont(b_font, 7)
        p.setFillColorRGB(*_PDF_MUTED)
        p.drawCentredString(mid, 42, _pdf_safe(doc_template.footer_text, 80))

    _page_footer()
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
    compact = request.GET.get("compact") == "1"
    inline = request.GET.get("inline") == "1"
    pdf_bytes = _build_estimate_pdf(estimate, business, compact=compact)
    response = FileResponse(BytesIO(pdf_bytes), as_attachment=not inline, filename=f"estimate_{estimate.id}.pdf")
    if inline:
        response["Content-Type"] = "application/pdf"
    return response


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

    from businesses.email_sender import send_business_email, is_email_configured, email_diagnostic
    if not is_email_configured(business):
        diag = email_diagnostic(business)
        if "permission" in diag.get("oauth_status", "").lower():
            messages.error(request, "Gmail is connected but doesn't have send permission. Go to Settings → Email and click 'Connect Gmail' to grant send access.")
        else:
            messages.error(request, diag.get("message", "Email is not configured. Go to Settings → Email to set up Gmail."))
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    logo_url = _get_logo_url(business, request)
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
    template_style = doc_template.template_key if doc_template else "modern_dark"
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
        "template_style": template_style,
        "header_text": doc_template.header_text if doc_template else "",
        "footer_text": doc_template.footer_text if doc_template else "",
        "terms_text": doc_template.terms_and_conditions if doc_template else "",
    })

    plain_body = intro + "\n\nView and accept your estimate: " + (view_url or "") + "\n\n" + closing + "\n\n" + business.name
    reply_to = [business.contact_email] if business.contact_email else None

    ok, detail = send_business_email(
        business=business,
        to=customer.email,
        subject=subject,
        body_text=plain_body,
        body_html=html_content,
        reply_to=reply_to,
    )
    if ok:
        estimate.status = "sent"
        estimate.sent_at = timezone.now()
        estimate.save(update_fields=["status", "sent_at"])
        ClientMessage.objects.create(
            customer=customer,
            channel=ClientMessage.CHANNEL_EMAIL,
            direction=ClientMessage.DIRECTION_SENT,
            subject=subject,
            body=f"Estimate \u00ab{estimate.title}\u00bb sent to client. View estimate #{estimate.id} in Billing.",
            to_address=customer.email,
            created_by=request.user,
        )
        messages.success(request, f"Estimate sent to {customer.email}")
    else:
        from businesses.email_sender import format_send_error
        messages.error(request, format_send_error(detail))

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

    from businesses.email_sender import send_business_email, is_email_configured, email_diagnostic
    if not is_email_configured(business):
        diag = email_diagnostic(business)
        if "permission" in diag.get("oauth_status", "").lower():
            messages.error(request, "Gmail is connected but doesn't have send permission. Go to Settings → Email and click 'Connect Gmail' to grant send access.")
        else:
            messages.error(request, diag.get("message", "Email is not configured. Go to Settings → Email to set up Gmail."))
        return redirect("billing:estimate_detail", estimate_id=estimate.id)

    logo_url = _get_logo_url(business, request)
    subject = (
        _email_template_vars(
            (business.estimate_followup_email_subject or "").strip(),
            title=estimate.title,
            customer_name=customer.name,
            business_name=business.name,
        )
        or f"Reminder: {estimate.title} \u2013 {business.name}"
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
    closing = _email_template_vars(
        (business.estimate_email_closing or "").strip() or "We look forward to working with you.",
        customer_name=customer.name,
        business_name=business.name,
    )
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
        "template_style": doc_template.template_key if doc_template else "modern_dark",
        "header_text": doc_template.header_text if doc_template else "",
        "footer_text": doc_template.footer_text if doc_template else "",
        "terms_text": doc_template.terms_and_conditions if doc_template else "",
    })

    reply_to = [business.contact_email] if business.contact_email else None
    plain_body = intro + "\n\nView your estimate: " + view_url

    ok, detail = send_business_email(
        business=business,
        to=customer.email,
        subject=subject,
        body_text=plain_body,
        body_html=html_content,
        reply_to=reply_to,
    )
    if ok:
        estimate.last_follow_up_at = timezone.now()
        estimate.save(update_fields=["last_follow_up_at"])
        ClientMessage.objects.create(
            customer=customer,
            channel=ClientMessage.CHANNEL_EMAIL,
            direction=ClientMessage.DIRECTION_SENT,
            subject=subject,
            body=f"Estimate follow-up \u00ab{estimate.title}\u00bb sent to client.",
            to_address=customer.email,
            created_by=request.user,
        )
        messages.success(request, f"Follow-up sent to {customer.email}")
    else:
        from businesses.email_sender import format_send_error
        messages.error(request, format_send_error(detail))

    return redirect("billing:estimate_detail", estimate_id=estimate.id)


def estimate_client_view(request, estimate_id, token):
    """Public page for clients to view estimate and select optional items. No login required."""
    estimate = get_object_or_404(
        Estimate.objects.select_related("business", "customer"),
        id=estimate_id,
        view_token=token,
        status__in=["sent", "accepted"],
    )
    # Track client view
    now = timezone.now()
    if not estimate.first_viewed_at:
        estimate.first_viewed_at = now
    estimate.last_viewed_at = now
    estimate.view_count = (estimate.view_count or 0) + 1
    estimate.save(update_fields=["first_viewed_at", "last_viewed_at", "view_count"])

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
        # Save directly from POST to avoid form validation issues
        template_key = request.POST.get("template_key", "").strip()
        if template_key in ("modern_dark", "clean_light", "luxury"):
            template_obj.template_key = template_key

        name = request.POST.get("name", "").strip()
        if name:
            template_obj.name = name

        color = request.POST.get("primary_color", "").strip()
        if color and len(color) == 7 and color.startswith("#"):
            template_obj.primary_color = color

        template_obj.header_text = request.POST.get("header_text", "").strip()
        template_obj.footer_text = request.POST.get("footer_text", "").strip()
        template_obj.terms_and_conditions = request.POST.get("terms_and_conditions", "").strip()

        # Parse custom fields
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
        messages.success(request, f"{doc_type.title()} template saved successfully.")
        return redirect("billing:document_template_edit", doc_type=doc_type)

    # GET — build form just for rendering widgets (header_text, footer_text, etc.)
    form = DocumentTemplateForm(instance=template_obj)

    logo_url = _get_logo_url(business, request)

    return render(request, "billing/document_template_edit.html", {
        "form": form,
        "doc_type": doc_type,
        "template_obj": template_obj,
        "business": business,
        "logo_url": logo_url,
    })


@role_required("owner", "manager")
def email_template_preview(request, doc_type):
    """Render a preview of the email template with sample data."""
    if doc_type not in ("invoice", "estimate"):
        return JsonResponse({"error": "Invalid doc_type"}, status=400)
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    doc_template = DocumentTemplate.get_default_for_business(business, doc_type)
    accent_color = doc_template.primary_color if doc_template and getattr(doc_template, "primary_color", None) else "#22c55e"
    logo_url = _get_logo_url(business, request)

    if doc_type == "invoice":
        html = render_to_string("billing/invoice_email.html", {
            "invoice": type("Inv", (), {
                "id": 1042, "total": lambda: "170.00", "issue_date": "Mar 21, 2026", "due_date": "Apr 4, 2026",
                "customer": type("C", (), {"name": "John Smith"})(),
                "line_items": type("LI", (), {"all": lambda: [
                    type("I", (), {"description": "Weekly Mowing", "line_total": "85.00"})(),
                    type("I", (), {"description": "Edging & Blowing", "line_total": "25.00"})(),
                    type("I", (), {"description": "Bush Trimming", "line_total": "60.00"})(),
                ]})(),
            })(),
            "business": business,
            "pay_url": "#",
            "logo_url": logo_url,
            "email_intro": business.invoice_email_intro or "Hi John, please find your invoice below.",
            "email_closing": business.invoice_email_closing or "Thank you for your business.",
            "accent_color": accent_color,
            "template_style": doc_template.template_key if doc_template else "modern_dark",
            "header_text": doc_template.header_text if doc_template else "",
            "footer_text": doc_template.footer_text if doc_template else "",
            "terms_text": doc_template.terms_and_conditions if doc_template else "",
        })
    else:
        html = render_to_string("billing/estimate_email.html", {
            "estimate": type("Est", (), {
                "id": 205, "title": "Landscape Renovation Estimate",
                "valid_until": "Apr 30, 2026",
                "notes": "Work to begin within 2 weeks of acceptance.",
                "base_total": lambda: "2,450.00",
                "addons_total": lambda: 0,
                "deposit_required": False,
                "deposit_amount": None,
                "images": type("Imgs", (), {"exists": lambda: False})(),
                "line_items": type("LI", (), {"all": lambda: [
                    type("I", (), {"description": "Lawn Renovation (4,500 sq ft)", "line_total": "1,200.00", "is_addon": False})(),
                    type("I", (), {"description": "Mulch Installation (12 yards)", "line_total": "850.00", "is_addon": False})(),
                    type("I", (), {"description": "Shrub Planting (6 plants)", "line_total": "400.00", "is_addon": False})(),
                ]})(),
            })(),
            "customer": type("C", (), {"name": "Sarah Johnson"})(),
            "business": business,
            "request": request,
            "view_url": "#",
            "logo_url": logo_url,
            "email_intro": business.estimate_email_intro or "Hi Sarah, here is your estimate for the landscaping project.",
            "email_closing": business.estimate_email_closing or "We look forward to working with you.",
            "accent_color": accent_color,
            "template_style": doc_template.template_key if doc_template else "modern_dark",
            "header_text": doc_template.header_text if doc_template else "",
            "footer_text": doc_template.footer_text if doc_template else "",
            "terms_text": doc_template.terms_and_conditions if doc_template else "",
        })
    return HttpResponse(html, content_type="text/html")


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

        try:
            product = FertilizerProduct.objects.create(
                business=business,
                name=name,
                category=request.POST.get("category", "fertilizer"),
                product_type=request.POST.get("product_type", "granular"),
                pricing_type=request.POST.get("pricing_type", "per_pound"),
                cost_per_pound=Decimal(request.POST["cost_per_pound"]) if request.POST.get("cost_per_pound") else None,
                cost_per_bag=Decimal(request.POST["cost_per_bag"]) if request.POST.get("cost_per_bag") else None,
                lbs_per_bag=Decimal(request.POST["lbs_per_bag"]) if request.POST.get("lbs_per_bag") else None,
                nitrogen_pct=Decimal(request.POST["nitrogen_pct"]) if request.POST.get("nitrogen_pct") else None,
                phosphorus_pct=Decimal(request.POST["phosphorus_pct"]) if request.POST.get("phosphorus_pct") else None,
                potassium_pct=Decimal(request.POST["potassium_pct"]) if request.POST.get("potassium_pct") else None,
                application_rate=Decimal(request.POST["application_rate"]) if request.POST.get("application_rate") else None,
                epa_registration_number=request.POST.get("epa_registration_number", "").strip(),
                notes=request.POST.get("notes", "").strip(),
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

        try:
            product.name = name
            product.category = request.POST.get("category", "fertilizer")
            product.product_type = request.POST.get("product_type", "granular")
            product.pricing_type = request.POST.get("pricing_type", "per_pound")
            product.cost_per_pound = Decimal(request.POST["cost_per_pound"]) if request.POST.get("cost_per_pound") else None
            product.cost_per_bag = Decimal(request.POST["cost_per_bag"]) if request.POST.get("cost_per_bag") else None
            product.lbs_per_bag = Decimal(request.POST["lbs_per_bag"]) if request.POST.get("lbs_per_bag") else None
            product.nitrogen_pct = Decimal(request.POST["nitrogen_pct"]) if request.POST.get("nitrogen_pct") else None
            product.phosphorus_pct = Decimal(request.POST["phosphorus_pct"]) if request.POST.get("phosphorus_pct") else None
            product.potassium_pct = Decimal(request.POST["potassium_pct"]) if request.POST.get("potassium_pct") else None
            product.application_rate = Decimal(request.POST["application_rate"]) if request.POST.get("application_rate") else None
            product.epa_registration_number = request.POST.get("epa_registration_number", "").strip()
            product.active = request.POST.get("active") == "on"
            product.notes = request.POST.get("notes", "").strip()
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
            messages.success(request, f"Site visit saved for {estimate.customer.name}{photo_msg}.")
            return redirect("billing:estimate_queue")
    else:
        initial = {"site_visit_date": timezone.localdate()}
        form = FieldCaptureForm(business=business, initial=initial)
        customer_id = request.GET.get("customer")
        if customer_id:
            try:
                cust = Customer.objects.get(id=customer_id, business=business)
                form.initial["customer"] = cust.id
                # Auto-select property if customer has exactly one
                props = Property.objects.filter(customer=cust)
                if props.count() == 1:
                    form.initial["property"] = props.first().id
                form.fields['property'].queryset = props
            except (Customer.DoesNotExist, ValueError):
                pass

    return render(request, "billing/field_capture.html", {"form": form})


@role_required("owner", "manager")
def estimate_queue(request):
    """Redirect to the combined estimates page with queue tab active."""
    return redirect("/billing/estimates/?tab=queue")


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
    return redirect("/billing/estimates/?tab=queue")


# ── Promotions ──────────────────────────────────────────────

@role_required("owner", "manager")
def promotion_list(request):
    """List and manage promotions."""
    from .models import Promotion
    business = _get_business(request)
    if not business:
        return redirect("/")
    promos = Promotion.objects.filter(business=business).select_related("customer").order_by("-created_at")
    customers = Customer.objects.filter(business=business).order_by("name")
    return render(request, "billing/promotion_list.html", {
        "promos": promos,
        "customers": customers,
    })


@require_POST
@role_required("owner", "manager")
def promotion_create(request):
    """Create a new promotion."""
    from .models import Promotion
    business = _get_business(request)
    if not business:
        return redirect("/")
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Promotion name is required.")
        return redirect("billing:promotion_list")

    promo_type = request.POST.get("promo_type", "buy_x_get_free")
    customer_id = request.POST.get("customer_id")
    customer = None
    if customer_id:
        customer = Customer.objects.filter(id=customer_id, business=business).first()

    promo = Promotion.objects.create(
        business=business,
        customer=customer,
        name=name,
        promo_type=promo_type,
        service_name=request.POST.get("service_name", "").strip(),
        buy_quantity=int(request.POST.get("buy_quantity") or 0) or None,
        free_quantity=int(request.POST.get("free_quantity") or 1) or 1,
        discount_value=request.POST.get("discount_value") or None,
        notes=request.POST.get("notes", "").strip(),
    )
    messages.success(request, f"Promotion '{name}' created.")
    return redirect("billing:promotion_list")


@require_POST
@role_required("owner", "manager")
def promotion_update_count(request, promo_id):
    """Increment or set the current count for a buy-X-get-free promotion."""
    from .models import Promotion
    business = _get_business(request)
    promo = get_object_or_404(Promotion, id=promo_id, business=business)
    action = request.POST.get("action", "increment")
    if action == "increment":
        promo.current_count += 1
    elif action == "set":
        promo.current_count = int(request.POST.get("count", 0))
    promo.save(update_fields=["current_count"])
    messages.success(request, f"Updated count for '{promo.name}' to {promo.current_count}.")
    return redirect("billing:promotion_list")


@require_POST
@role_required("owner", "manager")
def promotion_redeem(request, promo_id):
    """Mark a promotion as redeemed."""
    from .models import Promotion
    business = _get_business(request)
    promo = get_object_or_404(Promotion, id=promo_id, business=business)
    promo.status = "redeemed"
    promo.save(update_fields=["status"])
    messages.success(request, f"'{promo.name}' marked as redeemed.")
    return redirect("billing:promotion_list")
import secrets
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.forms import modelformset_factory, inlineformset_factory
from django.http import FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from customers.models import Customer
from .models import Invoice, Estimate, EstimateLineItem, EstimateImage
from .forms import EstimateForm, EstimateLineItemForm, EstimateImageForm

def invoice_list_view(request):
    invoices = Invoice.objects.all().order_by('-issue_date')
    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices
    })


@role_required("owner")
def invoice_list(request):
    invoices = Invoice.objects.select_related("customer").order_by("-issue_date", "-id")[:50]
    return render(request, "billing/invoice_list.html", {"invoices": invoices})


@role_required("owner")
def invoice_detail(request, invoice_id):
    business = getattr(request.user, "business", None)
    qs = Invoice.objects.select_related("business", "customer").filter(id=invoice_id)
    if business:
        qs = qs.filter(business=business)
    invoice = get_object_or_404(qs)
    items = invoice.line_items.all()
    quickbooks_connected = bool(business and getattr(business, "quickbooks_connection", None))
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "items": items,
        "quickbooks_connected": quickbooks_connected,
    })


@require_POST
@role_required("owner")
def send_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Only allow draft -> sent
    if invoice.status == "draft":
        invoice.status = "sent"
        invoice.save(update_fields=["status"])

    return redirect("billing:invoice_detail", invoice_id=invoice.id)


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


def _draw_pdf_logo(p, business, x=50, y_top=770, max_height=48, max_width=160):
    """Draw business logo on ReportLab canvas if present."""
    if not business or not business.logo:
        return
    try:
        path = business.logo.path
        if not path:
            return
        p.drawImage(path, x, y_top - max_height, width=max_width, height=max_height)
    except Exception:
        pass


@role_required("owner")
def invoice_pdf(request, invoice_id):
    canvas, LETTER = _get_reportlab()
    invoice = get_object_or_404(
        Invoice.objects.select_related("business", "customer"),
        id=invoice_id,
    )
    items = invoice.line_items.all()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 40
    business = invoice.business
    if business and business.logo:
        _draw_pdf_logo(p, business, x=50, y_top=y + 10, max_height=44, max_width=140)
        p.setFont("Helvetica-Bold", 20)
        p.drawString(50, y - 28, f"Invoice #{invoice.id}")
        y -= 50
    else:
        p.setFont("Helvetica-Bold", 20)
        p.drawString(50, y, f"Invoice #{invoice.id}")
        y -= 28

    p.setFont("Helvetica", 10)
    p.setFillColorRGB(0.4, 0.45, 0.55)
    p.drawString(50, y, f"Issue date: {invoice.issue_date}")
    y -= 14
    p.drawString(50, y, f"Due date: {invoice.due_date or '—'}")
    y -= 14
    p.setFillColorRGB(0.1, 0.1, 0.15)
    p.drawString(50, y, f"Bill to: {invoice.customer.name}")
    y -= 14
    if invoice.customer.full_address:
        p.setFont("Helvetica", 9)
        p.drawString(50, y, invoice.customer.full_address[:60])
        y -= 12
    p.setFont("Helvetica", 10)
    y -= 8

    p.setFillColorRGB(0.1, 0.1, 0.15)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(450, y, "Total")
    y -= 18

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

    y -= 6
    p.setFont("Helvetica-Bold", 12)
    total_to_show = getattr(invoice, "total", None) or computed_total
    p.drawRightString(560, y, f"Total: {_fmt_currency(total_to_show)}")

    p.showPage()
    p.save()
    buffer.seek(0)

    return FileResponse(buffer, as_attachment=True, filename=f"invoice_{invoice.id}.pdf")


# --- Estimates ---

def _get_business(request):
    return getattr(request.user, "business", None)


@role_required("owner")
def estimate_list(request):
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

    return render(request, "billing/estimate_list.html", {
        "estimates": estimates,
        "status_filter": status_filter,
    })


@role_required("owner")
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

    return render(request, "billing/estimate_form.html", {"form": form, "title": "Create Estimate"})


@role_required("owner")
@require_http_methods(["GET", "POST"])
def estimate_edit(request, estimate_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)

    LineItemFormSet = inlineformset_factory(
        Estimate, EstimateLineItem, form=EstimateLineItemForm,
        extra=2, can_delete=True
    )

    if request.method == "POST":
        form = EstimateForm(request.POST, instance=estimate, business=business)
        formset = LineItemFormSet(request.POST, instance=estimate)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Estimate updated.")
            return redirect("billing:estimate_detail", estimate_id=estimate.id)
    else:
        form = EstimateForm(instance=estimate, business=business)
        formset = LineItemFormSet(instance=estimate)

    return render(request, "billing/estimate_edit.html", {
        "form": form, "formset": formset, "estimate": estimate,
    })


@role_required("owner")
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
    return render(request, "billing/estimate_detail.html", {"estimate": estimate})


def _build_estimate_pdf(estimate, business):
    """Build estimate PDF bytes (with logo if business has one)."""
    canvas, LETTER = _get_reportlab()
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 40
    if business and business.logo:
        _draw_pdf_logo(p, business, x=50, y_top=y + 10, max_height=44, max_width=140)
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, y - 28, estimate.title)
        y -= 50
    else:
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, y, estimate.title)
        y -= 28

    p.setFont("Helvetica", 10)
    p.setFillColorRGB(0.4, 0.45, 0.55)
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
    p.setFillColorRGB(0.1, 0.1, 0.15)
    y -= 10

    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(450, y, "Total")
    y -= 18

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

    if addon_items.exists():
        y -= 6
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(50, y, "Optional items:")
        y -= 16
        p.setFont("Helvetica", 10)
        for item in addon_items:
            p.drawString(50, y, str(item.description)[:50])
            p.drawRightString(560, y, _fmt_currency(item.line_total))
            y -= 16
            if y < 100:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 10)

    y -= 8
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(560, y, f"Total: {_fmt_currency(estimate.total())}")

    if estimate.notes:
        y -= 24
        p.setFont("Helvetica", 9)
        for line in estimate.notes.split("\n")[:8]:
            p.drawString(50, y, line[:80])
            y -= 12
            if y < 80:
                break

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.read()


@role_required("owner")
def estimate_pdf(request, estimate_id):
    business = _get_business(request)
    if not business:
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    pdf_bytes = _build_estimate_pdf(estimate, business)
    return FileResponse(BytesIO(pdf_bytes), as_attachment=True, filename=f"estimate_{estimate.id}.pdf")


@require_POST
@role_required("owner")
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
    html_content = render_to_string("billing/estimate_email.html", {
        "estimate": estimate,
        "customer": customer,
        "business": business,
        "request": request,
        "view_url": view_url,
        "logo_url": logo_url,
    })

    subject = f"{estimate.title} - {business.name}"
    from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@landscape.local")
    reply_to = [business.contact_email] if business.contact_email else None
    msg = EmailMultiAlternatives(
        subject,
        "Please see the attached estimate.",
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
        messages.success(request, f"Estimate sent to {customer.email}")
    except Exception as e:
        messages.error(request, f"Failed to send: {str(e)}")

    return redirect("billing:estimate_detail", estimate_id=estimate.id)


@require_POST
@role_required("owner")
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
    html_content = render_to_string("billing/estimate_followup_email.html", {
        "estimate": estimate,
        "customer": customer,
        "business": business,
        "view_url": view_url,
        "logo_url": logo_url,
    })

    subject = f"Reminder: {estimate.title} - {business.name}"
    from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@landscape.local")
    reply_to = [business.contact_email] if business.contact_email else None
    msg = EmailMultiAlternatives(
        subject,
        f"Friendly reminder about your estimate from {business.name}. View it here: {view_url}",
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
        from django.utils import timezone
        estimate.last_follow_up_at = timezone.now()
        estimate.save(update_fields=["last_follow_up_at"])
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
    return render(request, "billing/estimate_client_view.html", {
        "estimate": estimate,
        "base_items": base_items,
        "optional_items": optional_items,
        "base_total": base_total,
        "token": token,
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
    return render(request, "billing/estimate_client_accepted.html", {
        "estimate": estimate,
        "accepted_total": total,
    })


@require_POST
@role_required("owner")
def estimate_add_image(request, estimate_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    form = EstimateImageForm(request.POST, request.FILES)
    if form.is_valid():
        img = form.save(commit=False)
        img.estimate = estimate
        img.save()
        messages.success(request, "Image added.")
    else:
        messages.error(request, "Invalid image upload.")
    return redirect("billing:estimate_edit", estimate_id=estimate.id)
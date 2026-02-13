from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.forms import modelformset_factory, inlineformset_factory
from django.http import FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

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
    invoice = get_object_or_404(Invoice, id=invoice_id)
    items = invoice.line_items.all()
    return render(request, "billing/invoice_detail.html", {"invoice": invoice, "items": items})


@require_POST
@role_required("owner")
def send_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Only allow draft -> sent
    if invoice.status == "draft":
        invoice.status = "sent"
        invoice.save(update_fields=["status"])

    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@role_required("owner")
def invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    items = invoice.line_items.all()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 50
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Invoice #{invoice.id}")
    y -= 25

    p.setFont("Helvetica", 10)
    p.drawString(50, y, f"Issue Date: {invoice.issue_date}")
    y -= 14
    p.drawString(50, y, f"Due Date: {invoice.due_date}")
    y -= 14
    p.drawString(50, y, f"Customer: {invoice.customer}")
    y -= 14
    p.drawString(50, y, f"Status: {invoice.status}")
    y -= 25

    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(320, y, "Qty")
    p.drawString(380, y, "Unit Price")
    p.drawString(470, y, "Line Total")
    y -= 15

    p.setFont("Helvetica", 10)

    computed_total = Decimal("0.00")
    for item in items:
        line_total = item.quantity * item.unit_price
        computed_total += line_total

        p.drawString(50, y, str(item.description)[:45])
        p.drawRightString(350, y, str(item.quantity))
        p.drawRightString(440, y, f"${item.unit_price}")
        p.drawRightString(540, y, f"${line_total}")
        y -= 15

        if y < 80:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 10)

    y -= 10
    p.setFont("Helvetica-Bold", 12)
    total_to_show = getattr(invoice, "total", None) or computed_total
    p.drawRightString(540, y, f"Total: ${total_to_show}")

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
    return render(request, "billing/estimate_list.html", {"estimates": estimates})


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

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    return render(request, "billing/estimate_detail.html", {"estimate": estimate})


@role_required("owner")
def estimate_pdf(request, estimate_id):
    business = _get_business(request)
    if not business:
        return redirect("/")

    estimate = get_object_or_404(Estimate, id=estimate_id, business=business)
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    y = height - 50
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, estimate.title)
    y -= 20
    p.setFont("Helvetica", 10)
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
    y -= 10

    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(320, y, "Qty")
    p.drawString(380, y, "Unit")
    p.drawString(430, y, "Unit Price")
    p.drawString(500, y, "Total")
    y -= 15

    p.setFont("Helvetica", 10)
    base_items = estimate.line_items.filter(is_addon=False)
    addon_items = estimate.line_items.filter(is_addon=True)

    for item in base_items:
        lt = item.line_total()
        p.drawString(50, y, str(item.description)[:40])
        p.drawRightString(350, y, str(item.quantity))
        p.drawString(360, y, str(item.unit)[:6])
        p.drawRightString(450, y, f"${item.unit_price}")
        p.drawRightString(560, y, f"${lt}")
        y -= 14
        if y < 100:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 10)

    if addon_items.exists():
        y -= 5
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(50, y, "Optional add-ons:")
        y -= 14
        p.setFont("Helvetica", 10)
        for item in addon_items:
            lt = item.line_total()
            p.drawString(50, y, str(item.description)[:40])
            p.drawRightString(350, y, str(item.quantity))
            p.drawRightString(450, y, f"${item.unit_price}")
            p.drawRightString(560, y, f"${lt}")
            y -= 14
            if y < 100:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 10)

    y -= 10
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(560, y, f"Total: ${estimate.total()}")

    if estimate.notes:
        y -= 25
        p.setFont("Helvetica", 9)
        for line in estimate.notes.split("\n")[:8]:
            p.drawString(50, y, line[:80])
            y -= 12
            if y < 80:
                break

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"estimate_{estimate.id}.pdf")


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

    html_content = render_to_string("billing/estimate_email.html", {
        "estimate": estimate,
        "customer": customer,
        "business": business,
        "request": request,
    })

    subject = f"{estimate.title} - {business.name}"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@landscape.local")
    msg = EmailMultiAlternatives(subject, "Please see the attached estimate.", from_email, [customer.email])
    msg.attach_alternative(html_content, "text/html")

    # Attach PDF
    buffer = BytesIO()
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas as pdf_canvas
    p = pdf_canvas.Canvas(buffer, pagesize=LETTER)
    w, h = LETTER
    y = h - 50
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, estimate.title)
    y -= 25
    p.setFont("Helvetica", 10)
    p.drawString(50, y, f"Estimate #{estimate.id} - {customer.name}")
    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Description")
    p.drawString(320, y, "Qty")
    p.drawString(430, y, "Unit Price")
    p.drawString(500, y, "Total")
    y -= 15
    p.setFont("Helvetica", 10)
    for item in estimate.line_items.all():
        lt = item.line_total()
        addon = " (optional)" if item.is_addon else ""
        p.drawString(50, y, str(item.description)[:40] + addon)
        p.drawRightString(350, y, str(item.quantity))
        p.drawRightString(450, y, f"${item.unit_price}")
        p.drawRightString(560, y, f"${lt}")
        y -= 14
        if y < 80:
            p.showPage()
            y = h - 50
            p.setFont("Helvetica", 10)
    y -= 10
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(560, y, f"Total: ${estimate.total()}")
    p.showPage()
    p.save()
    buffer.seek(0)
    msg.attach(f"estimate_{estimate.id}.pdf", buffer.read(), "application/pdf")

    try:
        msg.send()
        estimate.status = "sent"
        estimate.sent_at = timezone.now()
        estimate.save()
        messages.success(request, f"Estimate sent to {customer.email}")
    except Exception as e:
        messages.error(request, f"Failed to send: {str(e)}")

    return redirect("billing:estimate_detail", estimate_id=estimate.id)


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
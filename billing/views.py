from django.shortcuts import render, get_object_or_404, redirect
from .models import Invoice
from accounts.decorators import role_required

from io import BytesIO
from decimal import Decimal

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.decorators import role_required
from .models import Invoice

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from django.views.decorators.http import require_POST

from io import BytesIO
from decimal import Decimal

from django.http import FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from accounts.decorators import role_required
from .models import Invoice

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
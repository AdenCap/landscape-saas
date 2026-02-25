from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Sum, Q
from django.utils import timezone

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from billing.models import Invoice
from jobs.models import Job
from .models import Customer, Property, Contract, ClientMessage
from django.utils import timezone
from .forms import (
    CustomerForm,
    CustomerImportForm,
    parse_csv_customers,
    PropertyForm,
    ContractForm,
    SendMessageForm,
)


@role_required("owner")
def customer_list(request):
    """CRM home: list all customers with search."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view clients.")
        return redirect("/")

    search = request.GET.get("q", "").strip()
    customers = Customer.objects.filter(business=business)

    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(address_line1__icontains=search) |
            Q(city__icontains=search)
        )

    # Annotate with property and invoice counts (distinct=True so the JOIN doesn't inflate counts)
    customers = customers.annotate(
        property_count=Count('properties', distinct=True),
        invoice_count=Count('invoices', distinct=True),
    ).select_related('business').order_by('name')

    return render(request, "customers/customer_list.html", {
        "customers": customers,
        "search": search,
    })


@role_required("owner")
def client_messages_list(request):
    """Dedicated client messaging hub: all messages, search, send new, reply."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view messages.")
        return redirect("/")

    messages_search_q = (request.GET.get("q") or "").strip()
    qs = (
        ClientMessage.objects.filter(customer__business=business)
        .select_related("customer")
        .order_by("-created_at")
    )
    if messages_search_q:
        qs = qs.filter(
            Q(customer__name__icontains=messages_search_q)
            | Q(body__icontains=messages_search_q)
            | Q(subject__icontains=messages_search_q)
            | Q(to_address__icontains=messages_search_q)
        )
    client_messages = list(qs[:200])
    unread_messages_count = ClientMessage.objects.filter(
        customer__business=business,
        direction=ClientMessage.DIRECTION_RECEIVED,
        is_read=False,
    ).count()
    customers_list = list(Customer.objects.filter(business=business).order_by("name"))

    return render(request, "customers/client_messages_list.html", {
        "client_messages": client_messages,
        "messages_search_q": messages_search_q,
        "unread_messages_count": unread_messages_count,
        "customers_list": customers_list,
        "send_message_form": SendMessageForm(),
    })


@role_required("owner")
def customer_detail(request, customer_id):
    """Full CRM profile: contact info, properties, past services, contracts, invoices."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)

    properties = customer.properties.all().prefetch_related('jobs', 'recurring_jobs')

    # Past services = completed jobs across all properties
    past_jobs = (
        Job.objects.filter(property__customer=customer, status='completed')
        .select_related('property', 'assigned_to')
        .order_by('-scheduled_date')[:20]
    )

    contracts = customer.contracts.all().order_by('-created_at')

    invoices = (
        Invoice.objects.filter(customer=customer)
        .order_by('-issue_date')[:15]
    )

    total_revenue = Invoice.objects.filter(customer=customer, status='paid').aggregate(
        total=Sum('total')
    )['total'] or 0

    # Mark received messages as read when viewing the client profile
    customer.messages.filter(direction=ClientMessage.DIRECTION_RECEIVED, is_read=False).update(is_read=True)

    client_messages = customer.messages.all()[:50]
    send_message_form = SendMessageForm()

    # Get payment methods if customer has Stripe customer ID and business has Connect
    payment_methods = []
    has_saved_payment_method = False
    if customer.stripe_customer_id and business.stripe_connect_account_id and business.stripe_connect_charges_enabled:
        try:
            import stripe
            from django.conf import settings
            if getattr(settings, "STRIPE_SECRET_KEY", None):
                stripe.api_key = settings.STRIPE_SECRET_KEY
                payment_methods_list = stripe.PaymentMethod.list(
                    customer=customer.stripe_customer_id,
                    type="card",
                    stripe_account=business.stripe_connect_account_id,
                )
                payment_methods = payment_methods_list.data
                has_saved_payment_method = len(payment_methods) > 0
        except Exception:
            pass  # If Stripe call fails, just don't show payment methods

    return render(request, "customers/customer_detail.html", {
        "customer": customer,
        "properties": properties,
        "past_jobs": past_jobs,
        "contracts": contracts,
        "invoices": invoices,
        "total_revenue": total_revenue,
        "client_messages": client_messages,
        "send_message_form": send_message_form,
        "payment_methods": payment_methods,
        "has_saved_payment_method": has_saved_payment_method,
        "stripe_connect_enabled": bool(business.stripe_connect_account_id and business.stripe_connect_charges_enabled),
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def customer_create(request):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to add clients.")
        return redirect("/")

    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.business = business
            customer.save()
            messages.success(request, f"Client '{customer.name}' added successfully.")
            next_url = request.GET.get("next")
            if next_url == "estimate_and_select":
                return redirect("billing:estimate_create" + "?customer=" + str(customer.id))
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = CustomerForm()

    next_param = request.GET.get("next")
    return render(request, "customers/customer_form.html", {
        "form": form,
        "title": "Add New Client",
        "return_to_estimate": next_param in ("estimate", "estimate_and_select"),
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def customer_import(request):
    """Bulk import clients from a CSV file (first row = headers)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to import clients.")
        return redirect("/")

    if request.method == "POST":
        form = CustomerImportForm(request.POST, request.FILES)
        if form.is_valid():
            created = 0
            errors = []
            try:
                for customer, err in parse_csv_customers(request.FILES["csv_file"], business):
                    if err:
                        errors.append(err)
                        continue
                    customer.save()
                    created += 1
            except Exception as e:
                messages.error(request, f"Error reading CSV: {e}")
                return render(request, "customers/customer_import.html", {"form": form})

            if created:
                messages.success(request, f"Imported {created} client(s) successfully.")
            if errors:
                for err in errors[:10]:
                    messages.warning(request, err)
                if len(errors) > 10:
                    messages.warning(request, f"... and {len(errors) - 10} more row(s) skipped.")
            if not created and not errors:
                messages.warning(request, "No valid rows found. Ensure the first row has headers (e.g. name, email, phone).")
            return redirect("customer_list")
    else:
        form = CustomerImportForm()

    return render(request, "customers/customer_import.html", {"form": form})


@role_required("owner")
@require_http_methods(["GET", "POST"])
def customer_edit(request, customer_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Client '{customer.name}' updated.")
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = CustomerForm(instance=customer)

    return render(request, "customers/customer_form.html", {
        "form": form,
        "customer": customer,
        "title": "Edit Client",
    })


@role_required("owner")
def customer_communication_history(request, customer_id):
    """View all communication history for a customer in one place."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    
    customer = get_object_or_404(Customer, id=customer_id, business=business)
    
    # Get all communications
    messages = customer.messages.all().order_by('-created_at')
    invoices = customer.invoices.all().order_by('-issue_date')
    estimates = customer.estimates.all().order_by('-created_at')
    jobs = Job.objects.filter(property__customer=customer).order_by('-scheduled_date')
    reviews = []
    surveys = []
    
    # Try to get reviews and surveys if apps are installed
    try:
        from reviews.models import Review
        reviews = Review.objects.filter(customer=customer).order_by('-created_at')
    except ImportError:
        pass
    
    try:
        from surveys.models import Survey
        surveys = Survey.objects.filter(customer=customer).order_by('-completed_at')
    except ImportError:
        pass
    
    # Combine and sort by date
    timeline = []
    for msg in messages:
        timeline.append({
            'type': 'message',
            'date': msg.created_at,
            'object': msg,
        })
    for inv in invoices:
        timeline.append({
            'type': 'invoice',
            'date': inv.issue_date,
            'object': inv,
        })
    for est in estimates:
        timeline.append({
            'type': 'estimate',
            'date': est.created_at,
            'object': est,
        })
    for job in jobs:
        if job.scheduled_date:
            timeline.append({
                'type': 'job',
                'date': job.scheduled_date,
                'object': job,
            })
    for review in reviews:
        timeline.append({
            'type': 'review',
            'date': review.created_at,
            'object': review,
        })
    for survey in surveys:
        timeline.append({
            'type': 'survey',
            'date': survey.completed_at,
            'object': survey,
        })
    
    timeline.sort(key=lambda x: x['date'], reverse=True)
    
    return render(request, "customers/customer_communication_history.html", {
        "customer": customer,
        "timeline": timeline[:50],  # Last 50 items
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def property_add(request, customer_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)

    if request.method == "POST":
        form = PropertyForm(request.POST)
        if form.is_valid():
            prop = form.save(commit=False)
            prop.customer = customer
            prop.save()
            messages.success(request, f"Property '{prop.address}' added.")
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = PropertyForm()

    return render(request, "customers/property_form.html", {
        "form": form,
        "customer": customer,
        "title": "Add Property",
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def property_edit(request, customer_id, property_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)
    prop = get_object_or_404(Property, id=property_id, customer=customer)

    if request.method == "POST":
        form = PropertyForm(request.POST, instance=prop)
        if form.is_valid():
            form.save()
            messages.success(request, "Property updated.")
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = PropertyForm(instance=prop)

    return render(request, "customers/property_form.html", {
        "form": form,
        "customer": customer,
        "property": prop,
        "title": "Edit Property",
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def contract_add(request, customer_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)

    if request.method == "POST":
        form = ContractForm(request.POST)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.customer = customer
            contract.save()
            messages.success(request, "Contract added.")
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = ContractForm()

    return render(request, "customers/contract_form.html", {
        "form": form,
        "customer": customer,
        "title": "Add Contract",
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def contract_edit(request, customer_id, contract_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)
    contract = get_object_or_404(Contract, id=contract_id, customer=customer)

    if request.method == "POST":
        form = ContractForm(request.POST, instance=contract)
        if form.is_valid():
            form.save()
            messages.success(request, "Contract updated.")
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = ContractForm(instance=contract)

    return render(request, "customers/contract_form.html", {
        "form": form,
        "customer": customer,
        "contract": contract,
        "title": "Edit Contract",
    })


def _send_message_redirect(request, customer_id, fallback_view="customer_detail"):
    """Redirect after send: to 'next' param or customer detail."""
    from django.urls import reverse
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url:
        return redirect(next_url)
    return redirect(fallback_view, customer_id=customer_id)


@require_POST
@role_required("owner")
def customer_send_message(request, customer_id):
    """Send an email or SMS to the client and log it under their profile."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)
    form = SendMessageForm(request.POST)
    if not form.is_valid():
        for _field, errors in form.errors.items():
            for err in errors:
                messages.error(request, err)
        return _send_message_redirect(request, customer_id)

    channel = form.cleaned_data["channel"]
    subject = (form.cleaned_data.get("subject") or "").strip()
    body = form.cleaned_data["body"].strip()
    if not body:
        messages.error(request, "Message body is required.")
        return redirect("customer_detail", customer_id=customer.id)

    to_address = ""
    if channel == "email":
        to_address = customer.email or ""
        if not to_address:
            messages.error(request, "This client has no email address. Add one in Edit Client.")
            return _send_message_redirect(request, customer.id)
        connection = business.get_smtp_connection()
        if not connection:
            messages.error(
                request,
                "Connect your Gmail in Settings to send emails. Go to Settings and add your Gmail address and App Password.",
            )
            return _send_message_redirect(request, customer.id)
        from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
        reply_to = [business.contact_email] if business.contact_email else None
        msg = EmailMultiAlternatives(
            subject or f"Message from {business.name}",
            body,
            from_email,
            [to_address],
            reply_to=reply_to,
            connection=connection,
        )
        try:
            msg.send()
        except Exception as e:
            messages.error(request, f"Failed to send email: {str(e)}")
            return _send_message_redirect(request, customer.id)
        messages.success(request, f"Email sent to {to_address}")
    else:
        # SMS: use primary phone; log only (actual SMS can be added via Twilio later)
        to_address = customer.phone or customer.alt_phone or ""
        if not to_address:
            messages.error(request, "This client has no phone number. Add one in Edit Client.")
            return _send_message_redirect(request, customer.id)
        # TODO: integrate Twilio (or similar) to send real SMS when configured
        messages.success(request, f"Message logged for {to_address}. Configure Twilio in Settings to send real SMS.")

    ClientMessage.objects.create(
        customer=customer,
        channel=channel,
        direction=ClientMessage.DIRECTION_SENT,
        subject=subject,
        body=body,
        to_address=to_address,
        created_by=request.user,
    )
    return _send_message_redirect(request, customer.id)

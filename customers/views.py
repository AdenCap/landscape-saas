import csv

from django.conf import settings
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Sum, Q
from django.utils import timezone

from accounts.decorators import role_required
from accounts.ratelimit import ratelimit
from accounts.utils import get_business as _get_business
from billing.models import Invoice
from jobs.models import Job
from .models import Customer, Property, Contract, ClientMessage
from .forms import (
    CustomerForm,
    CustomerImportForm,
    parse_csv_customers,
    PropertyForm,
    ContractForm,
    SendMessageForm,
)


@role_required("owner", "manager")
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


@role_required("owner", "manager")
def client_messages_list(request):
    """Email log: all emails sent to clients, with search."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to view emails.")
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
    customers_list = list(Customer.objects.filter(business=business).order_by("name"))

    return render(request, "customers/client_messages_list.html", {
        "client_messages": client_messages,
        "messages_search_q": messages_search_q,
        "customers_list": customers_list,
    })


@role_required("owner", "manager")
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

    # Generate portal link if not exists
    if not customer.portal_access_token:
        customer.save()  # This will auto-generate the token
    
    portal_url = request.build_absolute_uri(f"/clients/portal/{customer.portal_access_token}/") if customer.portal_access_token else None

    # SMS configuration check
    sms_configured = bool(
        getattr(settings, "TWILIO_ACCOUNT_SID", "")
        and getattr(settings, "TWILIO_AUTH_TOKEN", "")
        and getattr(settings, "TWILIO_FROM_NUMBER", "")
    )

    # Separate messages by channel for tabs
    email_messages = customer.messages.filter(channel=ClientMessage.CHANNEL_EMAIL)[:50]
    sms_messages = customer.messages.filter(channel=ClientMessage.CHANNEL_SMS)[:50]

    return render(request, "customers/customer_detail.html", {
        "customer": customer,
        "business": business,
        "properties": properties,
        "past_jobs": past_jobs,
        "contracts": contracts,
        "invoices": invoices,
        "total_revenue": total_revenue,
        "client_messages": client_messages,
        "email_messages": email_messages,
        "sms_messages": sms_messages,
        "send_message_form": send_message_form,
        "portal_url": portal_url,
        "sms_configured": sms_configured,
    })


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return value
    return None


@role_required("owner", "manager")
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
            # Auto-create a property from the customer's address
            if customer.address_line1:
                Property.objects.create(
                    customer=customer,
                    address=customer.full_address,
                )
            messages.success(request, f"Client '{customer.name}' added successfully.")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url == "estimate_and_select":
                return redirect(reverse("billing:estimate_create") + "?customer=" + str(customer.id))
            safe_next = _safe_next(request, next_url)
            if safe_next:
                return redirect(safe_next)
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = CustomerForm()

    next_param = request.GET.get("next")
    return render(request, "customers/customer_form.html", {
        "form": form,
        "title": "Add New Client",
        "return_to_estimate": next_param in ("estimate", "estimate_and_select"),
        "next_value": next_param,
    })


@role_required("owner", "manager")
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
            updated = 0
            errors = []
            update_existing = bool(form.cleaned_data.get("update_existing"))
            try:
                duplicate_skipped = 0
                for customer, err in parse_csv_customers(request.FILES["csv_file"], business):
                    if err:
                        errors.append(err)
                        continue

                    existing_qs = Customer.objects.filter(business=business)
                    hit = None
                    duplicate_reason = ""

                    if customer.email:
                        hit = existing_qs.filter(email__iexact=customer.email).first()
                        if hit:
                            duplicate_reason = f"email matches existing client '{hit.name}'"

                    if not hit and customer.phone:
                        hit = existing_qs.filter(phone__iexact=customer.phone).first()
                        if hit:
                            duplicate_reason = f"phone matches existing client '{hit.name}'"

                    if not hit:
                        name = (customer.name or "").strip()
                        addr = (customer.address_line1 or "").strip()
                        if name and addr:
                            hit = existing_qs.filter(name__iexact=name, address_line1__iexact=addr).first()
                            if hit:
                                duplicate_reason = f"name+address matches existing client '{hit.name}'"

                    if hit:
                        if update_existing:
                            # Only overwrite with non-empty incoming values to avoid accidental data loss.
                            for field in [
                                "name", "phone", "alt_phone", "email", "address_line1", "address_line2",
                                "city", "state", "postal_code", "notes",
                            ]:
                                incoming = getattr(customer, field, None)
                                if isinstance(incoming, str):
                                    incoming = incoming.strip()
                                if incoming not in (None, ""):
                                    setattr(hit, field, incoming)
                            hit.save()
                            updated += 1
                            continue
                        duplicate_skipped += 1
                        errors.append(f"Skipped duplicate: {customer.name} ({duplicate_reason})")
                        continue

                    customer.save()
                    # Auto-create a property from the imported address
                    if customer.address_line1:
                        Property.objects.create(
                            customer=customer,
                            address=customer.full_address,
                        )
                    created += 1
            except Exception as e:
                messages.error(request, f"Error reading CSV: {e}")
                return render(request, "customers/customer_import.html", {"form": form, "next_value": request.GET.get("next", "")})

            if created:
                messages.success(request, f"Imported {created} client(s) successfully.")
            if updated:
                messages.success(request, f"Updated {updated} existing client(s).")
            if duplicate_skipped:
                messages.info(request, f"Skipped {duplicate_skipped} duplicate row(s).")
            if errors:
                for err in errors[:10]:
                    messages.warning(request, err)
                if len(errors) > 10:
                    messages.warning(request, f"... and {len(errors) - 10} more row(s) skipped.")
            if not created and not errors:
                messages.warning(request, "No valid rows found. Ensure the first row has headers (e.g. name, email, phone).")
            safe_next = _safe_next(request, (request.POST.get("next") or request.GET.get("next") or "").strip())
            if safe_next:
                return redirect(safe_next)
            return redirect("customer_list")
    else:
        form = CustomerImportForm()

    return render(request, "customers/customer_import.html", {"form": form, "next_value": request.GET.get("next", "")})


@role_required("owner", "manager")
def customer_import_template(request):
    """Download a starter CSV template for client imports."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="clients_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "name", "email", "phone", "alt_phone", "address", "address_line2", "city", "state", "zip", "notes"
    ])
    writer.writerow([
        "Jane Doe", "jane@example.com", "555-123-0001", "", "123 Maple St", "", "Austin", "TX", "78701", "Weekly mowing"
    ])
    writer.writerow([
        "John Smith", "john@example.com", "555-123-0002", "", "44 Oak Ave", "Unit B", "Dallas", "TX", "75201", "Prefers SMS reminders"
    ])
    return response


@role_required("owner", "manager")
def customer_export(request):
    """Export all business customers as CSV."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to export clients.")
        return redirect("/")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="clients_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "name", "email", "phone", "alt_phone", "address_line1", "address_line2",
        "city", "state", "postal_code", "communication_preference", "notes", "created_at"
    ])
    for c in Customer.objects.filter(business=business).order_by("name"):
        writer.writerow([
            c.name,
            c.email,
            c.phone,
            c.alt_phone,
            c.address_line1,
            c.address_line2,
            c.city,
            c.state,
            c.postal_code,
            c.communication_preference,
            c.notes,
            c.created_at.isoformat() if c.created_at else "",
        ])
    return response


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def customer_edit(request, customer_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)
    old_address = customer.full_address

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            new_address = customer.full_address

            # Sync the primary property when the address changes
            if customer.address_line1 and new_address != old_address:
                primary_prop = customer.properties.first()
                if primary_prop:
                    # Update the existing property if its address matched the old one
                    if primary_prop.address == old_address or primary_prop.address == "—":
                        primary_prop.address = new_address
                        primary_prop.save(update_fields=["address"])
                else:
                    # Customer didn't have a property yet — create one
                    Property.objects.create(
                        customer=customer,
                        address=new_address,
                    )

            messages.success(request, f"Client '{customer.name}' updated.")
            return redirect("customer_detail", customer_id=customer.id)
    else:
        form = CustomerForm(instance=customer)

    return render(request, "customers/customer_form.html", {
        "form": form,
        "customer": customer,
        "title": "Edit Client",
    })


@role_required("owner", "manager")
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


@role_required("owner", "manager")
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


@role_required("owner", "manager")
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


@role_required("owner", "manager")
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
@role_required("owner", "manager")
def customer_send_message(request, customer_id):
    """Send an email to the client and log it under their profile."""
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

    subject = (form.cleaned_data.get("subject") or "").strip()
    body = form.cleaned_data["body"].strip()
    if not body:
        messages.error(request, "Message body is required.")
        return redirect("customer_detail", customer_id=customer.id)

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
    from_email = business.get_from_email() or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fieldlgx.com")
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

    ClientMessage.objects.create(
        customer=customer,
        channel="email",
        direction=ClientMessage.DIRECTION_SENT,
        subject=subject,
        body=body,
        to_address=to_address,
        created_by=request.user,
    )
    return _send_message_redirect(request, customer.id)


@require_POST
@role_required("owner", "manager")
def customer_send_sms(request, customer_id):
    """Send an SMS to the client and log it under their profile."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    customer = get_object_or_404(Customer, id=customer_id, business=business)
    body = (request.POST.get("sms_body") or "").strip()
    if not body:
        messages.error(request, "Message body is required.")
        return _send_message_redirect(request, customer_id)

    to_phone = customer.phone
    if not to_phone:
        messages.error(request, "This client has no phone number. Add one in Edit Client.")
        return _send_message_redirect(request, customer_id)

    from messaging.sms import send_sms
    log = send_sms(business, to_phone, body, purpose="notification")
    if log.status == "sent":
        messages.success(request, f"Text sent to {to_phone}")
        ClientMessage.objects.create(
            customer=customer,
            channel=ClientMessage.CHANNEL_SMS,
            direction=ClientMessage.DIRECTION_SENT,
            subject="",
            body=body,
            to_address=to_phone,
            created_by=request.user,
        )
    else:
        error_detail = log.error_message or "Unknown error"
        messages.error(request, f"Failed to send text: {error_detail}")
    return _send_message_redirect(request, customer_id)


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def mass_communications(request):
    """Mass SMS and email to clients, with service-based filtering."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    from pricing.models import ServiceTemplate
    from jobs.models import JobServiceItem, RecurringJob

    services = ServiceTemplate.objects.filter(business=business, active=True).order_by("name")
    customers = Customer.objects.filter(business=business).order_by("name")

    if request.method == "GET":
        # Check if filtering by service
        service_id = request.GET.get("service")
        filtered_customers = customers

        if service_id:
            try:
                service_id = int(service_id)
                # Find customers who have had jobs with this service OR have recurring jobs with it
                job_customer_ids = (
                    JobServiceItem.objects.filter(
                        service_id=service_id,
                        job__property__customer__business=business,
                    )
                    .values_list("job__property__customer_id", flat=True)
                    .distinct()
                )
                recurring_customer_ids = (
                    RecurringJob.objects.filter(
                        property__customer__business=business,
                        active=True,
                        service_snapshot__contains=[{"service_id": service_id}],
                    )
                    .values_list("property__customer_id", flat=True)
                    .distinct()
                )
                # JSONField contains is tricky, fall back to Python filter for recurring
                # but job-based filter is the primary one
                all_ids = set(job_customer_ids)

                # For recurring jobs, check service_snapshot manually since JSONField contains
                # doesn't work well with nested list structures
                for rj in RecurringJob.objects.filter(
                    property__customer__business=business, active=True
                ):
                    for svc in (rj.service_snapshot or []):
                        if svc.get("service_id") == service_id:
                            all_ids.add(rj.property.customer_id)
                            break

                filtered_customers = customers.filter(id__in=all_ids)
            except (ValueError, TypeError):
                pass

        return render(request, "customers/mass_communications.html", {
            "services": services,
            "customers": filtered_customers,
            "all_customers": customers,
            "selected_service": request.GET.get("service", ""),
            "total_count": filtered_customers.count(),
            "sms_configured": bool(business.twilio_account_sid and business.twilio_auth_token and business.twilio_from_number),
            "email_configured": bool(business.email_smtp_user and business.email_smtp_password),
        })

    # POST — send the messages
    channel = request.POST.get("channel", "both")  # sms, email, both
    subject = request.POST.get("subject", "").strip()
    body = request.POST.get("body", "").strip()
    recipient_ids = request.POST.getlist("recipients")

    if not body:
        messages.error(request, "Message body is required.")
        return redirect("mass_communications")

    if not recipient_ids:
        messages.error(request, "Select at least one recipient.")
        return redirect("mass_communications")

    selected_customers = Customer.objects.filter(
        id__in=recipient_ids, business=business
    )

    sms_count = 0
    sms_fail = 0
    email_count = 0
    email_fail = 0

    # Send SMS
    if channel in ("sms", "both"):
        if not (business.twilio_account_sid and business.twilio_auth_token and business.twilio_from_number):
            messages.warning(request, "Twilio SMS is not configured. Go to Settings to add your Twilio credentials.")
        else:
            from messaging.sms import send_sms
            for customer in selected_customers:
                if not customer.phone:
                    continue
                # Respect communication preference
                pref = customer.communication_preference
                if pref and pref not in ("sms", "both", ""):
                    continue
                log = send_sms(business, customer.phone, body, purpose="mass_communication")
                if log.status == "sent":
                    sms_count += 1
                    ClientMessage.objects.create(
                        customer=customer,
                        channel=ClientMessage.CHANNEL_SMS,
                        direction=ClientMessage.DIRECTION_SENT,
                        subject=subject or "Mass Text",
                        body=body,
                        to_address=customer.phone,
                        created_by=request.user,
                    )
                else:
                    sms_fail += 1

    # Send Email
    if channel in ("email", "both"):
        connection = business.get_smtp_connection()
        if not connection:
            messages.warning(request, "Email (Gmail SMTP) is not configured. Go to Settings to add your Gmail credentials.")
        else:
            from_email = business.get_from_email() or settings.DEFAULT_FROM_EMAIL
            reply_to = [business.contact_email] if business.contact_email else None
            for customer in selected_customers:
                if not customer.email:
                    continue
                # Respect communication preference
                pref = customer.communication_preference
                if pref and pref not in ("email", "both", ""):
                    continue
                msg = EmailMultiAlternatives(
                    subject or f"Message from {business.name}",
                    body,
                    from_email,
                    [customer.email],
                    reply_to=reply_to,
                    connection=connection,
                )
                try:
                    msg.send()
                    email_count += 1
                    ClientMessage.objects.create(
                        customer=customer,
                        channel=ClientMessage.CHANNEL_EMAIL,
                        direction=ClientMessage.DIRECTION_SENT,
                        subject=subject or f"Message from {business.name}",
                        body=body,
                        to_address=customer.email,
                        created_by=request.user,
                    )
                except Exception:
                    email_fail += 1

    # Build result message
    parts = []
    if sms_count:
        parts.append(f"{sms_count} text{'s' if sms_count != 1 else ''} sent")
    if email_count:
        parts.append(f"{email_count} email{'s' if email_count != 1 else ''} sent")
    if sms_fail:
        parts.append(f"{sms_fail} text{'s' if sms_fail != 1 else ''} failed")
    if email_fail:
        parts.append(f"{email_fail} email{'s' if email_fail != 1 else ''} failed")

    if parts:
        messages.success(request, " · ".join(parts))
    else:
        messages.warning(request, "No messages were sent. Check that recipients have phone numbers or email addresses.")

    return redirect("mass_communications")


def make_review_action_token(customer_id, action):
    return signing.dumps({"customer_id": customer_id, "action": action}, salt="customers.review")


def _decode_review_action_token(token, expected_action):
    data = signing.loads(token, salt="customers.review", max_age=60 * 60 * 24 * 90)
    if data.get("action") != expected_action:
        raise signing.BadSignature("Invalid review action")
    return data["customer_id"]


@require_http_methods(["GET"])
def review_mark_done(request, token):
    try:
        customer_id = _decode_review_action_token(token, expected_action="done")
    except signing.BadSignature:
        return render(request, "customers/review_action_result.html", {"title": "Invalid link", "message": "This review confirmation link is invalid or expired."}, status=400)

    customer = get_object_or_404(Customer, id=customer_id)
    customer.google_review_status = "reviewed"
    customer.google_review_completed_at = timezone.now()
    customer.save(update_fields=["google_review_status", "google_review_completed_at", "updated_at"])
    return render(request, "customers/review_action_result.html", {"title": "Thanks for your review", "message": "Awesome — we’ve marked this as completed and won’t send more review reminders."})


@require_http_methods(["GET"])
def review_opt_out(request, token):
    try:
        customer_id = _decode_review_action_token(token, expected_action="optout")
    except signing.BadSignature:
        return render(request, "customers/review_action_result.html", {"title": "Invalid link", "message": "This opt-out link is invalid or expired."}, status=400)

    customer = get_object_or_404(Customer, id=customer_id)
    customer.google_review_status = "opted_out"
    customer.save(update_fields=["google_review_status", "updated_at"])
    return render(request, "customers/review_action_result.html", {"title": "You’re unsubscribed", "message": "Got it — you won’t receive any more Google review reminders."})


# Customer Portal Views (public access via token)
@require_http_methods(["GET", "POST"])
def customer_portal(request, token):
    """Customer portal: self-service booking, rescheduling, service history, payments."""
    customer = get_object_or_404(Customer, portal_access_token=token, portal_enabled=True)
    business = customer.business
    
    # Get customer's jobs, invoices, and service history
    jobs = Job.objects.filter(
        property__customer=customer
    ).select_related('property', 'assigned_to', 'assigned_crew').order_by('-scheduled_date')[:50]
    
    invoices = Invoice.objects.filter(
        customer=customer
    ).order_by('-issue_date')[:20]
    
    # Properties for booking
    properties = customer.properties.all()
    
    return render(request, "customers/customer_portal.html", {
        "customer": customer,
        "business": business,
        "jobs": jobs,
        "invoices": invoices,
        "properties": properties,
        "token": token,
    })


@require_http_methods(["GET", "POST"])
def customer_portal_booking(request, token):
    """Online booking form for customers."""
    customer = get_object_or_404(Customer, portal_access_token=token, portal_enabled=True)
    business = customer.business
    
    if request.method == "POST":
        property_id = request.POST.get("property_id")
        service_date = request.POST.get("service_date")
        service_time = request.POST.get("service_time")
        notes = request.POST.get("notes", "").strip()
        
        try:
            property_obj = Property.objects.get(id=property_id, customer=customer)
            
            job = Job.objects.create(
                property=property_obj,
                scheduled_date=service_date,
                scheduled_time=service_time if service_time else None,
                status='scheduled',
                notes=notes,
            )
            messages.success(request, "Service request submitted! We'll confirm your appointment soon.")
            return redirect("customer_portal", token=token)
        except Exception as e:
            messages.error(request, f"Error creating booking: {str(e)}")
    
    properties = customer.properties.all()
    # Get available services
    from pricing.models import ServiceTemplate
    services = ServiceTemplate.objects.filter(business=business, active=True).order_by('name')
    
    return render(request, "customers/customer_portal_booking.html", {
        "customer": customer,
        "business": business,
        "properties": properties,
        "services": services,
    })


@require_http_methods(["POST"])
def customer_portal_reschedule(request, token, job_id):
    """Customer reschedules a job."""
    customer = get_object_or_404(Customer, portal_access_token=token, portal_enabled=True)
    
    try:
        job = Job.objects.get(id=job_id, property__customer=customer)
        
        new_date = request.POST.get("new_date")
        new_time = request.POST.get("new_time")
        
        if new_date:
            job.scheduled_date = new_date
            job.scheduled_time = new_time if new_time else None
            job.save(update_fields=['scheduled_date', 'scheduled_time'])
            messages.success(request, "Job rescheduled successfully.")
        else:
            messages.error(request, "Please select a new date.")
    except Job.DoesNotExist:
        messages.error(request, "Job not found.")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
    
    return redirect("customer_portal", token=token)


@require_http_methods(["POST"])
def customer_portal_cancel(request, token, job_id):
    """Customer cancels a job."""
    customer = get_object_or_404(Customer, portal_access_token=token, portal_enabled=True)

    try:
        job = Job.objects.get(id=job_id, property__customer=customer, status__in=['scheduled', 'in_progress'])
        job.status = 'skipped'
        job.save(update_fields=['status'])
        messages.success(request, "Job cancelled. We'll contact you to reschedule.")
    except Job.DoesNotExist:
        messages.error(request, "Job not found.")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")

    return redirect("customer_portal", token=token)


# ── Public booking (no auth required) ────────────────────────────────

@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@require_http_methods(["GET", "POST"])
def public_booking(request, token):
    """Public booking page — prospects can request a service without an account."""
    from businesses.models import Business
    from pricing.models import ServiceTemplate

    business = get_object_or_404(Business, booking_token=token, booking_enabled=True)
    services = ServiceTemplate.objects.filter(business=business, active=True).order_by("name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        service_id = request.POST.get("service_id")
        service_date = request.POST.get("service_date")
        service_time = request.POST.get("service_time")
        notes = request.POST.get("notes", "").strip()

        if not name or not service_date:
            return render(request, "customers/public_booking.html", {
                "business": business,
                "services": services,
                "error": "Name and preferred date are required.",
            })

        # Find or create customer
        customer = None
        if email:
            customer = Customer.objects.filter(business=business, email__iexact=email).first()
        if not customer and phone:
            customer = Customer.objects.filter(business=business, phone=phone).first()
        if not customer:
            customer = Customer.objects.create(
                business=business,
                name=name,
                email=email,
                phone=phone,
                address_line1=address,
                city=city,
                state=state,
                postal_code=postal_code,
            )

        # Find or create property from address
        property_obj = None
        if address:
            property_obj = Property.objects.filter(customer=customer, address__iexact=address).first()
            if not property_obj:
                property_obj = Property.objects.create(
                    customer=customer,
                    name=address[:50],
                    address=address,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                )
        else:
            property_obj = customer.properties.first()
            if not property_obj:
                property_obj = Property.objects.create(
                    customer=customer,
                    name=f"{name}'s property",
                )

        # Create the job
        job_notes = notes
        if service_id:
            try:
                svc = ServiceTemplate.objects.get(id=service_id, business=business)
                job_notes = f"[{svc.name}] {notes}".strip()
            except ServiceTemplate.DoesNotExist:
                pass

        Job.objects.create(
            property=property_obj,
            scheduled_date=service_date,
            scheduled_time=service_time if service_time else None,
            status="scheduled",
            notes=job_notes,
        )

        return render(request, "customers/public_booking_success.html", {
            "business": business,
        })

    return render(request, "customers/public_booking.html", {
        "business": business,
        "services": services,
    })


@role_required("owner", "manager")
def property_photo_gallery(request, customer_id, property_id):
    """Aggregated photo gallery for a property: site photos + completion photos from all jobs."""
    business = _get_business(request)
    if not business:
        return redirect("dashboard")
    customer = get_object_or_404(Customer, id=customer_id, business=business)
    prop = get_object_or_404(Property, id=property_id, customer=customer)

    from jobs.models import JobPhoto, JobCompletionPhoto
    from itertools import chain

    category_filter = request.GET.get("category", "")

    site_photos = JobPhoto.objects.filter(job__property=prop).select_related("uploaded_by", "job").order_by("-uploaded_at")
    if category_filter:
        site_photos = site_photos.filter(category=category_filter)

    completion_photos = JobCompletionPhoto.objects.filter(job__property=prop).select_related("uploaded_by", "job").order_by("-captured_at")

    # Build unified list
    photos = []
    for p in site_photos:
        photos.append({
            "url": p.image.url,
            "category": p.get_category_display(),
            "category_key": p.category,
            "caption": p.caption,
            "date": p.uploaded_at,
            "job_date": p.job.scheduled_date,
            "job_id": p.job_id,
            "uploaded_by": p.uploaded_by.get_full_name() or p.uploaded_by.username if p.uploaded_by else "Unknown",
            "type": "site",
        })
    if not category_filter:
        for p in completion_photos:
            photos.append({
                "url": p.image.url,
                "category": "Completion",
                "category_key": "completion",
                "caption": "",
                "date": p.captured_at,
                "job_date": p.job.scheduled_date,
                "job_id": p.job_id,
                "uploaded_by": p.uploaded_by.get_full_name() or p.uploaded_by.username if p.uploaded_by else "Unknown",
                "type": "completion",
            })

    photos.sort(key=lambda x: x["date"], reverse=True)

    return render(request, "customers/property_photo_gallery.html", {
        "customer": customer,
        "property": prop,
        "photos": photos,
        "category_filter": category_filter,
    })

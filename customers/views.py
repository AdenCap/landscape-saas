from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Sum, Q
from django.utils import timezone

from accounts.decorators import role_required
from billing.models import Invoice
from jobs.models import Job
from .models import Customer, Property, Contract
from .forms import CustomerForm, CustomerImportForm, parse_csv_customers, PropertyForm, ContractForm


def _get_business(request):
    business = getattr(request.user, 'business', None)
    if not business:
        return None
    return business


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

    # Annotate with property and invoice counts
    customers = customers.annotate(
        property_count=Count('properties'),
        invoice_count=Count('invoices'),
    ).select_related('business').order_by('name')

    return render(request, "customers/customer_list.html", {
        "customers": customers,
        "search": search,
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

    return render(request, "customers/customer_detail.html", {
        "customer": customer,
        "properties": properties,
        "past_jobs": past_jobs,
        "contracts": contracts,
        "invoices": invoices,
        "total_revenue": total_revenue,
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

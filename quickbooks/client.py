"""
QuickBooks Online API client (OAuth 2.0 + REST v3).
Uses requests; tokens stored per-business in QuickBooksConnection.
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

INTUIT_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
INTUIT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
INTUIT_REVOKE_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/revoke"
QB_API_BASE = "https://quickbooks.api.intuit.com/v3/company"
SCOPES = "com.intuit.quickbooks.accounting"


def get_client_credentials():
    """Return (client_id, client_secret) from settings/env."""
    client_id = getattr(settings, "QUICKBOOKS_CLIENT_ID", None) or ""
    client_secret = getattr(settings, "QUICKBOOKS_CLIENT_SECRET", None) or ""
    return client_id.strip(), client_secret.strip()


def get_redirect_uri(request=None):
    """Build OAuth redirect URI for callback."""
    base = getattr(settings, "QUICKBOOKS_REDIRECT_URI", None)
    if base:
        return base.strip()
    if request:
        from django.urls import reverse
        path = reverse("quickbooks:oauth_callback")
        return request.build_absolute_uri(path)
    return "http://localhost:8000/quickbooks/callback/"


def get_authorization_url(request, state=None):
    """Build Intuit OAuth 2.0 authorization URL."""
    client_id, _ = get_client_credentials()
    redirect_uri = get_redirect_uri(request)
    if not state:
        import secrets
        state = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return requests.Request("GET", INTUIT_AUTH_URL, params=params).prepare().url, state


def exchange_code_for_tokens(request, code, realm_id, state=None):
    """
    Exchange authorization code for access_token and refresh_token.
    Returns dict with access_token, refresh_token, expires_in (seconds).
    """
    client_id, client_secret = get_client_credentials()
    redirect_uri = get_redirect_uri(request)
    response = requests.post(
        INTUIT_TOKEN_URL,
        auth=(client_id, client_secret),
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in", 3600),
    }


def refresh_access_token(connection):
    """Refresh the connection's access token; update and save connection."""
    from .models import QuickBooksConnection

    client_id, client_secret = get_client_credentials()
    resp = requests.post(
        INTUIT_TOKEN_URL,
        auth=(client_id, client_secret),
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": connection.refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    connection.access_token = data["access_token"]
    if data.get("refresh_token"):
        connection.refresh_token = data["refresh_token"]
    expires_in = data.get("expires_in", 3600)
    connection.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
    connection.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
    return connection


def get_valid_connection(connection):
    """Return connection with valid access token (refresh if needed)."""
    if not connection:
        return None
    # Refresh if expired or expiring in < 5 min
    if connection.token_expires_at:
        if timezone.now() >= connection.token_expires_at - timedelta(minutes=5):
            try:
                connection = refresh_access_token(connection)
            except Exception as e:
                logger.warning("QuickBooks token refresh failed: %s", e)
                return None
    return connection


def _api_request(connection, method, path, json_data=None, params=None):
    """Perform authenticated request to QuickBooks API v3."""
    connection = get_valid_connection(connection)
    if not connection:
        raise ValueError("QuickBooks connection invalid or expired")
    url = f"{QB_API_BASE}/{connection.realm_id}/{path}"
    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if method == "GET":
        r = requests.get(url, headers=headers, params=params, timeout=30)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=json_data, timeout=30)
    else:
        r = requests.request(method, url, headers=headers, json=json_data, timeout=30)
    if r.status_code >= 400:
        logger.warning("QuickBooks API %s %s: %s", method, path, r.text)
        r.raise_for_status()
    return r.json() if r.content else {}


def find_or_create_customer(connection, customer):
    """
    Find QuickBooks Customer by display name or create one.
    Returns QuickBooks Customer Id (string).
    """
    # Query by DisplayName
    q = f"select * from Customer where DisplayName = '{customer.name.replace(chr(39), chr(39)+chr(39))}'"
    result = _api_request(connection, "GET", "query", params={"query": q})
    query_response = result.get("QueryResponse", {})
    customers = query_response.get("Customer", [])
    if customers:
        return str(customers[0]["Id"])

    # Create customer
    payload = {
        "DisplayName": (customer.name or "Customer")[:500],
        "PrimaryEmailAddr": {"Address": (customer.email or "").strip()[:100]},
        "PrimaryPhone": {"FreeFormNumber": (customer.phone or "").strip()[:21]},
    }
    if getattr(customer, "address_line1", None) or getattr(customer, "city", None):
        payload["BillAddr"] = {
            "Line1": (getattr(customer, "address_line1", None) or "")[:500],
            "City": (getattr(customer, "city", None) or "")[:255],
            "CountrySubDivisionCode": (getattr(customer, "state", None) or "")[:255],
            "PostalCode": (getattr(customer, "postal_code", None) or "")[:30],
        }
    result = _api_request(connection, "POST", "customer", json_data=payload)
    c = result.get("Customer", {})
    return str(c["Id"])


def get_or_create_service_item(connection):
    """Get first Service type Item from QB or create a generic one. Returns Item Id (string)."""
    q = "select * from Item where Type = 'Service' maxresults 1"
    result = _api_request(connection, "GET", "query", params={"query": q})
    items = result.get("QueryResponse", {}).get("Item", [])
    if items:
        return str(items[0]["Id"])
    # Get first income-type account for new item
    acc_q = "select * from Account where AccountType = 'Income' maxresults 1"
    acc_result = _api_request(connection, "GET", "query", params={"query": acc_q})
    accounts = acc_result.get("QueryResponse", {}).get("Account", [])
    income_ref = {"value": str(accounts[0]["Id"])} if accounts else {"value": "1"}
    payload = {
        "Name": "FieldLgx Service",
        "Type": "Service",
        "IncomeAccountRef": income_ref,
    }
    result = _api_request(connection, "POST", "item", json_data=payload)
    return str(result.get("Item", {})["Id"])


def push_invoice_to_quickbooks(connection, invoice):
    """
    Create an Invoice in QuickBooks for the given billing.Invoice.
    - Creates or finds Customer in QB
    - Uses or creates a Service Item for line items
    Returns QuickBooks Invoice Id; saves it on invoice.quickbooks_invoice_id.
    """
    from billing.models import Invoice

    if not isinstance(invoice, Invoice):
        invoice = Invoice.objects.select_related("customer", "business").prefetch_related("line_items").get(pk=invoice)
    if invoice.quickbooks_invoice_id:
        return invoice.quickbooks_invoice_id

    customer = invoice.customer
    qb_customer_id = find_or_create_customer(connection, customer)
    service_item_id = get_or_create_service_item(connection)

    lines = []
    for item in invoice.line_items.all():
        total = float(item.line_total)
        if total <= 0:
            continue
        desc = (item.description or "Service")[:4000]
        qty = float(item.quantity) if item.quantity else 1
        unit_price = float(item.unit_price) if item.unit_price else (total / qty if qty else total)
        lines.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": round(total, 2),
            "Description": desc,
            "SalesItemLineDetail": {
                "Qty": qty,
                "UnitPrice": round(unit_price, 2),
                "ItemRef": {"value": service_item_id},
            },
        })

    if not lines:
        raise ValueError("Invoice has no line items with amount")

    # Subtotal/total
    subtotal = sum(float(item.line_total) for item in invoice.line_items.all())
    total = float(invoice.total) if invoice.total else subtotal

    payload = {
        "CustomerRef": {"value": qb_customer_id},
        "DocNumber": str(invoice.id),
        "TxnDate": invoice.issue_date.isoformat() if invoice.issue_date else datetime.now().date().isoformat(),
        "DueDate": (invoice.due_date or invoice.issue_date or datetime.now().date()).isoformat(),
        "Line": lines,
    }

    result = _api_request(connection, "POST", "invoice", json_data=payload)
    qb_invoice = result.get("Invoice", {})
    qb_id = str(qb_invoice["Id"])
    invoice.quickbooks_invoice_id = qb_id
    invoice.save(update_fields=["quickbooks_invoice_id"])
    return qb_id


def _get_first_account_by_type(connection, account_type):
    """Get first QuickBooks account of given type (e.g. 'Expense', 'Bank'). Returns dict with Id and Name."""
    q = f"select * from Account where AccountType = '{account_type}' and Active = true maxresults 1"
    result = _api_request(connection, "GET", "query", params={"query": q})
    accounts = result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        raise ValueError(f"No {account_type} account found in QuickBooks. Create one in your QB company.")
    return {"value": str(accounts[0]["Id"]), "name": accounts[0].get("Name", "")}


def push_payroll_payment_to_quickbooks(connection, payment):
    """
    Create a Journal Entry in QuickBooks for an EmployeePayment.
    Debit: Payroll expense account. Credit: Bank account.
    Saves quickbooks_journal_entry_id on payment.
    Returns QuickBooks Journal Entry Id.
    """
    from accounts.models import EmployeePayment

    if not isinstance(payment, EmployeePayment):
        payment = EmployeePayment.objects.select_related("employee", "business").get(pk=payment)
    if payment.quickbooks_journal_entry_id:
        return payment.quickbooks_journal_entry_id

    amount = round(float(payment.amount), 2)
    if amount <= 0:
        raise ValueError("Payment amount must be positive")

    expense_account = _get_first_account_by_type(connection, "Expense")
    bank_account = _get_first_account_by_type(connection, "Bank")

    emp_name = (payment.employee.get_full_name() or payment.employee.username or "Employee")[:100]
    desc = f"Payroll: {emp_name} – {payment.paid_date}"
    if payment.notes:
        desc = (desc + " – " + payment.notes)[:4000]

    payload = {
        "JournalEntry": {
            "TxnDate": payment.paid_date.isoformat(),
            "DocNumber": f"Payroll-{payment.id}",
            "Line": [
                {
                    "Description": desc,
                    "Amount": amount,
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "Debit",
                        "AccountRef": expense_account,
                    },
                },
                {
                    "Description": desc,
                    "Amount": amount,
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "Credit",
                        "AccountRef": bank_account,
                    },
                },
            ],
        }
    }

    result = _api_request(connection, "POST", "journalentry", json_data=payload)
    qb_je = result.get("JournalEntry", {})
    qb_id = str(qb_je["Id"])
    payment.quickbooks_journal_entry_id = qb_id
    payment.save(update_fields=["quickbooks_journal_entry_id"])
    return qb_id

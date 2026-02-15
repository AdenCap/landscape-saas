from django.db.models import Q
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from accounts.models import EmployeePayment
from billing.models import Invoice

from .models import QuickBooksConnection
from . import client


@role_required("owner")
@require_GET
def quickbooks_settings(request):
    """Show QuickBooks connection status and connect/disconnect."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    conn = getattr(business, "quickbooks_connection", None)
    client_id, _ = client.get_client_credentials()
    return render(
        request,
        "quickbooks/settings.html",
        {"connection": conn, "quickbooks_configured": bool(client_id)},
    )


@role_required("owner")
@require_GET
def oauth_start(request):
    """Redirect to Intuit OAuth consent screen."""
    business = _get_business(request)
    if not business:
        messages.error(request, "No business.")
        return redirect("/")
    client_id, client_secret = client.get_client_credentials()
    if not client_id or not client_secret:
        messages.error(
            request,
            "QuickBooks is not configured. Set QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET in settings.",
        )
        return redirect("business_settings")
    url, state = client.get_authorization_url(request)
    request.session["quickbooks_oauth_state"] = state
    request.session["quickbooks_oauth_business_id"] = business.id
    return redirect(url)


@role_required("owner")
@require_GET
def oauth_callback(request):
    """Handle Intuit redirect: exchange code for tokens and save connection."""
    business_id = request.session.pop("quickbooks_oauth_business_id", None)
    request.session.pop("quickbooks_oauth_state", None)
    if not business_id or getattr(request.user, "business_id", None) != business_id:
        messages.error(request, "Invalid session.")
        return redirect("business_settings")
    code = request.GET.get("code")
    realm_id = request.GET.get("realmId")
    if not code or not realm_id:
        messages.error(request, "QuickBooks did not return authorization.")
        return redirect("business_settings")
    try:
        tokens = client.exchange_code_for_tokens(request, code, realm_id)
    except Exception as e:
        messages.error(request, f"QuickBooks connection failed: {e}")
        return redirect("business_settings")
    from businesses.models import Business
    business = Business.objects.get(pk=business_id)
    from django.utils import timezone
    from datetime import timedelta
    expires_at = timezone.now() + timedelta(seconds=tokens.get("expires_in", 3600))
    conn, _ = QuickBooksConnection.objects.update_or_create(
        business=business,
        defaults={
            "realm_id": realm_id,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token") or "",
            "token_expires_at": expires_at,
        },
    )
    messages.success(request, "QuickBooks connected successfully.")
    return redirect("quickbooks:settings")


@role_required("owner")
@require_POST
def oauth_disconnect(request):
    """Remove QuickBooks connection for this business."""
    business = _get_business(request)
    if not business:
        return redirect("/")
    QuickBooksConnection.objects.filter(business=business).delete()
    messages.success(request, "QuickBooks disconnected.")
    return redirect("quickbooks:settings")


@role_required("owner")
@require_POST
def push_invoice(request, invoice_id):
    """Push a billing invoice to QuickBooks Online."""
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        business=business,
    )
    conn = getattr(business, "quickbooks_connection", None)
    if not conn:
        return JsonResponse({"error": "Connect QuickBooks in Settings first."}, status=400)
    try:
        qb_id = client.push_invoice_to_quickbooks(conn, invoice)
        return JsonResponse({"ok": True, "quickbooks_invoice_id": qb_id})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@role_required("owner")
@require_POST
def sync_payroll(request):
    """Sync all unsynced employee payments to QuickBooks as journal entries."""
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    conn = getattr(business, "quickbooks_connection", None)
    if not conn:
        return JsonResponse({"error": "Connect QuickBooks in Settings first."}, status=400)

    unsynced = list(
        EmployeePayment.objects.filter(business=business)
        .filter(Q(quickbooks_journal_entry_id__isnull=True) | Q(quickbooks_journal_entry_id=""))
        .select_related("employee")
    )
    synced = 0
    for payment in unsynced:
        try:
            client.push_payroll_payment_to_quickbooks(conn, payment)
            synced += 1
        except Exception as e:
            return JsonResponse({"error": f"Payment #{payment.id}: {e}"}, status=400)
    return JsonResponse({"ok": True, "synced": synced})

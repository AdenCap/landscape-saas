"""Document Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from accounts.decorators import role_required
from accounts.utils import get_business
from .models import Document


@role_required("owner")
def document_list(request):
    """List all documents."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    customer_filter = request.GET.get('customer', '')
    documents = Document.objects.filter(business=business)
    if customer_filter:
        documents = documents.filter(customer_id=customer_filter)
    
    documents = documents.order_by('-created_at')
    
    return render(request, 'documents/document_list.html', {
        'documents': documents,
        'customer_filter': customer_filter,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def document_upload(request):
    """Upload a document."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    if request.method == 'POST' and request.FILES.get('file'):
        document = Document.objects.create(
            business=business,
            title=request.POST.get('title', ''),
            document_type=request.POST.get('document_type', 'other'),
            file=request.FILES['file'],
            description=request.POST.get('description', ''),
            customer_id=request.POST.get('customer') or None,
            is_visible_to_customer=request.POST.get('is_visible_to_customer') == 'on',
            created_by=request.user,
        )
        messages.success(request, f"Document '{document.title}' uploaded.")
        return redirect('documents:document_detail', document_id=document.id)
    
    from customers.models import Customer
    return render(request, 'documents/document_upload.html', {
        'customers': business.customers.all() if business else [],
    })


@role_required("owner")
def document_detail(request, document_id):
    """Document detail."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    document = get_object_or_404(Document, pk=document_id, business=business)
    
    return render(request, 'documents/document_detail.html', {
        'document': document,
    })


@role_required("owner")
@require_http_methods(["POST"])
def document_delete(request, document_id):
    """Delete a document."""
    business = get_business(request)
    if not business:
        return redirect("/")
    
    document = get_object_or_404(Document, pk=document_id, business=business)
    document.delete()
    messages.success(request, "Document deleted.")
    return redirect('documents:document_list')

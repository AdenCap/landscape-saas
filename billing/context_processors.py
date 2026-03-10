"""Context processors for the billing app."""
from django.db.models import Count

from billing.models import Estimate


def estimate_queue_count(request):
    """Inject the count of draft estimates with zero line items (quote queue) into every template."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"estimate_queue_count": 0}
    if getattr(request.user, "role", None) == "crew":
        return {"estimate_queue_count": 0}
    business = getattr(request.user, "business", None)
    if not business:
        return {"estimate_queue_count": 0}
    count = (
        Estimate.objects.filter(business=business, status="draft")
        .annotate(line_count=Count("line_items"))
        .filter(line_count=0)
        .count()
    )
    return {"estimate_queue_count": count}

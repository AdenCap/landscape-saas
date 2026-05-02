def clean_service_label(value=None, service=None, default="Service"):
    """Return the customer-facing label for a service line item."""
    raw = (value or getattr(service, "name", "") or "").strip()
    if not raw:
        return default

    normalized = " ".join(raw.lower().split())
    if normalized == "mowing" or ("mow" in normalized and "field" in normalized):
        return "Mowing"

    return raw

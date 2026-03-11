"""Context processors for the multi-vertical terminology and navigation system."""


# ── Terminology defaults per business type ─────────────────────────────
TERMINOLOGY = {
    "landscaping": {
        "job": "Job",
        "job_plural": "Jobs",
        "crew": "Crew",
        "crew_plural": "Crews",
        "crew_member": "Crew Member",
        "property": "Property",
        "property_plural": "Properties",
        "material": "Material",
        "material_plural": "Materials",
        "estimate": "Estimate",
        "estimate_plural": "Estimates",
        "route": "Route",
        "route_plural": "Routes",
        "completion_photo": "Completion Photo",
    },
    "general": {
        "job": "Job",
        "job_plural": "Jobs",
        "crew": "Team",
        "crew_plural": "Teams",
        "crew_member": "Team Member",
        "property": "Property",
        "property_plural": "Properties",
        "material": "Material",
        "material_plural": "Materials",
        "estimate": "Estimate",
        "estimate_plural": "Estimates",
        "route": "Route",
        "route_plural": "Routes",
        "completion_photo": "Completion Photo",
    },
}

# Fallback for logged-out users or missing business
DEFAULT_TERMS = TERMINOLOGY["general"]


def terminology(request):
    """Inject vertical-specific terminology into every template context.

    Usage in templates: {{ terms.job }}, {{ terms.crew_member }}, etc.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"terms": DEFAULT_TERMS}

    business = getattr(request.user, "business", None)
    if business is None:
        return {"terms": DEFAULT_TERMS}

    business_type = business.business_type or "general"
    terms = dict(TERMINOLOGY.get(business_type, DEFAULT_TERMS))

    # Apply any per-business overrides
    overrides = business.terminology_overrides
    if overrides and isinstance(overrides, dict):
        terms.update(overrides)

    return {"terms": terms}


def navigation(request):
    """Inject module visibility flags for sidebar filtering.

    Usage in templates: {% if show_pricebook %} ... {% endif %}
    """
    flags = {
        "show_fertilization": False,
        "show_pricebook": False,
        "show_equipment": False,
        "show_service_agreements": False,
        "show_inspections": False,
        "show_property_estimator": False,
        "show_checklists": False,
        "show_growing_season": False,
    }

    if not hasattr(request, "user") or not request.user.is_authenticated:
        return flags

    business = getattr(request.user, "business", None)
    if business is None:
        return flags

    modules = business.enabled_modules or []
    flags["show_fertilization"] = "fertilization" in modules
    flags["show_pricebook"] = "pricebook" in modules
    flags["show_equipment"] = "equipment" in modules
    flags["show_service_agreements"] = "service_agreements" in modules
    flags["show_inspections"] = "inspections" in modules
    flags["show_property_estimator"] = "property_estimator" in modules
    flags["show_checklists"] = "checklists" in modules
    flags["show_growing_season"] = "growing_season" in modules

    return flags

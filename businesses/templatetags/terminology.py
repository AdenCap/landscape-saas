"""Template tag for vertical-specific terminology.

Usage:
    {% load terminology %}
    {% term "job" %}          → "Job" (landscaping) or "Service Call" (HVAC)
    {% term "crew_member" %}  → "Crew Member" (landscaping) or "Technician" (HVAC)
"""
from django import template
from businesses.context_processors import DEFAULT_TERMS

register = template.Library()


@register.simple_tag(takes_context=True)
def term(context, key):
    """Return the terminology value for the given key.

    Falls back to DEFAULT_TERMS if no terms are in context.
    """
    terms = context.get("terms", DEFAULT_TERMS)
    return terms.get(key, key)

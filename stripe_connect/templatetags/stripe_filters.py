"""
Custom template filters for Stripe Connect.
"""
from django import template

register = template.Library()


@register.filter
def cents_to_dollars(cents):
    """Convert cents to dollars for display."""
    if cents is None:
        return "0.00"
    try:
        return "{:.2f}".format(float(cents) / 100)
    except (ValueError, TypeError):
        return "0.00"

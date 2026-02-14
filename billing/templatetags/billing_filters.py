"""Template filters for billing display."""
from django import template

register = template.Library()


@register.filter
def currency(value):
    """Format number as currency, trimming unnecessary trailing zeros. $150.00 -> $150, $150.50 -> $150.50"""
    if value is None:
        return "$0"
    try:
        n = float(value)
        s = f"{n:.2f}".rstrip("0").rstrip(".")
        return f"${s}" if s else "$0"
    except (TypeError, ValueError):
        return str(value)

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


@register.filter
def mul(value, arg):
    """Multiply value by arg."""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def div(value, arg):
    """Divide value by arg."""
    try:
        arg_float = float(arg)
        if arg_float == 0:
            return 0
        return float(value) / arg_float
    except (TypeError, ValueError):
        return 0

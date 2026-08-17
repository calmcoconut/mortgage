from decimal import Decimal
from typing import Any

from django import template

register = template.Library()


@register.filter(name="money_fmt")
def money_fmt(value: Any) -> str:
    """Format decimal/float/int as '$1,250', '-$1,250', or '$0'."""
    if value is None or value == "":
        return "$0"
    try:
        val = Decimal(str(value))
    except Exception:
        return str(value)

    if val == Decimal("0"):
        return "$0"
    elif val < Decimal("0"):
        return f"-${abs(val):,.0f}"
    else:
        return f"${val:,.0f}"


@register.filter(name="money_signed")
def money_signed(value: Any) -> str:
    """Format decimal/float/int with explicit sign: '+$1,250', '-$1,250', or '$0'."""
    if value is None or value == "":
        return "$0"
    try:
        val = Decimal(str(value))
    except Exception:
        return str(value)

    if val == Decimal("0"):
        return "$0"
    elif val > Decimal("0"):
        return f"+${val:,.0f}"
    else:
        return f"-${abs(val):,.0f}"


@register.filter(name="money_abs")
def money_abs(value: Any) -> str:
    """Format absolute value as '$1,250'."""
    if value is None or value == "":
        return "$0"
    try:
        val = abs(Decimal(str(value)))
        return f"${val:,.0f}"
    except Exception:
        return str(value)

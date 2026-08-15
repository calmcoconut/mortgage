from decimal import ROUND_HALF_UP, Decimal

MONEY_Q = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Quantize a Decimal value to standard currency cents using ROUND_HALF_UP."""
    if not isinstance(value, Decimal):
        raise TypeError(f"Expected Decimal, got {type(value).__name__}")
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)

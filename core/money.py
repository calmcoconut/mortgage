from decimal import ROUND_HALF_UP, Decimal

MONEY_Q = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Quantize a Decimal value to standard currency cents using ROUND_HALF_UP."""
    if not isinstance(value, Decimal):
        raise TypeError(f"Expected Decimal, got {type(value).__name__}")
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def parse_rate_pct(val: str | Decimal | float | int | None) -> Decimal:
    """Parses a rate value (e.g. '6.875', 6.875, or '0.06875') to a decimal fraction (e.g. Decimal('0.06875')).

    Values greater than 1 are assumed to be percentage representations and divided by 100.
    """
    if val is None or val == "":
        return Decimal("0.0000")
    d = Decimal(str(val)) if not isinstance(val, Decimal) else val
    if d > 1:
        return d / 100
    return d


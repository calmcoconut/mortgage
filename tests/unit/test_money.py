from decimal import Decimal

import pytest

from core.money import MONEY_Q, money


def test_money_quantization_round_half_up():
    assert money(Decimal("123.456")) == Decimal("123.46")
    assert money(Decimal("123.454")) == Decimal("123.45")
    assert money(Decimal("123.455")) == Decimal("123.46")
    assert money(Decimal("0.000")) == Decimal("0.00")
    assert money(Decimal("100")) == Decimal("100.00")


def test_money_constants():
    assert MONEY_Q == Decimal("0.01")


def test_reject_float_conversion():
    # money function expects Decimal
    with pytest.raises(TypeError):
        money(123.45)  # type: ignore


def test_parse_rate_pct():
    from core.money import parse_rate_pct

    # Percentage string conversion
    assert parse_rate_pct("6.875") == Decimal("0.06875")
    assert parse_rate_pct("0.06875") == Decimal("0.06875")
    assert parse_rate_pct(Decimal("6.875")) == Decimal("0.06875")
    assert parse_rate_pct(Decimal("0.06875")) == Decimal("0.06875")
    assert parse_rate_pct(6.875) == Decimal("0.06875")
    assert parse_rate_pct(None) == Decimal("0.0000")
    assert parse_rate_pct("") == Decimal("0.0000")


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

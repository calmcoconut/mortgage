from decimal import Decimal
import pytest
from core.mi_fees import (
    conventional_pmi_monthly,
    fha_mip,
    usda_guarantee_fee,
    va_funding_fee,
)
from core.money import money


def test_conventional_pmi_monthly():
    # <= 80% LTV -> $0 PMI
    assert conventional_pmi_monthly(Decimal("400000"), Decimal("0.80"), "760+") == Decimal("0.00")

    # 95% LTV, 760+ -> ~0.38%/yr = $126.67/mo
    pmi = conventional_pmi_monthly(Decimal("400000"), Decimal("0.95"), "760+")
    assert pmi > Decimal("0")
    assert money(pmi) == Decimal("126.67")


def test_fha_mip():
    # 96.5% LTV, $400k loan -> 1.75% upfront ($7,000) and 0.55% annual ($183.33/mo)
    upfront, monthly = fha_mip(Decimal("400000"), Decimal("0.965"), 360)
    assert money(upfront) == Decimal("7000.00")
    assert money(monthly) == Decimal("183.33")


def test_va_funding_fee():
    # First use, 0% down -> 2.15% = $8,600
    fee_0down = va_funding_fee(Decimal("400000"), Decimal("0.0"), prior_use=False)
    assert money(fee_0down) == Decimal("8600.00")

    # First use, 5% down -> 1.50% = $6,000
    fee_5down = va_funding_fee(Decimal("400000"), Decimal("0.05"), prior_use=False)
    assert money(fee_5down) == Decimal("6000.00")


def test_usda_guarantee_fee():
    # Upfront 1.00% ($4,000), Annual 0.35% ($116.67/mo)
    upfront, monthly = usda_guarantee_fee(Decimal("400000"))
    assert money(upfront) == Decimal("4000.00")
    assert money(monthly) == Decimal("116.67")

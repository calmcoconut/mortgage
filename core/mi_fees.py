from decimal import Decimal

from core.money import money


def conventional_pmi_monthly(
    loan_amount: Decimal,
    ltv: Decimal,
    fico_band: str | None = None,
) -> Decimal:
    """Estimate monthly private mortgage insurance (PMI) for conventional loans.
    Source: Standard MGIC / Radian Rate Card benchmarks (checked Aug 2026).
    """
    if ltv <= Decimal("0.80") or loan_amount <= Decimal("0"):
        return Decimal("0.00")

    # Estimate annual rate based on LTV tiers
    if ltv <= Decimal("0.85"):
        annual_rate = Decimal("0.0020")  # 0.20%
    elif ltv <= Decimal("0.90"):
        annual_rate = Decimal("0.0028")  # 0.28%
    elif ltv <= Decimal("0.95"):
        annual_rate = Decimal("0.0038")  # 0.38%
    else:
        annual_rate = Decimal("0.0055")  # 0.55%

    # Small FICO adjustment
    if fico_band in ["680-719", "660-679"]:
        annual_rate += Decimal("0.0015")
    elif fico_band in ["620-659", "580-619", "<580"]:
        annual_rate += Decimal("0.0030")

    return money((loan_amount * annual_rate) / Decimal("12"))


def fha_mip(
    loan_amount: Decimal,
    ltv: Decimal,
    term_months: int = 360,
) -> tuple[Decimal, Decimal]:
    """Estimate upfront and monthly FHA Mortgage Insurance Premium (MIP).
    Source: HUD Mortgagee Letter guidelines (checked Aug 2026).
    Returns (upfront_mip, monthly_mip).
    """
    upfront = money(loan_amount * Decimal("0.0175"))  # 1.75% upfront
    annual_rate = (
        Decimal("0.0055") if ltv > Decimal("0.95") else Decimal("0.0050")
    )  # 55bps or 50bps
    monthly = money((loan_amount * annual_rate) / Decimal("12"))
    return upfront, monthly


def va_funding_fee(
    loan_amount: Decimal,
    down_pct: Decimal = Decimal("0.0"),
    prior_use: bool = False,
) -> Decimal:
    """Estimate VA Funding Fee based on down payment and prior entitlement use.
    Source: VA Pamphlet 26-7 (checked Aug 2026).
    """
    if down_pct >= Decimal("0.10"):
        fee_rate = Decimal("0.0125")  # 1.25%
    elif down_pct >= Decimal("0.05"):
        fee_rate = Decimal("0.0150")  # 1.50%
    else:
        fee_rate = (
            Decimal("0.0330") if prior_use else Decimal("0.0215")
        )  # 3.30% vs 2.15%

    return money(loan_amount * fee_rate)


def usda_guarantee_fee(loan_amount: Decimal) -> tuple[Decimal, Decimal]:
    """Estimate USDA upfront guarantee fee and annual guarantee fee (monthly).
    Source: USDA Rural Development Handbook (checked Aug 2026).
    Returns (upfront_fee, monthly_fee).
    """
    upfront = money(loan_amount * Decimal("0.0100"))  # 1.00% upfront
    monthly = money((loan_amount * Decimal("0.0035")) / Decimal("12"))  # 0.35% annual
    return upfront, monthly

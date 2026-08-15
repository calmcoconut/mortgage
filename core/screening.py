from decimal import Decimal
from core.models import ScenarioInput, ScreeningResult, ScreeningState


def ltv(scenario: ScenarioInput) -> Decimal:
    """Calculate Loan-to-Value (LTV) ratio."""
    if scenario.property_value <= Decimal("0"):
        return Decimal("0")
    return scenario.loan_amount / scenario.property_value


def back_end_dti(scenario: ScenarioInput, proposed_housing_payment: Decimal) -> Decimal | None:
    """Derive back-end Debt-to-Income (DTI) ratio from gross income, debt, and proposed housing payment."""
    if not scenario.gross_monthly_income or scenario.gross_monthly_income <= Decimal("0"):
        return None
    debts = scenario.recurring_monthly_debts or Decimal("0")
    return (proposed_housing_payment + debts) / scenario.gross_monthly_income


def screen_conventional(scenario: ScenarioInput, proposed_housing_payment: Decimal) -> ScreeningResult:
    """Sanity check conventional screening rules."""
    scenario_ltv = ltv(scenario)
    scenario_dti = back_end_dti(scenario, proposed_housing_payment)

    if scenario_dti is None:
        return ScreeningResult(ScreeningState.MORE_INFO_NEEDED, "INCOME_OR_DEBT_MISSING")
    if scenario_ltv > Decimal("0.97"):
        return ScreeningResult(ScreeningState.UNLIKELY, "LTV_ABOVE_97")
    if scenario.fico_band in ["<580", "580-619"]:
        return ScreeningResult(ScreeningState.UNLIKELY, "CREDIT_BELOW_620")
    if scenario_dti > Decimal("0.50"):
        return ScreeningResult(ScreeningState.NEEDS_AUS, "DTI_ABOVE_TYPICAL_DU_CEILING")
    return ScreeningResult(ScreeningState.LIKELY, "WITHIN_TYPICAL_SCREEN")


def screen_fha(scenario: ScenarioInput, proposed_housing_payment: Decimal) -> ScreeningResult:
    """Sanity check FHA screening rules."""
    scenario_ltv = ltv(scenario)
    scenario_dti = back_end_dti(scenario, proposed_housing_payment)

    if scenario_dti is None:
        return ScreeningResult(ScreeningState.MORE_INFO_NEEDED, "INCOME_OR_DEBT_MISSING")
    if scenario_ltv > Decimal("0.965"):
        return ScreeningResult(ScreeningState.UNLIKELY, "LTV_ABOVE_96_5")
    if scenario.fico_band == "<580":
        return ScreeningResult(ScreeningState.UNLIKELY, "CREDIT_BELOW_580")
    if scenario_dti > Decimal("0.57"):
        return ScreeningResult(ScreeningState.NEEDS_AUS, "DTI_ABOVE_FHA_MANUAL_CAP")
    return ScreeningResult(ScreeningState.LIKELY, "WITHIN_TYPICAL_SCREEN")


def screen_va(scenario: ScenarioInput, proposed_housing_payment: Decimal) -> ScreeningResult:
    """Sanity check VA screening rules."""
    scenario_dti = back_end_dti(scenario, proposed_housing_payment)

    if scenario_dti is None:
        return ScreeningResult(ScreeningState.MORE_INFO_NEEDED, "INCOME_OR_DEBT_MISSING")
    if scenario_dti > Decimal("0.41"):
        return ScreeningResult(ScreeningState.NEEDS_AUS, "DTI_ABOVE_41_BENCHMARK")
    return ScreeningResult(ScreeningState.LIKELY, "WITHIN_TYPICAL_SCREEN")


def screen_usda(scenario: ScenarioInput, proposed_housing_payment: Decimal) -> ScreeningResult:
    """Sanity check USDA screening rules."""
    scenario_dti = back_end_dti(scenario, proposed_housing_payment)

    if scenario_dti is None:
        return ScreeningResult(ScreeningState.MORE_INFO_NEEDED, "INCOME_OR_DEBT_MISSING")
    if scenario_dti > Decimal("0.41"):
        return ScreeningResult(ScreeningState.NEEDS_AUS, "DTI_ABOVE_41_BENCHMARK")
    return ScreeningResult(ScreeningState.LIKELY, "WITHIN_TYPICAL_SCREEN")


def screen_all_programs(
    scenario: ScenarioInput,
    proposed_housing_payment: Decimal,
) -> dict[str, ScreeningResult]:
    """Run screening check for all standard mortgage programs."""
    return {
        "conventional": screen_conventional(scenario, proposed_housing_payment),
        "fha": screen_fha(scenario, proposed_housing_payment),
        "va": screen_va(scenario, proposed_housing_payment),
        "usda": screen_usda(scenario, proposed_housing_payment),
    }

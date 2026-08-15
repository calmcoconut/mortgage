from decimal import Decimal
from typing import Any
from uuid import UUID
from core.financing_cost import compare_options
from core.models import (
    ComparisonResult,
    LoanOptionInput,
    ScenarioInput,
    SourceType,
)
from web.models import LoanOptionModel, ScenarioModel


def scenario_to_input(model: ScenarioModel) -> ScenarioInput:
    """Convert Django ScenarioModel into frozen core ScenarioInput."""
    return ScenarioInput(
        purpose=model.purpose,  # type: ignore
        property_value=model.property_value,
        loan_amount=model.loan_amount,
        down_payment=model.down_payment,
        fico_band=model.fico_band,
        occupancy=model.occupancy,  # type: ignore
        property_type=model.property_type,  # type: ignore
        state=model.state,
        county_fips=model.county_fips,
        program=model.program,  # type: ignore
        term_months=model.term_months,
        expected_horizon_months=model.expected_horizon_months,
        gross_monthly_income=model.gross_monthly_income,
        recurring_monthly_debts=model.recurring_monthly_debts,
        estimated_property_tax_monthly=model.estimated_property_tax_monthly,
        estimated_homeowners_insurance_monthly=model.estimated_homeowners_insurance_monthly,
        estimated_hoa_monthly=model.estimated_hoa_monthly,
    )


def loan_option_to_input(model: LoanOptionModel) -> LoanOptionInput:
    """Convert Django LoanOptionModel into frozen core LoanOptionInput."""
    return LoanOptionInput(
        option_id=model.id,
        label=model.label,
        source_type=SourceType(model.source_type),
        entered_on=model.entered_on,
        loan_amount=model.loan_amount,
        note_rate=model.note_rate,
        apr=model.apr,
        term_months=model.term_months,
        points_pct=model.points_pct,
        lender_credit=model.lender_credit,
        lender_fees=model.lender_fees,
        monthly_mi=model.monthly_mi,
        upfront_mi=model.upfront_mi,
        notes=model.notes,
    )


def compare_scenario(
    scenario_id: UUID | str,
    horizon_months: int | None = None,
    discount_rate: Decimal | None = None,
) -> ComparisonResult:
    """Load scenario and options from DB, convert at the boundary, and run core comparison."""
    scenario_model = ScenarioModel.objects.get(id=scenario_id)
    option_models = list(scenario_model.loan_options.all().order_by("created_at"))

    scenario_input = scenario_to_input(scenario_model)
    option_inputs = [loan_option_to_input(opt) for opt in option_models]

    return compare_options(
        scenario=scenario_input,
        options=option_inputs,
        horizon_months=horizon_months,
        discount_rate=discount_rate,
    )


def build_projected_costs_chart_data(comparison: ComparisonResult) -> dict[str, Any]:
    """Serialize comparison result into server-computed JSON data structures for Chart.js.
    Per Section 7.2 of Design Spec: Chart.js never calculates source-of-truth numbers.
    """
    if not comparison.option_results:
        return {"months": [], "series": []}

    max_term = max(len(opt.amortization) for opt in comparison.option_results)
    months = list(range(0, max_term + 1))

    series = []
    for opt in comparison.option_results:
        # Precomputed cumulative financing cost
        cost_series = [float(round(c, 2)) for c in opt.financing_cost_by_month]
        # Pad if option term was shorter
        if len(cost_series) < len(months):
            cost_series.extend([cost_series[-1]] * (len(months) - cost_series))

        # Precomputed remaining loan balance (month 0 is initial loan amount, then row balances)
        balance_series = [float(round(opt.amortization[0].principal + opt.amortization[0].balance, 2)) if opt.amortization else 0.0]
        for row in opt.amortization:
            balance_series.append(float(round(row.balance, 2)))
        if len(balance_series) < len(months):
            balance_series.extend([0.0] * (len(months) - len(balance_series)))

        # Precomputed payment composition breakdown
        principal_by_month = [0.0] + [float(round(r.principal, 2)) for r in opt.amortization]
        interest_by_month = [0.0] + [float(round(r.interest, 2)) for r in opt.amortization]
        mi_by_month = [0.0] + [float(round(r.mortgage_insurance, 2)) for r in opt.amortization]

        series.append({
            "option_id": str(opt.option_id),
            "label": opt.label,
            "source_type": str(opt.source_type),
            "monthly_pi": float(round(opt.monthly_pi, 2)),
            "financing_cost": cost_series,
            "balance": balance_series,
            "principal": principal_by_month,
            "interest": interest_by_month,
            "mi": mi_by_month,
        })

    return {
        "months": months,
        "series": series,
        "break_even_month": comparison.break_even.break_even_month if comparison.break_even else None,
        "horizon_months": comparison.horizon_months,
    }

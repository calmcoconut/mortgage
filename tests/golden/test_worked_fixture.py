from datetime import date
from decimal import Decimal
from uuid import uuid4

from core.financing_cost import (
    calculate_break_even,
    calculate_option_result,
    compare_options,
)
from core.models import LoanOptionInput, ScenarioInput, SourceType
from core.money import money


def test_worked_fixture_section_11():
    scenario = ScenarioInput(
        purpose="purchase",
        property_value=Decimal("500000"),
        loan_amount=Decimal("400000"),
        down_payment=Decimal("100000"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        county_fips=None,
        program="conventional",
        term_months=360,
        expected_horizon_months=84,  # 7 years
    )

    opt_a_id = uuid4()
    opt_b_id = uuid4()

    option_a = LoanOptionInput(
        option_id=opt_a_id,
        label="Option A: 6.50% / 0 pts",
        source_type=SourceType.MANUAL,
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("400000"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0000"),
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("0.00"),
        monthly_mi=Decimal("0.00"),
        upfront_mi=Decimal("0.00"),
    )

    option_b = LoanOptionInput(
        option_id=opt_b_id,
        label="Option B: 6.00% / 2 pts",
        source_type=SourceType.LOAN_ESTIMATE,
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("400000"),
        note_rate=Decimal("0.0600"),
        apr=Decimal("0.0615"),
        term_months=360,
        points_pct=Decimal("0.0200"),  # 2 points = $8,000
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("0.00"),
        monthly_mi=Decimal("0.00"),
        upfront_mi=Decimal("0.00"),
    )

    result_a_5yr = calculate_option_result(option_a, horizon_months=60)
    result_b_5yr = calculate_option_result(option_b, horizon_months=60)

    result_a_7yr = calculate_option_result(option_a, horizon_months=84)
    result_b_7yr = calculate_option_result(option_b, horizon_months=84)

    result_a_30yr = calculate_option_result(option_a, horizon_months=360)
    result_b_30yr = calculate_option_result(option_b, horizon_months=360)

    # Monthly P&I assertions
    assert money(result_a_7yr.monthly_pi) == Decimal("2528.27")
    assert money(result_b_7yr.monthly_pi) == Decimal("2398.20")

    # Net upfront costs
    assert money(result_a_7yr.net_upfront) == Decimal("0.00")
    assert money(result_b_7yr.net_upfront) == Decimal("8000.00")

    # Financing cost at 5 years (60 months)
    assert money(result_a_5yr.financing_cost_at_horizon) == Decimal("126140.24")
    assert money(result_b_5yr.financing_cost_at_horizon) == Decimal("124109.55")
    diff_5yr = (
        result_a_5yr.financing_cost_at_horizon - result_b_5yr.financing_cost_at_horizon
    )
    assert money(diff_5yr) == Decimal("2030.68")

    # Financing cost at 7 years (84 months)
    assert money(result_a_7yr.financing_cost_at_horizon) == Decimal("174039.84")
    assert money(result_b_7yr.financing_cost_at_horizon) == Decimal("168006.52")
    diff_7yr = (
        result_a_7yr.financing_cost_at_horizon - result_b_7yr.financing_cost_at_horizon
    )
    assert money(diff_7yr) == Decimal("6033.32")

    # Financing cost at 30 years (360 months)
    assert money(result_a_30yr.financing_cost_at_horizon) == Decimal("510177.95")
    assert money(result_b_30yr.financing_cost_at_horizon) == Decimal("471352.76")
    diff_30yr = (
        result_a_30yr.financing_cost_at_horizon
        - result_b_30yr.financing_cost_at_horizon
    )
    assert money(diff_30yr) == Decimal("38825.20")

    # Break-even calculation: Option B is cheaper after month 48
    be = calculate_break_even(candidate=option_b, baseline=option_a, horizon_months=84)
    assert be is not None
    assert be.break_even_month == 48
    assert money(be.savings_at_horizon) == Decimal("6033.32")

    # Full comparison result
    comparison = compare_options(scenario, [option_a, option_b], horizon_months=84)
    assert comparison.recommended_option_id == opt_b_id
    assert comparison.break_even is not None
    assert comparison.break_even.break_even_month == 48

from datetime import date
from decimal import Decimal

import pytest

from core.models import SourceType
from web.models import LoanOptionModel, ScenarioModel
from web.services import (
    build_projected_costs_chart_data,
    compare_scenario,
    loan_option_to_input,
    scenario_to_input,
)


@pytest.mark.django_db
def test_orm_to_core_conversion_and_comparison():
    scenario = ScenarioModel.objects.create(
        name="Worked Fixture",
        purpose="purchase",
        property_value=Decimal("500000.00"),
        loan_amount=Decimal("400000.00"),
        down_payment=Decimal("100000.00"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
        gross_monthly_income=Decimal("12000.00"),
        recurring_monthly_debts=Decimal("800.00"),
    )

    opt_a = LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option A: 6.50% / 0 pts",
        source_type="manual",
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("400000.00"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0000"),
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("0.00"),
    )

    opt_b = LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option B: 6.00% / 2 pts",
        source_type="loan_estimate",
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("400000.00"),
        note_rate=Decimal("0.0600"),
        apr=Decimal("0.0615"),
        term_months=360,
        points_pct=Decimal("0.0200"),
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("0.00"),
    )

    # Test conversion functions
    sc_input = scenario_to_input(scenario)
    assert sc_input.loan_amount == Decimal("400000.00")
    assert sc_input.term_months == 360

    opt_input_a = loan_option_to_input(opt_a)
    assert opt_input_a.source_type == SourceType.MANUAL
    assert opt_input_a.note_rate == Decimal("0.0650")

    # Test comparison service
    comparison = compare_scenario(scenario.id, horizon_months=84)
    assert comparison.recommended_option_id == opt_b.id
    assert comparison.break_even is not None
    assert comparison.break_even.break_even_month == 48

    # Test Chart serialization
    chart_data = build_projected_costs_chart_data(comparison)
    assert "months" in chart_data
    assert len(chart_data["months"]) == 361  # Month 0 to 360
    assert "series" in chart_data
    assert len(chart_data["series"]) == 2
    assert chart_data["series"][0]["label"] == "Option A: 6.50% / 0 pts"
    assert chart_data["series"][0]["financing_cost"][0] == 0.0  # month 0 upfront
    assert "break_even_explanation" in chart_data
    assert "recoup" in chart_data["break_even_explanation"].lower()


def test_format_clean_label():
    from web.services import format_clean_label

    assert format_clean_label("sfcu") == "San Francisco Federal Credit Union"
    assert (
        format_clean_label("Sacramento Credit Union (30-YEAR FIXED)")
        == "Sacramento Credit Union · 30Y Fixed"
    )
    assert (
        format_clean_label("tech cu (7/1 arm conforming)")
        == "Tech CU · 7/1 ARM"
    )
    assert format_clean_label("Option A") == "Option A"


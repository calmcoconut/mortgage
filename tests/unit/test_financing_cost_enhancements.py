import uuid
from datetime import date
from decimal import Decimal

import pytest

from core.financing_cost import calculate_option_result
from core.models import LoanOptionInput, ScenarioInput, SourceType
from web.forms import ScenarioForm
from web.services import export_scenario_to_dict, import_or_update_scenario_from_dict


@pytest.fixture
def base_scenario_input():
    return ScenarioInput(
        purpose="purchase",
        property_value=Decimal("800000.00"),
        loan_amount=Decimal("640000.00"),
        down_payment=Decimal("160000.00"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        county_fips="06085",
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
        estimated_property_tax_monthly=Decimal("800.00"),
        estimated_homeowners_insurance_monthly=Decimal("120.00"),
        estimated_hoa_monthly=Decimal("50.00"),
        annual_appreciation_pct=Decimal("0.0400"),  # 4% annual
        marginal_tax_rate_pct=Decimal("0.2400"),   # 24% bracket
        itemize_deductions=True,
        filing_status="single",
    )


@pytest.fixture
def sample_option():
    return LoanOptionInput(
        option_id=uuid.uuid4(),
        label="30Y Fixed 6.5%",
        source_type="loan_estimate",
        entered_on=date.today(),
        loan_amount=Decimal("640000.00"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0000"),
        lender_fees=Decimal("1000.00"),
        lender_credit=Decimal("0.00"),
    )


def test_total_outflow_and_equity_buildup(base_scenario_input, sample_option):
    res = calculate_option_result(sample_option, 84, scenario=base_scenario_input)

    # Initial outflow: net_upfront ($1,000) + down payment ($160,000) = $161,000
    assert res.total_outflow_by_month[0] == Decimal("161000.00")

    # Initial equity: $800,000 - $640,000 = $160,000
    assert res.home_equity_by_month[0] == Decimal("160000.00")

    # After 84 months (7 years), property value at 4% appreciation > $800,000 and loan balance is amortized down
    assert res.home_equity_at_horizon > Decimal("300000.00")
    assert res.total_outflow_at_horizon > res.financing_cost_at_horizon

    # Total monthly PITI should be monthly P&I + Taxes + Insurance + HOA
    escrow = Decimal("800.00") + Decimal("120.00") + Decimal("50.00")
    assert res.total_piti_monthly == res.monthly_pi + escrow


def test_after_tax_deduction_shield(base_scenario_input, sample_option):
    res_itemized = calculate_option_result(sample_option, 84, scenario=base_scenario_input)

    # After-tax financing cost should be lower than pure pre-tax financing cost due to interest deduction
    assert res_itemized.after_tax_cost_at_horizon < res_itemized.financing_cost_at_horizon

    # When itemize_deductions is False, after_tax_cost equals financing_cost
    scenario_no_item = ScenarioInput(
        purpose="purchase",
        property_value=Decimal("800000.00"),
        loan_amount=Decimal("640000.00"),
        down_payment=Decimal("160000.00"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        county_fips="06085",
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
        annual_appreciation_pct=Decimal("0.0300"),
        marginal_tax_rate_pct=Decimal("0.2400"),
        itemize_deductions=False,
    )
    res_no_item = calculate_option_result(sample_option, 84, scenario=scenario_no_item)
    assert res_no_item.after_tax_cost_at_horizon == res_no_item.financing_cost_at_horizon


@pytest.mark.django_db
def test_scenario_form_appreciation_and_tax_handling():
    data = {
        "name": "Appreciation Test Scenario",
        "purpose": "purchase",
        "property_value": "$800,000",
        "loan_amount": "$640,000",
        "down_payment": "$160,000",
        "fico_band": "760+",
        "occupancy": "primary",
        "property_type": "single_family",
        "state": "CA",
        "program": "conventional",
        "term_months": 360,
        "expected_horizon_months": 84,
        "annual_appreciation_pct": "3.5",
        "marginal_tax_rate_pct": "28.0",
        "itemize_deductions": True,
        "filing_status": "single",
    }
    form = ScenarioForm(data=data)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.annual_appreciation_pct == Decimal("0.0350")
    assert instance.marginal_tax_rate_pct == Decimal("0.2800")
    assert instance.itemize_deductions is True

    # Test editing existing scenario instance
    edit_form_get = ScenarioForm(instance=instance)
    assert edit_form_get.initial["annual_appreciation_pct"] == Decimal("3.50")
    assert edit_form_get.initial["marginal_tax_rate_pct"] == Decimal("28.00")

    # Test re-submitting with decimal percentage string or float decimal
    edit_data = {
        "name": "Appreciation Test Scenario Updated",
        "purpose": "purchase",
        "property_value": "$850,000",
        "loan_amount": "$680,000",
        "down_payment": "$170,000",
        "fico_band": "760+",
        "occupancy": "primary",
        "property_type": "single_family",
        "state": "CA",
        "program": "conventional",
        "term_months": 360,
        "expected_horizon_months": 84,
        "annual_appreciation_pct": "0.0350",  # 4 decimal places should also be cleanly parsed
        "marginal_tax_rate_pct": "0.2800",
        "itemize_deductions": False,
        "filing_status": "single",
    }
    edit_form_post = ScenarioForm(data=edit_data, instance=instance)
    assert edit_form_post.is_valid(), edit_form_post.errors
    updated_instance = edit_form_post.save()
    assert updated_instance.annual_appreciation_pct == Decimal("0.0350")
    assert updated_instance.marginal_tax_rate_pct == Decimal("0.2800")



@pytest.mark.django_db
def test_json_import_export_with_appreciation_and_tax():
    payload = {
        "scenario": {
            "name": "JSON Appreciation Test",
            "property_value": 900000,
            "loan_amount": 720000,
            "annual_appreciation_pct": "4.2%",
            "marginal_tax_rate_pct": "33.3%",
            "itemize_deductions": True,
            "filing_status": "married_joint",
        }
    }
    scenario = import_or_update_scenario_from_dict(payload)
    assert scenario.annual_appreciation_pct == Decimal("0.0420")
    assert scenario.marginal_tax_rate_pct == Decimal("0.3330")
    assert scenario.itemize_deductions is True
    assert scenario.filing_status == "married_joint"

    exported = export_scenario_to_dict(scenario)
    assert exported["scenario"]["annual_appreciation_pct"] == 4.2
    assert exported["scenario"]["marginal_tax_rate_pct"] == 33.3
    assert exported["scenario"]["itemize_deductions"] is True
    assert exported["scenario"]["filing_status"] == "married_joint"


def test_calculate_break_even_immediate_day_1():
    from core.financing_cost import calculate_break_even

    # Candidate has $0 points and lower rate vs Baseline with $2000 points and higher rate
    candidate = LoanOptionInput(
        option_id=uuid.uuid4(),
        label="Candidate Lower Upfront & Lower Rate",
        source_type=SourceType.MANUAL,
        entered_on=date(2026, 8, 1),
        loan_amount=Decimal("500000.00"),
        note_rate=Decimal("0.0600"),
        apr=Decimal("0.0600"),
        term_months=360,
        points_pct=Decimal("0.0000"),
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("500.00"),
    )
    baseline = LoanOptionInput(
        option_id=uuid.uuid4(),
        label="Baseline Higher Upfront & Higher Rate",
        source_type=SourceType.MANUAL,
        entered_on=date(2026, 8, 1),
        loan_amount=Decimal("500000.00"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0660"),
        term_months=360,
        points_pct=Decimal("0.0100"),
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("1500.00"),
    )

    res = calculate_break_even(candidate=candidate, baseline=baseline, horizon_months=84)
    assert res.break_even_month == 0
    assert "No upfront cost to recoup" in res.break_even_explanation
    assert res.upfront_delta < 0
    assert res.savings_at_horizon > 0


def test_mortgage_tags_filters():
    from web.templatetags.mortgage_tags import money_abs, money_fmt, money_signed

    # money_fmt
    assert money_fmt(1250) == "$1,250"
    assert money_fmt(-1250) == "-$1,250"
    assert money_fmt(0) == "$0"
    assert money_fmt(Decimal("-26000")) == "-$26,000"

    # money_signed
    assert money_signed(1250) == "+$1,250"
    assert money_signed(-1250) == "-$1,250"
    assert money_signed(0) == "$0"
    assert money_signed(Decimal("519")) == "+$519"

    # money_abs
    assert money_abs(-1250) == "$1,250"
    assert money_abs(1250) == "$1,250"
    assert money_abs(0) == "$0"


from decimal import Decimal

from core.models import ScenarioInput, ScreeningState
from core.screening import (
    back_end_dti,
    ltv,
    screen_all_programs,
    screen_conventional,
)


def test_ltv_and_dti_derivation():
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
        expected_horizon_months=84,
        gross_monthly_income=Decimal("10000"),
        recurring_monthly_debts=Decimal("500"),
    )
    assert ltv(scenario) == Decimal("0.80")
    assert back_end_dti(scenario, Decimal("2500")) == Decimal(
        "0.30"
    )  # (2500 + 500) / 10000


def test_screening_missing_income_returns_more_info():
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
        expected_horizon_months=84,
        gross_monthly_income=None,
        recurring_monthly_debts=Decimal("500"),
    )
    res = screen_conventional(scenario, Decimal("2500"))
    assert res.state == ScreeningState.MORE_INFO_NEEDED
    assert res.reason_code == "INCOME_OR_DEBT_MISSING"


def test_conventional_ltv_above_97_unlikely():
    scenario = ScenarioInput(
        purpose="purchase",
        property_value=Decimal("500000"),
        loan_amount=Decimal("490000"),  # 98% LTV
        down_payment=Decimal("10000"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        county_fips=None,
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
        gross_monthly_income=Decimal("10000"),
        recurring_monthly_debts=Decimal("500"),
    )
    res = screen_conventional(scenario, Decimal("2500"))
    assert res.state == ScreeningState.UNLIKELY
    assert res.reason_code == "LTV_ABOVE_97"


def test_conventional_high_dti_needs_aus():
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
        expected_horizon_months=84,
        gross_monthly_income=Decimal("6000"),
        recurring_monthly_debts=Decimal("1000"),
    )
    # payment $2500 + debt $1000 = $3500 / 6000 = 58.33% DTI > 50%
    res = screen_conventional(scenario, Decimal("2500"))
    assert res.state == ScreeningState.NEEDS_AUS
    assert res.reason_code == "DTI_ABOVE_TYPICAL_DU_CEILING"


def test_screen_all_programs():
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
        expected_horizon_months=84,
        gross_monthly_income=Decimal("10000"),
        recurring_monthly_debts=Decimal("500"),
    )
    results = screen_all_programs(scenario, Decimal("2500"))
    assert "conventional" in results
    assert "fha" in results
    assert "va" in results
    assert "usda" in results
    assert results["conventional"].state == ScreeningState.LIKELY

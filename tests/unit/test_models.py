from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from web.models import BenchmarkPointModel, LoanOptionModel, ScenarioModel


@pytest.mark.django_db
def test_create_scenario_and_loan_option():
    scenario = ScenarioModel.objects.create(
        name="Mountain View Purchase",
        purpose="purchase",
        property_value=Decimal("850000.00"),
        loan_amount=Decimal("680000.00"),
        down_payment=Decimal("170000.00"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        county_fips="06085",
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
        gross_monthly_income=Decimal("15000.00"),
        recurring_monthly_debts=Decimal("1000.00"),
        estimated_property_tax_monthly=Decimal("850.00"),
        estimated_homeowners_insurance_monthly=Decimal("140.00"),
        estimated_hoa_monthly=Decimal("0.00"),
    )
    assert scenario.id is not None
    assert scenario.property_value == Decimal("850000.00")

    opt1 = LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option A: 6.50% / 0 pts",
        source_type="manual",
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("680000.00"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0000"),
        lender_credit=Decimal("0.00"),
        lender_fees=Decimal("0.00"),
        monthly_mi=Decimal("0.00"),
        upfront_mi=Decimal("0.00"),
    )
    assert opt1.id is not None
    assert opt1.scenario == scenario
    assert opt1.note_rate == Decimal("0.0650")


@pytest.mark.django_db
def test_create_benchmark_point():
    point = BenchmarkPointModel.objects.create(
        series="MORTGAGE30US",
        observed_on=date(2026, 8, 14),
        value=Decimal("6.52"),
        fetched_at=timezone.now(),
    )
    assert point.id is not None
    assert point.series == "MORTGAGE30US"

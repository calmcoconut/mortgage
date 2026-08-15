from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from web.models import LoanOptionModel, ScenarioModel


@pytest.fixture
def sample_scenario():
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
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
        gross_monthly_income=Decimal("15000.00"),
        recurring_monthly_debts=Decimal("1000.00"),
        estimated_property_tax_monthly=Decimal("850.00"),
        estimated_homeowners_insurance_monthly=Decimal("140.00"),
        estimated_hoa_monthly=Decimal("0.00"),
    )
    LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option A",
        source_type="manual",
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("680000.00"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0000"),
    )
    LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option B",
        source_type="loan_estimate",
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("680000.00"),
        note_rate=Decimal("0.0600"),
        apr=Decimal("0.0615"),
        term_months=360,
        points_pct=Decimal("0.0200"),
    )
    return scenario


@pytest.mark.django_db
def test_scenario_list_view(client, sample_scenario):
    url = reverse("web:scenario_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "Mountain View Purchase" in resp.content.decode()


@pytest.mark.django_db
def test_scenario_compare_view(client, sample_scenario):
    url = reverse("web:scenario_compare", kwargs={"scenario_id": sample_scenario.id})
    resp = client.get(url, {"horizon": "84"})
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Compare financing paths" in content
    assert "Option A" in content
    assert "Option B" in content


@pytest.mark.django_db
def test_scenario_projected_costs_view(client, sample_scenario):
    url = reverse(
        "web:scenario_projected_costs", kwargs={"scenario_id": sample_scenario.id}
    )
    resp = client.get(url, {"horizon": "84"})
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Projected financing costs" in content
    assert "chart_data_json" in resp.context


@pytest.mark.django_db
def test_scenario_screening_preview_htmx(client):
    url = reverse("web:scenario_screen_preview")
    resp = client.post(
        url,
        {
            "property_value": "500000",
            "loan_amount": "400000",
            "gross_monthly_income": "10000",
            "recurring_monthly_debts": "500",
            "fico_band": "760+",
            "program": "conventional",
        },
    )
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "conventional" in content.lower()
    assert "LIKELY" in content

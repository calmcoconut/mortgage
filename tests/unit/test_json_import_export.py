import json
from decimal import Decimal

import pytest
from django.urls import reverse

from web.models import LoanOptionModel, ScenarioModel
from web.services import export_scenario_to_dict, import_or_update_scenario_from_dict


@pytest.fixture
def sample_scenario_with_options(db):
    scenario = ScenarioModel.objects.create(
        name="Silicon Valley Starter",
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
        gross_monthly_income=Decimal("16000.00"),
        recurring_monthly_debts=Decimal("1200.00"),
        estimated_property_tax_monthly=Decimal("800.00"),
        estimated_homeowners_insurance_monthly=Decimal("120.00"),
        estimated_hoa_monthly=Decimal("50.00"),
    )
    LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option A (30Y Fixed)",
        source_type="manual",
        loan_amount=Decimal("640000.00"),
        note_rate=Decimal("0.0650"),
        apr=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0000"),
        lender_fees=Decimal("1200.00"),
        lender_credit=Decimal("0.00"),
    )
    LoanOptionModel.objects.create(
        scenario=scenario,
        label="Option B (30Y Fixed 2pts)",
        source_type="loan_estimate",
        loan_amount=Decimal("640000.00"),
        note_rate=Decimal("0.0600"),
        apr=Decimal("0.0615"),
        term_months=360,
        points_pct=Decimal("0.0200"),
        lender_fees=Decimal("800.00"),
        lender_credit=Decimal("0.00"),
    )
    return scenario


@pytest.mark.django_db
def test_export_scenario_to_dict(sample_scenario_with_options):
    data = export_scenario_to_dict(sample_scenario_with_options)

    assert "scenario" in data
    assert data["scenario"]["name"] == "Silicon Valley Starter"
    assert data["scenario"]["loan_amount"] == 640000.0
    assert data["scenario"]["property_value"] == 800000.0
    assert "loan_options" in data
    assert len(data["loan_options"]) == 2
    assert data["loan_options"][0]["label"] == "Option A (30Y Fixed)"
    assert data["loan_options"][1]["note_rate"] == 0.06


@pytest.mark.django_db
def test_import_new_scenario_from_dict():
    payload = {
        "scenario": {
            "name": "Oakland Condo Purchase",
            "purpose": "purchase",
            "property_value": "$650,000",
            "loan_amount": "$520,000",
            "down_payment": "$130,000",
            "fico_band": "740-759",
            "occupancy": "primary",
            "property_type": "condo",
            "state": "CA",
            "program": "conventional",
            "term_months": 360,
            "expected_horizon_months": 84,
            "gross_monthly_income": "$14,000",
            "recurring_monthly_debts": "$900",
        },
        "loan_options": [
            {
                "label": "Star One 30Y Fixed",
                "source_type": "loan_estimate",
                "loan_amount": "$520,000",
                "note_rate": "6.25%",
                "apr": "6.28%",
                "term_months": 360,
                "points_pct": "0.0",
                "lender_fees": "$500",
            }
        ],
    }

    scenario = import_or_update_scenario_from_dict(payload)
    assert scenario.pk is not None
    assert scenario.name == "Oakland Condo Purchase"
    assert scenario.loan_amount == Decimal("520000.00")
    assert scenario.property_value == Decimal("650000.00")

    options = list(scenario.loan_options.all())
    assert len(options) == 1
    assert options[0].label == "Star One 30Y Fixed"
    assert options[0].note_rate == Decimal("0.0625")
    assert options[0].loan_amount == Decimal("520000.00")


@pytest.mark.django_db
def test_update_existing_scenario_from_dict(sample_scenario_with_options):
    scenario = sample_scenario_with_options
    opt_a = scenario.loan_options.all()[0]

    payload = {
        "scenario": {
            "name": "Silicon Valley Starter (Updated)",
            "property_value": 850000,
            "loan_amount": 680000,
            "down_payment": 170000,
        },
        "loan_options": [
            {
                "id": str(opt_a.id),
                "label": "Option A (Updated Rate)",
                "note_rate": 0.0625,
                "loan_amount": 680000,
            },
            {
                "label": "Brand New Option C",
                "source_type": "rate_api",
                "loan_amount": 680000,
                "note_rate": 0.05875,
                "term_months": 360,
            },
        ],
    }

    updated = import_or_update_scenario_from_dict(payload, scenario=scenario)
    assert updated.id == scenario.id
    assert updated.name == "Silicon Valley Starter (Updated)"
    assert updated.property_value == Decimal("850000.00")
    assert updated.loan_amount == Decimal("680000.00")

    opt_a.refresh_from_db()
    assert opt_a.label == "Option A (Updated Rate)"
    assert opt_a.note_rate == Decimal("0.0625")
    assert opt_a.loan_amount == Decimal("680000.00")

    options = list(scenario.loan_options.all())
    assert any(o.label == "Brand New Option C" for o in options)


@pytest.mark.django_db
def test_scenario_import_json_view(client):
    url = reverse("web:scenario_import_json")
    payload = {
        "scenario": {
            "name": "HTTP Imported Scenario",
            "loan_amount": 500000,
            "property_value": 625000,
        }
    }
    resp = client.post(url, {"json_payload": json.dumps(payload)})
    assert resp.status_code == 302
    created = ScenarioModel.objects.get(name="HTTP Imported Scenario")
    assert created.loan_amount == Decimal("500000.00")


@pytest.mark.django_db
def test_scenario_export_json_view(client, sample_scenario_with_options):
    url = reverse(
        "web:scenario_export_json",
        kwargs={"scenario_id": sample_scenario_with_options.id},
    )
    resp = client.get(url, {"download": "1"})
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/json"
    assert "attachment" in resp["Content-Disposition"]
    data = json.loads(resp.content)
    assert data["scenario"]["name"] == "Silicon Valley Starter"


@pytest.mark.django_db
def test_scenario_edit_json_view(client, sample_scenario_with_options):
    scenario = sample_scenario_with_options
    url = reverse("web:scenario_edit_json", kwargs={"scenario_id": scenario.id})
    resp = client.get(url)
    assert resp.status_code == 200

    payload = {
        "scenario": {
            "name": "Edited Via JSON View",
            "loan_amount": 600000,
        }
    }
    resp = client.post(url, {"json_payload": json.dumps(payload)})
    assert resp.status_code == 302
    scenario.refresh_from_db()
    assert scenario.name == "Edited Via JSON View"
    assert scenario.loan_amount == Decimal("600000.00")



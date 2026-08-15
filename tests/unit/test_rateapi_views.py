from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from web.integrations.rateapi import RateApiAdapter
from web.models import LoanOptionModel, ScenarioModel


@pytest.fixture
def test_scenario(db):
    return ScenarioModel.objects.create(
        name="Test RateAPI Scenario",
        purpose="purchase",
        property_value=Decimal("625000.00"),
        loan_amount=Decimal("500000.00"),
        down_payment=Decimal("125000.00"),
        fico_band="760+",
        occupancy="primary",
        property_type="single_family",
        state="CA",
        program="conventional",
        term_months=360,
        expected_horizon_months=84,
    )


@pytest.mark.django_db
def test_scenario_enrich_preview_view(client, test_scenario):
    mock_result = {
        "from_cache": False,
        "offers": [
            {
                "rank": 1,
                "credit_union_name": "Bay Area Credit Union",
                "rate": 5.95,
                "apr": 6.02,
                "points": 0.0,
                "monthly_payment": 2981.25,
                "confidence_score": 0.95,
                "confidence_category": "high",
                "eligibility": {
                    "status": "likely_eligible",
                    "requirements_summary": "Community charter in CA",
                },
            }
        ],
        "budget": {
            "month_key": "2026-08",
            "call_count": 3,
            "monthly_limit": 20,
            "safety_threshold": 18,
            "can_call": True,
        },
    }

    with patch.object(
        RateApiAdapter, "fetch_decisions", return_value=mock_result
    ):
        url = reverse("web:scenario_enrich_preview", kwargs={"scenario_id": test_scenario.id})
        response = client.get(url)

        assert response.status_code == 200
        assert "Bay Area Credit Union" in response.content.decode()
        assert "5.95" in response.content.decode()
        assert "Budget: 3 / 18" in response.content.decode()


@pytest.mark.django_db
def test_scenario_import_rateapi_offer_post(client, test_scenario):
    url = reverse("web:scenario_import_rateapi_offer", kwargs={"scenario_id": test_scenario.id})
    post_data = {
        "label": "Safe 1 Credit Union - 30-Year Fixed",
        "institution_name": "Safe 1 Credit Union",
        "note_rate": "0.060000",
        "apr": "0.060000",
        "points_pct": "0.000000",
        "loan_amount": "500000.00",
        "term_months": "360",
        "confidence_score": "0.950",
    }

    response = client.post(url, data=post_data)
    assert response.status_code == 302
    assert response.url == reverse("web:scenario_compare", kwargs={"scenario_id": test_scenario.id})

    option = LoanOptionModel.objects.get(scenario=test_scenario, label="Safe 1 Credit Union - 30-Year Fixed")
    assert option.source_type == "rate_api"
    assert option.institution_name == "Safe 1 Credit Union"
    assert option.note_rate == Decimal("0.060000")
    assert option.confidence_score == Decimal("0.950")


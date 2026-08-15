from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from web.integrations.rateapi import (
    BudgetExhaustedError,
    RateApiAdapter,
    get_amount_bucket,
)
from web.models import RateApiBudgetModel, RateApiCacheModel


def test_get_amount_bucket():
    assert get_amount_bucket(Decimal("487500")) == 500000
    assert get_amount_bucket(Decimal("512000")) == 500000
    assert get_amount_bucket(Decimal("513000")) == 525000
    assert get_amount_bucket(Decimal("400000")) == 400000
    assert get_amount_bucket(Decimal("0")) == 0


def test_build_payload_purchase():
    adapter = RateApiAdapter(api_key="test_key")
    payload = adapter.build_payload(
        state="CA",
        amount=Decimal("500000"),
        term_months=360,
        intent="purchase",
        county="Santa Clara",
        zip_code="94040",
    )
    assert payload == {
        "decision_type": "financing",
        "context": {
            "geo": {
                "state": "CA",
                "county": "Santa Clara",
                "zip": "94040",
            }
        },
        "product_request": {
            "product_type": "mortgage",
            "intent": "purchase",
            "amount": 500000,
            "term_months": 360,
        },
    }


def test_build_payload_refinance():
    adapter = RateApiAdapter(api_key="test_key")
    payload = adapter.build_payload(
        state="TX",
        amount=Decimal("350000"),
        term_months=180,
        intent="refinance",
        current_apr=Decimal("0.06875"),
    )
    assert payload["product_request"]["intent"] == "refinance"
    assert payload["product_request"]["current_offer"] == {"apr": 6.875}


@pytest.mark.django_db
def test_cache_hit_avoids_api_call():
    adapter = RateApiAdapter(api_key="test_key")
    now = timezone.now()

    RateApiCacheModel.objects.create(
        cache_key="CA_purchase_500000_360",
        query_state="CA",
        query_intent="purchase",
        query_amount_bucket=500000,
        query_term_months=360,
        response_payload={
            "actions": [
                {
                    "offers": [
                        {
                            "rank": 1,
                            "credit_union_name": "Cached CU",
                            "rate": 5.875,
                            "apr": 5.95,
                            "points": 0,
                            "monthly_payment": 2950.0,
                        }
                    ]
                }
            ]
        },
        cached_at=now,
        expires_at=now + timedelta(hours=24),
    )

    with patch("requests.post") as mock_post:
        result = adapter.fetch_decisions(
            state="CA",
            amount=Decimal("495000"),  # Buckets to 500000
            term_months=360,
            intent="purchase",
        )
        assert not mock_post.called
        assert result["from_cache"] is True
        assert result["offers"][0]["credit_union_name"] == "Cached CU"


@pytest.mark.django_db
def test_budget_guard_blocks_call_at_threshold():
    adapter = RateApiAdapter(api_key="test_key", safety_threshold=18)
    month_key = timezone.now().strftime("%Y-%m")

    # Set budget to 18 (safety threshold reached)
    RateApiBudgetModel.objects.create(
        month_key=month_key,
        call_count=18,
        monthly_limit=20,
        safety_threshold=18,
    )

    with patch("requests.post") as mock_post:
        with pytest.raises(BudgetExhaustedError):
            adapter.fetch_decisions(
                state="WA",
                amount=Decimal("600000"),
                term_months=360,
                intent="purchase",
            )
        assert not mock_post.called


@pytest.mark.django_db
def test_anomaly_filtering():
    adapter = RateApiAdapter(api_key="test_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "actions": [
            {
                "score": 0.9,
                "offers": [
                    {
                        "rank": 1,
                        "credit_union_name": "High Confidence CU",
                        "rate": 6.0,
                        "apr": 6.0,
                        "points": 0,
                        "eligibility": {"confidence": 0.95, "status": "likely_eligible"},
                    },
                    {
                        "rank": 2,
                        "credit_union_name": "Low Confidence CU",
                        "rate": 5.5,
                        "apr": 5.5,
                        "points": 0,
                        "eligibility": {"confidence": 0.60, "status": "unknown"},
                    },
                    {
                        "rank": 3,
                        "credit_union_name": "Quarantined CU",
                        "rate": 4.0,
                        "apr": 4.0,
                        "points": 0,
                        "eligibility": {"confidence": 0.30, "status": "unknown"},
                    },
                ],
            }
        ]
    }

    with patch("requests.post", return_value=mock_resp):
        res = adapter.fetch_decisions(
            state="NV",
            amount=Decimal("400000"),
            term_months=360,
            intent="purchase",
        )

    # 3rd offer (<0.5 confidence) should be filtered out
    offers = res["offers"]
    assert len(offers) == 2
    assert offers[0]["credit_union_name"] == "High Confidence CU"
    assert offers[0]["confidence_category"] == "high"
    assert offers[1]["credit_union_name"] == "Low Confidence CU"
    assert offers[1]["confidence_category"] == "warning"

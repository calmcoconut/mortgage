from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from web.integrations.rateapi import (
    RateApiAdapter,
    aggregate_product_term_structure,
    calculate_fred_vs_cu_spread,
)
from web.models import BenchmarkPointModel, RateApiSnapshotModel


@pytest.mark.django_db
def test_rateapi_snapshot_persistence_and_idempotency():
    adapter = RateApiAdapter(api_key="test_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "rates": [
            {
                "lender": "Coast Central Credit Union",
                "state": "CA",
                "product_type": "5-1-arm",
                "product_name": "5/1 ARM Conforming",
                "rate": 5.375,
                "apr": 5.480,
                "points": 0.0,
                "as_of": "2026-08-14T08:00:00.000Z",
                "eligibility": {
                    "status": "likely_eligible",
                    "requirements_summary": "Community charter in CA",
                },
            },
            {
                "lender": "Safe 1 Credit Union",
                "state": "CA",
                "product_type": "30-year-fixed",
                "product_name": "30-Year Fixed Rate",
                "rate": 6.000,
                "apr": 6.000,
                "points": 0.0,
                "as_of": "2026-08-14T08:00:00.000Z",
                "eligibility": {
                    "status": "unknown",
                    "requirements_summary": "Charter check",
                },
            },
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        snapshots = adapter.fetch_and_persist_market_rates(state="CA", force_refresh=True)

    assert len(snapshots) == 2
    assert RateApiSnapshotModel.objects.count() == 2

    first = RateApiSnapshotModel.objects.get(lender="Coast Central Credit Union", product_type="5-1-arm")
    assert first.rate == Decimal("5.375")
    assert first.apr == Decimal("5.480")
    assert first.state == "CA"
    assert "Community charter" in first.eligibility_summary

    # Test idempotency: Calling again with same observations updates existing rows without duplicating
    with patch("requests.get", return_value=mock_resp):
        adapter.fetch_and_persist_market_rates(state="CA", force_refresh=True)

    assert RateApiSnapshotModel.objects.count() == 2


@pytest.mark.django_db
def test_product_term_structure_aggregation():
    now = timezone.now().date()
    # Create sample market snapshot models
    RateApiSnapshotModel.objects.create(
        lender="CU 1",
        state="CA",
        product_type="30-year-fixed",
        product_name="30Y Fixed",
        rate=Decimal("6.000"),
        apr=Decimal("6.050"),
        points=Decimal("0.000"),
        observed_on=now,
    )
    RateApiSnapshotModel.objects.create(
        lender="CU 2",
        state="CA",
        product_type="30-year-fixed",
        product_name="30Y Fixed",
        rate=Decimal("6.250"),
        apr=Decimal("6.250"),
        points=Decimal("0.000"),
        observed_on=now,
    )
    RateApiSnapshotModel.objects.create(
        lender="CU 1",
        state="CA",
        product_type="15-year-fixed",
        product_name="15Y Fixed",
        rate=Decimal("5.375"),
        apr=Decimal("5.375"),
        points=Decimal("0.000"),
        observed_on=now,
    )
    RateApiSnapshotModel.objects.create(
        lender="CU 3",
        state="CA",
        product_type="5-1-arm",
        product_name="5/1 ARM",
        rate=Decimal("5.125"),
        apr=Decimal("5.250"),
        points=Decimal("0.000"),
        observed_on=now,
    )

    curve = aggregate_product_term_structure()
    # Should contain aggregated products
    product_keys = [p["label"] for p in curve]
    assert "30-Year Fixed" in product_keys
    assert "15-Year Fixed" in product_keys
    assert "5/1 ARM" in product_keys

    # Check 30-Year Fixed average note rate: (6.000 + 6.250) / 2 = 6.125
    item_30 = next(p for p in curve if p["label"] == "30-Year Fixed")
    assert item_30["avg_rate"] == 6.125
    assert item_30["avg_apr"] == 6.15


@pytest.mark.django_db
def test_calculate_fred_vs_cu_spread():
    today = date.today()
    # Add FRED benchmark
    BenchmarkPointModel.objects.create(
        series="MORTGAGE30US",
        observed_on=today,
        value=Decimal("6.50"),
    )
    # Add CU Snapshot
    RateApiSnapshotModel.objects.create(
        lender="Safe 1 CU",
        state="CA",
        product_type="30-year-fixed",
        product_name="30Y Fixed",
        rate=Decimal("6.00"),
        apr=Decimal("6.00"),
        points=Decimal("0.00"),
        observed_on=today,
    )

    spread_data = calculate_fred_vs_cu_spread()
    assert spread_data["fred_30y"] == 6.50
    assert spread_data["top_cu_30y"] == 6.00
    assert spread_data["spread_bps"] == -50  # 50 bps discount

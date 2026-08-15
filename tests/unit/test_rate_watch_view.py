import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from web.models import BenchmarkPointModel, RateApiSnapshotModel


@pytest.mark.django_db
def test_rate_watch_view_with_rateapi_and_fred_data(client):
    today = date.today()
    five_years_ago = today - timedelta(days=365 * 5)

    # 1. Create FRED benchmarks spanning 5 years
    BenchmarkPointModel.objects.create(
        series="MORTGAGE30US",
        observed_on=five_years_ago,
        value=Decimal("3.100"),
    )
    BenchmarkPointModel.objects.create(
        series="MORTGAGE30US",
        observed_on=today,
        value=Decimal("6.550"),
    )
    BenchmarkPointModel.objects.create(
        series="MORTGAGE15US",
        observed_on=five_years_ago,
        value=Decimal("2.400"),
    )
    BenchmarkPointModel.objects.create(
        series="MORTGAGE15US",
        observed_on=today,
        value=Decimal("5.800"),
    )

    # 2. Create durable RateAPI snapshots
    RateApiSnapshotModel.objects.create(
        lender="Safe 1 Credit Union",
        state="CA",
        product_type="30-year-fixed",
        product_name="30-Year Fixed Rate",
        rate=Decimal("6.000"),
        apr=Decimal("6.000"),
        points=Decimal("0.000"),
        observed_on=today,
    )
    RateApiSnapshotModel.objects.create(
        lender="Coast Central Credit Union",
        state="CA",
        product_type="5-1-arm",
        product_name="5/1 ARM",
        rate=Decimal("5.250"),
        apr=Decimal("5.350"),
        points=Decimal("0.000"),
        observed_on=today,
    )

    url = reverse("web:rate_watch")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Check that context JSONs and template elements are rendered
    assert "product_chart_json" in response.context
    assert "dispersion_chart_json" in response.context
    assert "macro_spread" in response.context

    # Assert 5-year timeline dates are included
    chart_dates = json.loads(response.context["chart_dates_json"])
    assert five_years_ago.strftime("%Y-%m-%d") in chart_dates
    assert today.strftime("%Y-%m-%d") in chart_dates

    # Assert rendered chart labels in response
    assert "30-Year Fixed" in content
    assert "Safe 1" in content
    assert "FRED" in content or "Freddie Mac" in content


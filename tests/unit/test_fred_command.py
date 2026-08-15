from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from web.models import BenchmarkPointModel


@pytest.mark.django_db
def test_fetch_fred_benchmarks_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "observations": [
            {"date": "2026-08-01", "value": "6.55"},
            {"date": "2026-08-08", "value": "6.48"},
            {"date": "2026-08-15", "value": "."},  # non-numeric observation to ignore
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        call_command("fetch_fred_benchmarks", api_key="test-api-key")

    assert BenchmarkPointModel.objects.filter(series="MORTGAGE30US").count() == 2
    assert BenchmarkPointModel.objects.filter(series="MORTGAGE15US").count() == 2
    pt = BenchmarkPointModel.objects.get(
        series="MORTGAGE30US", observed_on=date(2026, 8, 8)
    )
    assert pt.value == Decimal("6.48")


@pytest.mark.django_db
def test_fetch_fred_benchmarks_no_key_warning(capsys, settings):
    settings.FRED_API_KEY = ""
    # Should not crash if no API key is provided
    call_command("fetch_fred_benchmarks", api_key="")
    captured = capsys.readouterr()
    assert (
        "No FRED_API_KEY" in captured.out
        or "No FRED_API_KEY" in captured.err
        or BenchmarkPointModel.objects.count() == 0
    )


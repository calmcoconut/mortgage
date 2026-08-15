from datetime import date
from decimal import Decimal
import pytest
from django.urls import reverse
from web.models import LoanOptionModel, ScenarioModel


@pytest.fixture
def sample_scenario():
    return ScenarioModel.objects.create(
        name="Test Scenario",
        property_value=Decimal("500000.00"),
        loan_amount=Decimal("400000.00"),
        term_months=360,
        expected_horizon_months=84,
    )


@pytest.mark.django_db
def test_create_loan_option_post(client, sample_scenario):
    url = reverse("web:option_create", kwargs={"scenario_id": sample_scenario.id})
    resp = client.post(url, {
        "label": "Lender C",
        "source_type": "manual",
        "entered_on": "2026-08-14",
        "loan_amount": "400000",
        "term_months": "360",
        "rate_percent": "6.25",
        "points_percent": "1.0",
        "lender_credit": "0",
        "lender_fees": "500",
        "monthly_mi": "0",
        "upfront_mi": "0",
    })
    assert resp.status_code == 302
    assert sample_scenario.loan_options.count() == 1
    opt = sample_scenario.loan_options.first()
    assert opt.label == "Lender C"
    assert opt.note_rate == Decimal("0.0625")
    assert opt.points_pct == Decimal("0.0100")


@pytest.mark.django_db
def test_edit_and_delete_loan_option(client, sample_scenario):
    opt = LoanOptionModel.objects.create(
        scenario=sample_scenario,
        label="Old Label",
        source_type="manual",
        entered_on=date(2026, 8, 14),
        loan_amount=Decimal("400000"),
        note_rate=Decimal("0.0650"),
        term_months=360,
        points_pct=Decimal("0.0"),
    )
    edit_url = reverse("web:option_edit", kwargs={"scenario_id": sample_scenario.id, "option_id": opt.id})
    resp = client.post(edit_url, {
        "label": "Updated Label",
        "source_type": "loan_estimate",
        "entered_on": "2026-08-14",
        "loan_amount": "400000",
        "term_months": "360",
        "rate_percent": "5.875",
        "points_percent": "2.0",
        "lender_credit": "0",
        "lender_fees": "0",
    })
    assert resp.status_code == 302
    opt.refresh_from_db()
    assert opt.label == "Updated Label"
    assert opt.note_rate == Decimal("0.05875")

    del_url = reverse("web:option_delete", kwargs={"scenario_id": sample_scenario.id, "option_id": opt.id})
    resp_del = client.post(del_url)
    assert resp_del.status_code == 302
    assert sample_scenario.loan_options.count() == 0

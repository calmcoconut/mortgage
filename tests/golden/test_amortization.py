from decimal import Decimal

from core.amortization import calculate_amortization, calculate_monthly_pi
from core.money import money


def test_monthly_pi_worked_fixture():
    # Option A: $400,000, 30 years, 6.50%
    pi_a = calculate_monthly_pi(
        loan_amount=Decimal("400000"),
        note_rate=Decimal("0.0650"),
        term_months=360,
    )
    assert money(pi_a) == Decimal("2528.27")

    # Option B: $400,000, 30 years, 6.00%
    pi_b = calculate_monthly_pi(
        loan_amount=Decimal("400000"),
        note_rate=Decimal("0.0600"),
        term_months=360,
    )
    assert money(pi_b) == Decimal("2398.20")


def test_amortization_360_months_reconciliation():
    schedule = calculate_amortization(
        loan_amount=Decimal("400000"),
        note_rate=Decimal("0.0650"),
        term_months=360,
        monthly_mi=Decimal("0"),
    )
    assert len(schedule) == 360
    # Month 1
    assert schedule[0].month == 1
    assert money(schedule[0].payment) == Decimal("2528.27")
    assert money(schedule[0].interest) == Decimal("2166.67")
    assert money(schedule[0].principal) == Decimal("361.61")

    # Month 360 final payment and zero balance
    last_row = schedule[-1]
    assert last_row.month == 360
    assert money(last_row.balance) == Decimal("0.00")
    assert last_row.balance == Decimal("0")

    # Sum of principal equals original loan amount exactly
    total_principal = sum(row.principal for row in schedule)
    assert money(total_principal) == Decimal("400000.00")


def test_amortization_12_months_reconciliation():
    schedule = calculate_amortization(
        loan_amount=Decimal("120000"),
        note_rate=Decimal("0.0500"),
        term_months=12,
        monthly_mi=Decimal("0"),
    )
    assert len(schedule) == 12
    assert schedule[-1].balance == Decimal("0")
    total_principal = sum(row.principal for row in schedule)
    assert money(total_principal) == Decimal("120000.00")


def test_amortization_zero_interest_rate():
    schedule = calculate_amortization(
        loan_amount=Decimal("12000"),
        note_rate=Decimal("0.0000"),
        term_months=12,
        monthly_mi=Decimal("0"),
    )
    assert len(schedule) == 12
    for row in schedule:
        assert money(row.interest) == Decimal("0.00")
        assert money(row.principal) == Decimal("1000.00")
    assert schedule[-1].balance == Decimal("0")

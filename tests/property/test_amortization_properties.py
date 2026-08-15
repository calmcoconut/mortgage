from decimal import Decimal
from hypothesis import given, settings, strategies as st
from core.amortization import calculate_amortization
from core.money import money


@settings(max_examples=100)
@given(
    loan_amount=st.decimals(min_value=Decimal("10000"), max_value=Decimal("2000000"), places=2),
    rate_pct=st.decimals(min_value=Decimal("0.0"), max_value=Decimal("20.0"), places=4),
    term_months=st.integers(min_value=12, max_value=480),
)
def test_amortization_invariants(loan_amount: Decimal, rate_pct: Decimal, term_months: int):
    note_rate = rate_pct / Decimal("100")
    schedule = calculate_amortization(
        loan_amount=loan_amount,
        note_rate=note_rate,
        term_months=term_months,
    )

    assert len(schedule) == term_months

    # Invariant 1: Final balance is exactly zero
    assert schedule[-1].balance == Decimal("0")

    # Invariant 2: Sum of principal equals loan amount exactly
    total_principal = sum(row.principal for row in schedule)
    assert money(total_principal) == money(loan_amount)

    # Invariant 3: No intermediate balance is negative
    for row in schedule:
        assert row.balance >= Decimal("0")
        assert row.principal >= Decimal("0")
        assert row.interest >= Decimal("0")


@settings(max_examples=50)
@given(
    loan_amount=st.decimals(min_value=Decimal("50000"), max_value=Decimal("1000000"), places=2),
    rate1_pct=st.decimals(min_value=Decimal("0.0"), max_value=Decimal("10.0"), places=2),
    rate2_pct=st.decimals(min_value=Decimal("10.01"), max_value=Decimal("20.0"), places=2),
    term_months=st.sampled_from([180, 240, 360]),
)
def test_total_interest_monotonic_with_rate(
    loan_amount: Decimal,
    rate1_pct: Decimal,
    rate2_pct: Decimal,
    term_months: int,
):
    # For higher rate, total interest must be strictly greater (or equal if rates were equal)
    rate1 = rate1_pct / Decimal("100")
    rate2 = rate2_pct / Decimal("100")

    schedule1 = calculate_amortization(loan_amount, rate1, term_months)
    schedule2 = calculate_amortization(loan_amount, rate2, term_months)

    total_interest_1 = sum(r.interest for r in schedule1)
    total_interest_2 = sum(r.interest for r in schedule2)

    assert total_interest_2 >= total_interest_1

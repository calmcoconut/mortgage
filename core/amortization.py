from decimal import Decimal

from core.models import AmortizationRow


def calculate_monthly_pi(
    loan_amount: Decimal,
    note_rate: Decimal,
    term_months: int,
) -> Decimal:
    """Calculate fixed-rate monthly principal & interest (P&I) payment at full Decimal precision."""
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if loan_amount < 0:
        raise ValueError("loan_amount cannot be negative")

    if note_rate == Decimal("0"):
        return loan_amount / Decimal(term_months)

    monthly_rate = note_rate / Decimal("12")
    # P = L * [r * (1 + r)^n] / [(1 + r)^n - 1]
    # Use Decimal power
    factor = (Decimal("1") + monthly_rate) ** term_months
    numerator = loan_amount * monthly_rate * factor
    denominator = factor - Decimal("1")
    return numerator / denominator


def calculate_amortization(
    loan_amount: Decimal,
    note_rate: Decimal,
    term_months: int,
    monthly_mi: Decimal = Decimal("0"),
) -> tuple[AmortizationRow, ...]:
    """Generate fixed-rate amortization schedule with exact final-payment reconciliation."""
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if loan_amount <= Decimal("0"):
        return ()

    monthly_pi = calculate_monthly_pi(loan_amount, note_rate, term_months)
    monthly_rate = note_rate / Decimal("12")

    current_balance = loan_amount
    rows: list[AmortizationRow] = []

    for month in range(1, term_months + 1):
        interest = current_balance * monthly_rate

        if month == term_months:
            # Final month: set principal to exact remaining balance, adjust payment to clear balance to zero
            principal = current_balance
            payment = interest + principal
            current_balance = Decimal("0")
        else:
            principal = monthly_pi - interest
            current_balance = current_balance - principal
            payment = monthly_pi

        rows.append(
            AmortizationRow(
                month=month,
                payment=payment,
                principal=principal,
                interest=interest,
                mortgage_insurance=monthly_mi,
                balance=current_balance,
            )
        )

    return tuple(rows)

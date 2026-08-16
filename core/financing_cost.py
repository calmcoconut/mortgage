from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from core.amortization import calculate_amortization, calculate_monthly_pi
from core.models import (
    BreakEvenResult,
    ComparisonResult,
    LoanOptionInput,
    OptionResult,
    ScenarioInput,
)


def calculate_net_upfront(option: LoanOptionInput) -> Decimal:
    """Compute net upfront loan costs: points - credits + fees + upfront_mi."""
    points_dollars = option.loan_amount * option.points_pct
    upfront_mi = option.upfront_mi or Decimal("0")
    return points_dollars - option.lender_credit + option.lender_fees + upfront_mi


def calculate_option_result(
    option: LoanOptionInput,
    horizon_months: int,
) -> OptionResult:
    """Compute detailed amortization, cumulative financing costs, and horizon results for a loan option."""
    monthly_mi = option.monthly_mi or Decimal("0")
    schedule = calculate_amortization(
        loan_amount=option.loan_amount,
        note_rate=option.note_rate,
        term_months=option.term_months,
        monthly_mi=monthly_mi,
    )
    monthly_pi = calculate_monthly_pi(
        option.loan_amount, option.note_rate, option.term_months
    )
    net_upfront = calculate_net_upfront(option)

    # Cumulative financing costs by month (month 0 is net_upfront)
    costs_by_month: list[Decimal] = [net_upfront]
    cumulative_interest_mi = Decimal("0")

    for row in schedule:
        cumulative_interest_mi += row.interest + row.mortgage_insurance
        costs_by_month.append(net_upfront + cumulative_interest_mi)

    # Determine cost and balance at target horizon
    clamped_horizon = min(max(horizon_months, 0), option.term_months)
    cost_at_horizon = costs_by_month[clamped_horizon]

    if clamped_horizon == 0:
        balance_at_horizon = option.loan_amount
        cum_interest = Decimal("0")
        cum_mi = Decimal("0")
    else:
        balance_at_horizon = schedule[clamped_horizon - 1].balance
        cum_interest = sum((r.interest for r in schedule[:clamped_horizon]), Decimal("0"))
        cum_mi = sum((r.mortgage_insurance for r in schedule[:clamped_horizon]), Decimal("0"))

    return OptionResult(
        option_id=option.option_id,
        label=option.label,
        source_type=option.source_type,
        monthly_pi=monthly_pi,
        amortization=schedule,
        net_upfront=net_upfront,
        financing_cost_by_month=tuple(costs_by_month),
        financing_cost_at_horizon=cost_at_horizon,
        remaining_balance_at_horizon=balance_at_horizon,
        cumulative_interest_at_horizon=cum_interest,
        cumulative_mi_at_horizon=cum_mi,
        note_rate=option.note_rate,
        apr=option.apr,
        points_pct=option.points_pct,
        lender_fees=option.lender_fees,
        lender_credit=option.lender_credit,
        monthly_mi=monthly_mi,
        term_months=option.term_months,
    )


def calculate_break_even(
    candidate: LoanOptionInput,
    baseline: LoanOptionInput,
    horizon_months: int,
    discount_rate: Decimal | None = None,
) -> BreakEvenResult:
    """Find points break-even month and horizon savings between candidate (e.g. paying points) and baseline."""
    res_candidate = calculate_option_result(candidate, horizon_months)
    res_baseline = calculate_option_result(baseline, horizon_months)

    savings_at_horizon = (
        res_baseline.financing_cost_at_horizon - res_candidate.financing_cost_at_horizon
    )

    upfront_delta = res_candidate.net_upfront - res_baseline.net_upfront
    interest_delta = (
        res_candidate.cumulative_interest_at_horizon
        - res_baseline.cumulative_interest_at_horizon
    )
    mi_delta = (
        res_candidate.cumulative_mi_at_horizon
        - res_baseline.cumulative_mi_at_horizon
    )
    monthly_pi_delta = res_candidate.monthly_pi - res_baseline.monthly_pi

    max_months = min(candidate.term_months, baseline.term_months)
    break_even_month: int | None = None

    for m in range(1, max_months + 1):
        if (
            res_candidate.financing_cost_by_month[m]
            < res_baseline.financing_cost_by_month[m]
        ):
            break_even_month = m
            break

    discounted_break_even_month: int | None = None
    discounted_savings: Decimal | None = None

    if discount_rate is not None and discount_rate > Decimal("0"):
        # Calculate discounted outflows
        disc_monthly_rate = discount_rate / Decimal("12")
        cand_net_upfront = res_candidate.net_upfront
        base_net_upfront = res_baseline.net_upfront

        cand_disc_outflows: list[Decimal] = [cand_net_upfront]
        base_disc_outflows: list[Decimal] = [base_net_upfront]

        cand_running = cand_net_upfront
        base_running = base_net_upfront

        for m in range(1, max_months + 1):
            factor = (Decimal("1") + disc_monthly_rate) ** m
            cand_row = res_candidate.amortization[m - 1]
            base_row = res_baseline.amortization[m - 1]

            cand_payment = cand_row.payment + cand_row.mortgage_insurance
            base_payment = base_row.payment + base_row.mortgage_insurance

            cand_running += cand_payment / factor
            base_running += base_payment / factor

            cand_disc_outflows.append(cand_running)
            base_disc_outflows.append(base_running)

            if discounted_break_even_month is None and cand_running < base_running:
                discounted_break_even_month = m

        clamped_h = min(horizon_months, max_months)
        discounted_savings = (
            base_disc_outflows[clamped_h] - cand_disc_outflows[clamped_h]
        )

    # Human-friendly derivation explanation
    horizon_years = horizon_months // 12
    explanation = ""
    if break_even_month is not None:
        if break_even_month <= horizon_months:
            explanation = (
                f"Upfront points/fees recoup by Month {break_even_month} "
                f"({(break_even_month / 12):.1f} yrs), saving ${savings_at_horizon:,.0f} net over your {horizon_years}-year hold."
            )
        else:
            explanation = (
                f"Break-even occurs in Month {break_even_month} "
                f"({(break_even_month / 12):.1f} yrs), which is after your planned {horizon_years}-year hold."
            )
    else:
        if upfront_delta > 0 and monthly_pi_delta >= 0:
            explanation = (
                f"Higher upfront fees (${upfront_delta:,.0f}) never pay off because monthly payment is not lower."
            )
        elif upfront_delta > 0:
            explanation = (
                f"Points don't pay off within your {horizon_years}-year hold period "
                f"(monthly savings of ${abs(monthly_pi_delta):,.0f}/mo are insufficient to recoup ${upfront_delta:,.0f} in upfront fees)."
            )
        elif savings_at_horizon > 0:
            explanation = (
                f"{candidate.label} is cheaper immediately from Month 1 "
                f"(lower upfront costs and lower/equal monthly payments)."
            )
        else:
            explanation = f"Baseline remains cheaper over your {horizon_years}-year holding horizon."

    return BreakEvenResult(
        candidate_id=candidate.option_id,
        baseline_id=baseline.option_id,
        break_even_month=break_even_month,
        savings_at_horizon=savings_at_horizon,
        discounted_break_even_month=discounted_break_even_month,
        discounted_savings_at_horizon=discounted_savings,
        break_even_explanation=explanation,
        upfront_delta=upfront_delta,
        interest_delta_at_horizon=interest_delta,
        mi_delta_at_horizon=mi_delta,
        monthly_pi_delta=monthly_pi_delta,
    )


def compare_options(
    scenario: ScenarioInput,
    options: Sequence[LoanOptionInput],
    horizon_months: int | None = None,
    discount_rate: Decimal | None = None,
) -> ComparisonResult:
    """Compare multiple loan options for a given scenario at target horizon."""
    target_horizon = (
        horizon_months
        if horizon_months is not None
        else scenario.expected_horizon_months
    )
    results = [calculate_option_result(opt, target_horizon) for opt in options]

    recommended_id: UUID | None = None
    if results:
        # Lowest financing cost at target horizon
        best = min(results, key=lambda r: r.financing_cost_at_horizon)
        recommended_id = best.option_id

    break_even: BreakEvenResult | None = None
    if len(options) >= 2:
        # By default compute break-even of the lowest-rate/points option vs first baseline option
        candidate = options[1] if len(options) > 1 else options[0]
        baseline = options[0]
        break_even = calculate_break_even(
            candidate=candidate,
            baseline=baseline,
            horizon_months=target_horizon,
            discount_rate=discount_rate,
        )

    return ComparisonResult(
        horizon_months=target_horizon,
        option_results=tuple(results),
        break_even=break_even,
        recommended_option_id=recommended_id,
    )

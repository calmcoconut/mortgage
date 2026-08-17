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
    scenario: ScenarioInput | None = None,
) -> OptionResult:
    """Compute detailed amortization, cumulative financing costs, total cash outflows, home equity, and horizon results."""
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

    # Total Cash Outflows (PITI + HOA + Upfront + Down Payment) & Home Equity Buildup
    monthly_escrow = Decimal("0")
    down_payment = Decimal("0")
    property_val_0 = option.loan_amount
    annual_appreciation = Decimal("0.03")
    itemize_deductions = False
    marginal_tax_rate = Decimal("0.0")
    filing_status = "single"

    if scenario:
        monthly_escrow = (
            (scenario.estimated_property_tax_monthly or Decimal("0"))
            + (scenario.estimated_homeowners_insurance_monthly or Decimal("0"))
            + (scenario.estimated_hoa_monthly or Decimal("0"))
        )
        down_payment = scenario.down_payment or Decimal("0")
        if scenario.property_value and scenario.property_value > Decimal("0"):
            property_val_0 = scenario.property_value
        else:
            property_val_0 = option.loan_amount + down_payment
        annual_appreciation = scenario.annual_appreciation_pct or Decimal("0.03")
        itemize_deductions = scenario.itemize_deductions
        marginal_tax_rate = scenario.marginal_tax_rate_pct or Decimal("0.0")
        filing_status = scenario.filing_status

    total_piti_monthly = monthly_pi + monthly_mi + monthly_escrow

    # Month-by-month total cash outflow
    initial_outflow = net_upfront + down_payment
    outflow_by_month: list[Decimal] = [initial_outflow]
    running_outflow = initial_outflow

    # Month-by-month home equity buildup
    initial_equity = max(property_val_0 - option.loan_amount, Decimal("0"))
    home_equity_by_month: list[Decimal] = [initial_equity]

    monthly_appreciation_factor = Decimal("1") + (annual_appreciation / Decimal("12"))

    for m_idx, row in enumerate(schedule, start=1):
        running_outflow += row.payment + row.mortgage_insurance + monthly_escrow
        outflow_by_month.append(running_outflow)

        future_prop_val = property_val_0 * (monthly_appreciation_factor ** m_idx)
        equity_m = max(future_prop_val - row.balance, Decimal("0"))
        home_equity_by_month.append(equity_m)

    # After-tax financing cost calculation (IRS acquisition debt cap $750k)
    after_tax_cost_by_month: list[Decimal] = list(costs_by_month)
    if itemize_deductions and marginal_tax_rate > Decimal("0"):
        std_deduction = Decimal("14600") if filing_status == "single" else Decimal("29200")
        debt_limit_ratio = (
            min(Decimal("1"), Decimal("750000") / option.loan_amount)
            if option.loan_amount > Decimal("0")
            else Decimal("1")
        )

        running_tax_savings = Decimal("0")
        after_tax_costs: list[Decimal] = [net_upfront]

        num_years = (len(schedule) + 11) // 12
        for y in range(1, num_years + 1):
            y_start = (y - 1) * 12
            y_end = min(y * 12, len(schedule))
            year_interest = sum(
                (schedule[i].interest for i in range(y_start, y_end)), Decimal("0")
            )
            eligible_interest = year_interest * debt_limit_ratio
            year_excess = max(Decimal("0"), eligible_interest - std_deduction)
            year_tax_savings = year_excess * marginal_tax_rate
            months_in_year = Decimal(str(y_end - y_start))
            monthly_tax_savings = (
                year_tax_savings / months_in_year if months_in_year > Decimal("0") else Decimal("0")
            )

            for m in range(y_start + 1, y_end + 1):
                running_tax_savings += monthly_tax_savings
                after_tax_costs.append(
                    max(Decimal("0"), costs_by_month[m] - running_tax_savings)
                )

        if len(after_tax_costs) == len(costs_by_month):
            after_tax_cost_by_month = after_tax_costs

    # Determine cost and balance at target horizon
    clamped_horizon = min(max(horizon_months, 0), option.term_months)
    cost_at_horizon = costs_by_month[clamped_horizon]
    outflow_at_horizon = (
        outflow_by_month[clamped_horizon]
        if clamped_horizon < len(outflow_by_month)
        else outflow_by_month[-1]
    )
    equity_at_horizon = (
        home_equity_by_month[clamped_horizon]
        if clamped_horizon < len(home_equity_by_month)
        else home_equity_by_month[-1]
    )
    after_tax_at_horizon = (
        after_tax_cost_by_month[clamped_horizon]
        if clamped_horizon < len(after_tax_cost_by_month)
        else after_tax_cost_by_month[-1]
    )

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
        total_outflow_by_month=tuple(outflow_by_month),
        home_equity_by_month=tuple(home_equity_by_month),
        after_tax_cost_by_month=tuple(after_tax_cost_by_month),
        total_outflow_at_horizon=outflow_at_horizon,
        home_equity_at_horizon=equity_at_horizon,
        after_tax_cost_at_horizon=after_tax_at_horizon,
        total_piti_monthly=total_piti_monthly,
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

    if upfront_delta <= 0:
        if monthly_pi_delta <= 0:
            # Candidate has lower or equal upfront cost AND lower/equal monthly payment -> Cheaper from Day 1!
            break_even_month = 0
        else:
            # Candidate is cheaper upfront, but baseline has lower monthly payment.
            # Baseline eventually catches up to candidate at month m.
            for m in range(1, max_months + 1):
                if (
                    res_baseline.financing_cost_by_month[m]
                    < res_candidate.financing_cost_by_month[m]
                ):
                    break_even_month = m
                    break
    else:
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
    if break_even_month == 0:
        if upfront_delta < 0 and monthly_pi_delta < 0:
            explanation = (
                f"No upfront cost to recoup — candidate starts with lower upfront fees (-${abs(upfront_delta):,.0f}) "
                f"and saves ${abs(monthly_pi_delta):,.0f}/mo immediately (${savings_at_horizon:,.0f} net savings over {horizon_years} yrs)."
            )
        elif upfront_delta < 0:
            explanation = (
                f"No upfront cost to recoup — candidate provides ${abs(upfront_delta):,.0f} in upfront savings "
                f"(${savings_at_horizon:,.0f} net savings over {horizon_years} yrs)."
            )
        else:
            explanation = (
                f"Candidate option is cheaper from Day 1 (${savings_at_horizon:,.0f} net savings over {horizon_years} yrs)."
            )
    elif break_even_month is not None:
        years_fmt = (
            f"{break_even_month / 12:.1f}"
            if break_even_month % 12 != 0
            else f"{break_even_month // 12}"
        )
        if upfront_delta <= 0:
            explanation = (
                f"Candidate is cheaper upfront by ${abs(upfront_delta):,.0f}, but baseline's lower monthly payment "
                f"catches up by Month {break_even_month} ({years_fmt} yrs)."
            )
        elif break_even_month <= horizon_months:
            explanation = (
                f"Upfront points/fees recoup by Month {break_even_month} "
                f"({years_fmt} yrs), saving ${savings_at_horizon:,.0f} net over your {horizon_years}-year hold."
            )
        else:
            explanation = (
                f"Break-even occurs in Month {break_even_month} "
                f"({years_fmt} yrs), which is after your planned {horizon_years}-year hold."
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
                f"{candidate.label} is cheaper immediately from Day 1 "
                f"(lower upfront costs and lower monthly payments)."
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
    results = [
        calculate_option_result(opt, target_horizon, scenario=scenario)
        for opt in options
    ]

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
        scenario=scenario,
    )

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db import transaction

from core.financing_cost import compare_options
from core.models import (
    ComparisonResult,
    LoanOptionInput,
    ScenarioInput,
    SourceType,
)
from web.models import LoanOptionModel, ScenarioModel


def scenario_to_input(model: ScenarioModel) -> ScenarioInput:
    """Convert Django ScenarioModel into frozen core ScenarioInput."""
    return ScenarioInput(
        purpose=model.purpose,  # type: ignore
        property_value=model.property_value,
        loan_amount=model.loan_amount,
        down_payment=model.down_payment,
        fico_band=model.fico_band,
        occupancy=model.occupancy,  # type: ignore
        property_type=model.property_type,  # type: ignore
        state=model.state,
        county_fips=model.county_fips,
        program=model.program,  # type: ignore
        term_months=model.term_months,
        expected_horizon_months=model.expected_horizon_months,
        gross_monthly_income=model.gross_monthly_income,
        recurring_monthly_debts=model.recurring_monthly_debts,
        estimated_property_tax_monthly=model.estimated_property_tax_monthly,
        estimated_homeowners_insurance_monthly=model.estimated_homeowners_insurance_monthly,
        estimated_hoa_monthly=model.estimated_hoa_monthly,
        annual_appreciation_pct=model.annual_appreciation_pct,
        marginal_tax_rate_pct=model.marginal_tax_rate_pct or Decimal("0"),
        itemize_deductions=model.itemize_deductions,
        filing_status=model.filing_status,  # type: ignore
    )


def loan_option_to_input(model: LoanOptionModel) -> LoanOptionInput:
    """Convert Django LoanOptionModel into frozen core LoanOptionInput."""
    return LoanOptionInput(
        option_id=model.id,
        label=model.label,
        source_type=SourceType(model.source_type),
        entered_on=model.entered_on,
        loan_amount=model.loan_amount,
        note_rate=model.note_rate,
        apr=model.apr,
        term_months=model.term_months,
        points_pct=model.points_pct,
        lender_credit=model.lender_credit,
        lender_fees=model.lender_fees,
        monthly_mi=model.monthly_mi,
        upfront_mi=model.upfront_mi,
        notes=model.notes,
    )


def compare_scenario(
    scenario_id: UUID | str,
    horizon_months: int | None = None,
    discount_rate: Decimal | None = None,
) -> ComparisonResult:
    """Load scenario and options from DB, convert at the boundary, and run core comparison."""
    scenario_model = ScenarioModel.objects.get(id=scenario_id)
    option_models = list(scenario_model.loan_options.all().order_by("created_at"))

    scenario_input = scenario_to_input(scenario_model)
    option_inputs = [loan_option_to_input(opt) for opt in option_models]

    return compare_options(
        scenario=scenario_input,
        options=option_inputs,
        horizon_months=horizon_months,
        discount_rate=discount_rate,
    )


def format_clean_label(raw_label: str) -> str:
    """Standardize lender and option labels into clean, title-cased professional strings."""
    if not raw_label:
        return "Conforming Option"

    raw = raw_label.strip()

    # Map known lowercase abbreviations
    known_abbrevs = {
        "sfcu": "San Francisco Federal Credit Union",
        "tech cu": "Tech CU",
        "star one": "Star One Credit Union",
        "first tech": "First Tech Federal Credit Union",
    }
    if raw.lower() in known_abbrevs:
        return known_abbrevs[raw.lower()]

    # Check for parenthesis product tails like (30-YEAR FIXED), (30y fixed conventional), (5/6 ARM), (7/6 ARM)
    match_tail = re.search(
        r"\s*\(((?:30|15|10|7|5|3)(?:-year|-yr|\/1|\/6|y| yr| year)?\s*(?:fixed|arm)?(?:\s*(?:conforming|conventional))?)\)",
        raw,
        flags=re.IGNORECASE,
    )
    if match_tail:
        product_text = match_tail.group(1).strip().upper()
        # Clean product text
        if "30" in product_text and "FIXED" in product_text:
            cleaned_product = "30Y Fixed"
        elif "15" in product_text and "FIXED" in product_text:
            cleaned_product = "15Y Fixed"
        elif "10" in product_text and "FIXED" in product_text:
            cleaned_product = "10Y Fixed"
        elif "7/1" in product_text or "7/6" in product_text:
            cleaned_product = "7/6 ARM" if "7/6" in product_text else "7/1 ARM"
        elif "5/1" in product_text or "5/6" in product_text:
            cleaned_product = "5/6 ARM" if "5/6" in product_text else "5/1 ARM"
        elif "3/1" in product_text:
            cleaned_product = "3/1 ARM"
        else:
            cleaned_product = product_text.title()

        lender_prefix = raw[: match_tail.start()].strip()
        if "/" in lender_prefix:
            domain_part = lender_prefix.split("/")[0]
            if "neohomeloans" in domain_part.lower():
                lender_prefix = "Neo Home Loans"
            else:
                lender_prefix = re.sub(r"[_\-]+", " ", domain_part).title()
        if lender_prefix.lower() in known_abbrevs:
            lender_prefix = known_abbrevs[lender_prefix.lower()]
        elif lender_prefix.isupper() or lender_prefix.islower():
            lender_prefix = lender_prefix.title()
        return f"{lender_prefix} · {cleaned_product}"

    # Clean URL or domain paths like "neohomeloans/branch/..." or "https://neohomeloans.com/..."
    if (
        "://" in raw
        or re.search(
            r"^(?:https?:\/\/)?(?:www\.)?[a-zA-Z0-9_\-]+\.(?:com|org|net|io|co)(?:\/.*)?$",
            raw,
            re.IGNORECASE,
        )
        or re.search(
            r"^[a-zA-Z0-9_\-]+\/(?:branch|lenders|rates|quotes|better)\b",
            raw,
            re.IGNORECASE,
        )
    ):
        domain_part = (
            raw.split("://")[-1]
            .split("/")[0]
            .replace(".com", "")
            .replace(".org", "")
            .replace(".net", "")
            .replace("www.", "")
        )
        clean_name = re.sub(r"[_\-]+", " ", domain_part).title()
        if clean_name.lower().replace(" ", "") == "neohomeloans":
            clean_name = "Neo Home Loans"
        raw = clean_name

    if raw.isupper() and len(raw) > 5:
        return raw.title()

    return raw


def build_projected_costs_chart_data(comparison: ComparisonResult) -> dict[str, Any]:
    """Serialize comparison result into server-computed JSON data structures for Chart.js.
    Per Section 7.2 of Design Spec: Chart.js never calculates source-of-truth numbers.
    """
    if not comparison.option_results:
        return {"months": [], "series": []}

    max_term = max(len(opt.amortization) for opt in comparison.option_results)
    months = list(range(0, max_term + 1))

    # Scenario appreciation and escrow context for projecting post-payoff horizons
    property_val_0 = Decimal("0")
    monthly_escrow = Decimal("0")
    monthly_appreciation_factor = Decimal("1")
    if comparison.scenario:
        sc = comparison.scenario
        down_payment = sc.down_payment or Decimal("0")
        if sc.property_value and sc.property_value > Decimal("0"):
            property_val_0 = sc.property_value
        else:
            property_val_0 = (sc.loan_amount or Decimal("0")) + down_payment
        annual_appreciation = sc.annual_appreciation_pct or Decimal("0.03")
        monthly_appreciation_factor = Decimal("1") + (
            annual_appreciation / Decimal("12")
        )
        monthly_escrow = (
            (sc.estimated_property_tax_monthly or Decimal("0"))
            + (sc.estimated_homeowners_insurance_monthly or Decimal("0"))
            + (sc.estimated_hoa_monthly or Decimal("0"))
        )

    series = []
    for opt in comparison.option_results:
        # Precomputed cumulative financing cost (holds constant once paid off)
        cost_series = [float(round(c, 2)) for c in opt.financing_cost_by_month]
        if len(cost_series) < len(months):
            cost_series.extend([cost_series[-1]] * (len(months) - len(cost_series)))

        # Precomputed remaining loan balance (0 once paid off)
        balance_series = [
            float(round(opt.amortization[0].principal + opt.amortization[0].balance, 2))
            if opt.amortization
            else 0.0
        ]
        for row in opt.amortization:
            balance_series.append(float(round(row.balance, 2)))
        if len(balance_series) < len(months):
            balance_series.extend([0.0] * (len(months) - len(balance_series)))

        # Precomputed payment composition breakdown
        principal_by_month = [0.0] + [
            float(round(r.principal, 2)) for r in opt.amortization
        ]
        if len(principal_by_month) < len(months):
            principal_by_month.extend([0.0] * (len(months) - len(principal_by_month)))

        interest_by_month = [0.0] + [
            float(round(r.interest, 2)) for r in opt.amortization
        ]
        if len(interest_by_month) < len(months):
            interest_by_month.extend([0.0] * (len(months) - len(interest_by_month)))

        mi_by_month = [0.0] + [
            float(round(r.mortgage_insurance, 2)) for r in opt.amortization
        ]
        if len(mi_by_month) < len(months):
            mi_by_month.extend([0.0] * (len(months) - len(mi_by_month)))

        # Outflow series (continues with escrow once loan is paid off)
        outflow_series = [float(round(v, 2)) for v in opt.total_outflow_by_month]
        if len(outflow_series) < len(months):
            last_outflow = Decimal(str(outflow_series[-1]))
            for _ in range(len(months) - len(outflow_series)):
                last_outflow += monthly_escrow
                outflow_series.append(float(round(last_outflow, 2)))

        # Home equity series (continues growing with full property value once loan balance is 0)
        equity_series = [float(round(v, 2)) for v in opt.home_equity_by_month]
        if len(equity_series) < len(months):
            for m in range(len(equity_series), len(months)):
                if property_val_0 > Decimal("0"):
                    future_prop_val = property_val_0 * (
                        monthly_appreciation_factor**m
                    )
                else:
                    future_prop_val = Decimal(str(equity_series[-1]))
                equity_series.append(float(round(future_prop_val, 2)))

        # After tax cost series (holds constant once paid off)
        after_tax_series = [float(round(v, 2)) for v in opt.after_tax_cost_by_month]
        if len(after_tax_series) < len(months):
            after_tax_series.extend(
                [after_tax_series[-1]] * (len(months) - len(after_tax_series))
            )

        is_verified = opt.source_type in ["loan_estimate", "manual"]
        clean_lbl = format_clean_label(opt.label)

        series.append(
            {
                "option_id": str(opt.option_id),
                "label": clean_lbl,
                "raw_label": opt.label,
                "source_type": str(opt.source_type),
                "is_verified": is_verified,
                "monthly_pi": float(round(opt.monthly_pi, 2)),
                "total_piti": float(round(opt.total_piti_monthly, 2)),
                "financing_cost": cost_series,
                "total_outflow": outflow_series,
                "home_equity": equity_series,
                "after_tax_cost": after_tax_series,
                "balance": balance_series,
                "principal": principal_by_month,
                "interest": interest_by_month,
                "mi": mi_by_month,
                "net_upfront": float(round(opt.net_upfront, 2)),
                "cumulative_interest": float(
                    round(opt.cumulative_interest_at_horizon, 2)
                ),
                "cumulative_mi": float(round(opt.cumulative_mi_at_horizon, 2)),
                "total_horizon_cost": float(
                    round(opt.financing_cost_at_horizon, 2)
                ),
                "total_outflow_at_horizon": float(
                    round(opt.total_outflow_at_horizon, 2)
                ),
                "home_equity_at_horizon": float(
                    round(opt.home_equity_at_horizon, 2)
                ),
                "after_tax_cost_at_horizon": float(
                    round(opt.after_tax_cost_at_horizon, 2)
                ),
                "note_rate_pct": float(round(opt.note_rate * Decimal("100"), 3)),
                "apr_pct": float(round(opt.apr * Decimal("100"), 3))
                if opt.apr
                else None,
                "points_pct": float(round(opt.points_pct * Decimal("100"), 3)),
            }
        )

    return {
        "months": months,
        "series": series,
        "break_even_month": comparison.break_even.break_even_month
        if comparison.break_even
        else None,
        "break_even_explanation": comparison.break_even.break_even_explanation
        if comparison.break_even
        else "",
        "horizon_months": comparison.horizon_months,
    }


def parse_json_decimal(
    val: Any, default: Decimal | None = None
) -> Decimal | None:
    if val is None or val == "":
        return default
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    if isinstance(val, str):
        clean = val.strip().replace("$", "").replace(",", "")
        if not clean:
            return default
        try:
            return Decimal(clean)
        except InvalidOperation:
            return default
    return default


def parse_json_rate(
    val: Any, default: Decimal | None = None
) -> Decimal | None:
    if val is None or val == "":
        return default
    if isinstance(val, str):
        clean = val.strip().replace("%", "")
        try:
            dec = Decimal(clean)
            if dec > Decimal("1.0"):
                return dec / Decimal("100")
            return dec
        except InvalidOperation:
            return default
    try:
        dec = Decimal(str(val))
        if dec > Decimal("1.0"):
            return dec / Decimal("100")
        return dec
    except (InvalidOperation, ValueError, TypeError):
        return default


def export_scenario_to_dict(scenario: ScenarioModel) -> dict[str, Any]:
    """Serialize ScenarioModel and its LoanOptionModels into a JSON-serializable structure."""
    options_data = []
    for opt in scenario.loan_options.all().order_by("created_at"):
        options_data.append(
            {
                "id": str(opt.id),
                "label": opt.label,
                "source_type": opt.source_type,
                "entered_on": opt.entered_on.isoformat()
                if opt.entered_on
                else None,
                "loan_amount": float(round(opt.loan_amount, 2))
                if opt.loan_amount is not None
                else None,
                "note_rate": float(round(opt.note_rate, 4))
                if opt.note_rate is not None
                else None,
                "apr": float(round(opt.apr, 4))
                if opt.apr is not None
                else None,
                "term_months": opt.term_months,
                "points_pct": float(round(opt.points_pct, 4))
                if opt.points_pct is not None
                else 0.0,
                "lender_credit": float(round(opt.lender_credit, 2))
                if opt.lender_credit is not None
                else 0.0,
                "lender_fees": float(round(opt.lender_fees, 2))
                if opt.lender_fees is not None
                else 0.0,
                "monthly_mi": float(round(opt.monthly_mi, 2))
                if opt.monthly_mi is not None
                else 0.0,
                "upfront_mi": float(round(opt.upfront_mi, 2))
                if opt.upfront_mi is not None
                else 0.0,
                "notes": opt.notes or "",
            }
        )

    return {
        "version": "1.0",
        "scenario": {
            "id": str(scenario.id),
            "name": scenario.name,
            "purpose": scenario.purpose,
            "property_value": float(round(scenario.property_value, 2))
            if scenario.property_value is not None
            else None,
            "loan_amount": float(round(scenario.loan_amount, 2)),
            "down_payment": float(round(scenario.down_payment, 2))
            if scenario.down_payment is not None
            else 0.0,
            "fico_band": scenario.fico_band,
            "occupancy": scenario.occupancy,
            "property_type": scenario.property_type,
            "state": scenario.state,
            "county_fips": scenario.county_fips or "",
            "program": scenario.program,
            "term_months": scenario.term_months,
            "expected_horizon_months": scenario.expected_horizon_months,
            "gross_monthly_income": float(round(scenario.gross_monthly_income, 2))
            if scenario.gross_monthly_income is not None
            else None,
            "recurring_monthly_debts": float(
                round(scenario.recurring_monthly_debts, 2)
            )
            if scenario.recurring_monthly_debts is not None
            else None,
            "estimated_property_tax_monthly": float(
                round(scenario.estimated_property_tax_monthly, 2)
            )
            if scenario.estimated_property_tax_monthly is not None
            else 0.0,
            "estimated_homeowners_insurance_monthly": float(
                round(scenario.estimated_homeowners_insurance_monthly, 2)
            )
            if scenario.estimated_homeowners_insurance_monthly is not None
            else 0.0,
            "estimated_hoa_monthly": float(
                round(scenario.estimated_hoa_monthly, 2)
            )
            if scenario.estimated_hoa_monthly is not None
            else 0.0,
            "annual_appreciation_pct": float(
                round(scenario.annual_appreciation_pct * Decimal("100"), 3)
            ),
            "marginal_tax_rate_pct": float(
                round(scenario.marginal_tax_rate_pct * Decimal("100"), 3)
            )
            if scenario.marginal_tax_rate_pct is not None
            else 0.0,
            "itemize_deductions": scenario.itemize_deductions,
            "filing_status": scenario.filing_status,
        },
        "loan_options": options_data,
    }


def import_or_update_scenario_from_dict(
    payload: dict[str, Any],
    scenario: ScenarioModel | None = None,
) -> ScenarioModel:
    """Parse JSON/dictionary structure and create or update a ScenarioModel with LoanOptions."""
    # Support nested {"scenario": {...}} or root dict
    sc_data = payload.get("scenario", payload)
    options_data = payload.get("loan_options", [])

    with transaction.atomic():
        if scenario is None:
            # Create new
            scenario = ScenarioModel()

        # Update scenario fields
        if "name" in sc_data and sc_data["name"]:
            scenario.name = str(sc_data["name"]).strip()
        elif not scenario.name:
            scenario.name = "Imported Scenario"

        if "purpose" in sc_data:
            scenario.purpose = str(sc_data["purpose"]).lower()
        if "property_value" in sc_data:
            scenario.property_value = parse_json_decimal(sc_data["property_value"])
        if "loan_amount" in sc_data:
            scenario.loan_amount = (
                parse_json_decimal(sc_data["loan_amount"])
                or scenario.loan_amount
                or Decimal("500000.00")
            )
        if "down_payment" in sc_data:
            scenario.down_payment = parse_json_decimal(
                sc_data["down_payment"], Decimal("0.00")
            )
        if "fico_band" in sc_data:
            scenario.fico_band = str(sc_data["fico_band"])
        if "occupancy" in sc_data:
            scenario.occupancy = str(sc_data["occupancy"]).lower()
        if "property_type" in sc_data:
            scenario.property_type = str(sc_data["property_type"]).lower()
        if "state" in sc_data:
            scenario.state = str(sc_data["state"]).upper()[:2]
        if "county_fips" in sc_data:
            scenario.county_fips = str(sc_data["county_fips"])
        if "program" in sc_data:
            scenario.program = str(sc_data["program"]).lower()
        if "term_months" in sc_data and sc_data["term_months"]:
            scenario.term_months = int(sc_data["term_months"])
        if "expected_horizon_months" in sc_data and sc_data["expected_horizon_months"]:
            scenario.expected_horizon_months = int(
                sc_data["expected_horizon_months"]
            )
        if "gross_monthly_income" in sc_data:
            scenario.gross_monthly_income = parse_json_decimal(
                sc_data["gross_monthly_income"]
            )
        if "recurring_monthly_debts" in sc_data:
            scenario.recurring_monthly_debts = parse_json_decimal(
                sc_data["recurring_monthly_debts"]
            )
        if "estimated_property_tax_monthly" in sc_data:
            scenario.estimated_property_tax_monthly = parse_json_decimal(
                sc_data["estimated_property_tax_monthly"], Decimal("0.00")
            )
        if "estimated_homeowners_insurance_monthly" in sc_data:
            scenario.estimated_homeowners_insurance_monthly = parse_json_decimal(
                sc_data["estimated_homeowners_insurance_monthly"],
                Decimal("0.00"),
            )
        if "estimated_hoa_monthly" in sc_data:
            scenario.estimated_hoa_monthly = parse_json_decimal(
                sc_data["estimated_hoa_monthly"], Decimal("0.00")
            )
        if "annual_appreciation_pct" in sc_data:
            scenario.annual_appreciation_pct = (
                parse_json_rate(sc_data["annual_appreciation_pct"])
                or Decimal("0.0300")
            )
        if "marginal_tax_rate_pct" in sc_data:
            scenario.marginal_tax_rate_pct = parse_json_rate(
                sc_data["marginal_tax_rate_pct"], Decimal("0.2400")
            )
        if "itemize_deductions" in sc_data:
            scenario.itemize_deductions = bool(sc_data["itemize_deductions"])
        if "filing_status" in sc_data:
            scenario.filing_status = str(sc_data["filing_status"]).lower()

        scenario.save()

        # Handle loan options if provided
        for opt_item in options_data:
            opt_id = opt_item.get("id")
            opt_model = None
            if opt_id:
                try:
                    opt_model = scenario.loan_options.get(id=opt_id)
                except (
                    LoanOptionModel.DoesNotExist,
                    ValueError,
                    TypeError,
                ):
                    opt_model = None

            if opt_model is None:
                opt_model = LoanOptionModel(scenario=scenario)

            if "label" in opt_item:
                opt_model.label = str(opt_item["label"]).strip()
            elif not opt_model.label:
                opt_model.label = "Loan Option"

            if "source_type" in opt_item:
                opt_model.source_type = str(opt_item["source_type"]).lower()
            if "entered_on" in opt_item and opt_item["entered_on"]:
                val = opt_item["entered_on"]
                if isinstance(val, str):
                    try:
                        opt_model.entered_on = datetime.fromisoformat(
                            val
                        ).date()
                    except ValueError:
                        opt_model.entered_on = date.today()
                elif isinstance(val, date):
                    opt_model.entered_on = val
            elif not opt_model.entered_on:
                opt_model.entered_on = date.today()

            if "loan_amount" in opt_item:
                opt_model.loan_amount = (
                    parse_json_decimal(opt_item["loan_amount"])
                    or scenario.loan_amount
                )
            elif not opt_model.loan_amount:
                opt_model.loan_amount = scenario.loan_amount

            if "note_rate" in opt_item:
                opt_model.note_rate = (
                    parse_json_rate(opt_item["note_rate"])
                    or Decimal("0.0650")
                )
            if "apr" in opt_item:
                opt_model.apr = parse_json_rate(opt_item["apr"])
            if "term_months" in opt_item and opt_item["term_months"]:
                opt_model.term_months = int(opt_item["term_months"])
            elif not opt_model.term_months:
                opt_model.term_months = scenario.term_months or 360

            if "points_pct" in opt_item:
                opt_model.points_pct = (
                    parse_json_rate(opt_item["points_pct"])
                    or Decimal("0.0000")
                )
            if "lender_credit" in opt_item:
                opt_model.lender_credit = parse_json_decimal(
                    opt_item["lender_credit"], Decimal("0.00")
                )
            if "lender_fees" in opt_item:
                opt_model.lender_fees = parse_json_decimal(
                    opt_item["lender_fees"], Decimal("0.00")
                )
            if "monthly_mi" in opt_item:
                opt_model.monthly_mi = parse_json_decimal(
                    opt_item["monthly_mi"], Decimal("0.00")
                )
            if "upfront_mi" in opt_item:
                opt_model.upfront_mi = parse_json_decimal(
                    opt_item["upfront_mi"], Decimal("0.00")
                )
            if "notes" in opt_item:
                opt_model.notes = str(opt_item["notes"])

            opt_model.save()

    return scenario



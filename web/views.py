import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.management import call_command
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import ScenarioInput
from core.money import parse_rate_pct
from core.screening import screen_all_programs
from web.forms import LoanOptionForm, ScenarioForm
from web.integrations.rateapi import (
    BudgetExhaustedError,
    RateApiAdapter,
    aggregate_product_term_structure,
    calculate_fred_vs_cu_spread,
)
from web.models import (
    BenchmarkPointModel,
    LoanOptionModel,
    RateApiCacheModel,
    RateApiSnapshotModel,
    ScenarioModel,
)
from web.services import (
    build_projected_costs_chart_data,
    compare_scenario,
    export_scenario_to_dict,
    import_or_update_scenario_from_dict,
)


def scenario_list(request: HttpRequest) -> HttpResponse:
    scenarios = ScenarioModel.objects.all().prefetch_related("loan_options")
    return render(request, "scenario_list.html", {"scenarios": scenarios})


def scenario_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ScenarioForm(request.POST)
        if form.is_valid():
            scenario = form.save()
            return redirect("web:scenario_compare", scenario_id=scenario.id)
    else:
        form = ScenarioForm()

    return render(
        request,
        "scenario_form.html",
        {
            "form": form,
            "is_create": True,
        },
    )


def scenario_import_json(request: HttpRequest) -> HttpResponse:
    error_msg = None
    initial_json = ""
    if request.method == "POST":
        raw_text = request.POST.get("json_payload", "").strip()
        uploaded_file = request.FILES.get("json_file")

        if uploaded_file:
            try:
                raw_text = uploaded_file.read().decode("utf-8")
            except Exception as e:
                error_msg = f"Failed to read uploaded JSON file: {e}"

        if not error_msg:
            if not raw_text:
                error_msg = "Please provide JSON text or upload a .json file."
            else:
                try:
                    payload = json.loads(raw_text)
                    scenario = import_or_update_scenario_from_dict(payload)
                    return redirect("web:scenario_compare", scenario_id=scenario.id)
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON syntax: {e}"
                    initial_json = raw_text
                except Exception as e:
                    error_msg = f"Failed to import scenario: {e}"
                    initial_json = raw_text

    return render(
        request,
        "scenario_import_json.html",
        {
            "error_msg": error_msg,
            "initial_json": initial_json,
        },
    )


def scenario_export_json(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    data = export_scenario_to_dict(scenario)
    json_str = json.dumps(data, indent=2)
    response = HttpResponse(json_str, content_type="application/json")
    if request.GET.get("download") == "1":
        clean_name = "".join(
            c for c in scenario.name if c.isalnum() or c in (" ", "_", "-")
        ).strip().replace(" ", "_")
        response["Content-Disposition"] = (
            f'attachment; filename="scenario_{clean_name or scenario.id}.json"'
        )
    return response


def scenario_edit_json(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    error_msg = None
    if request.method == "POST":
        raw_text = request.POST.get("json_payload", "").strip()
        if not raw_text:
            error_msg = "JSON content cannot be empty."
        else:
            try:
                payload = json.loads(raw_text)
                import_or_update_scenario_from_dict(payload, scenario=scenario)
                return redirect("web:scenario_compare", scenario_id=scenario.id)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON syntax: {e}"
            except Exception as e:
                error_msg = f"Failed to update scenario: {e}"
        current_json = raw_text
    else:
        current_json = json.dumps(export_scenario_to_dict(scenario), indent=2)

    return render(
        request,
        "scenario_edit_json.html",
        {
            "scenario": scenario,
            "current_json": current_json,
            "error_msg": error_msg,
        },
    )


def scenario_edit(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    if request.method == "POST":
        form = ScenarioForm(request.POST, instance=scenario)
        if form.is_valid():
            form.save()
            return redirect("web:scenario_compare", scenario_id=scenario.id)
    else:
        form = ScenarioForm(instance=scenario)

    return render(
        request,
        "scenario_form.html",
        {
            "form": form,
            "is_create": False,
            "scenario": scenario,
        },
    )


def scenario_delete(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    if request.method == "POST":
        scenario.delete()
        return redirect("web:scenario_list")
    return render(request, "scenario_confirm_delete.html", {"scenario": scenario})


@csrf_exempt
def scenario_screen_preview(request: HttpRequest) -> HttpResponse:
    data = request.POST if request.method == "POST" else request.GET

    def parse_dec(val: str | None) -> Decimal | None:
        if not val or not val.strip():
            return None
        try:
            return Decimal(val.strip().replace("$", "").replace(",", ""))
        except InvalidOperation:
            return None

    property_val = parse_dec(data.get("property_value")) or Decimal("0")
    loan_amt = parse_dec(data.get("loan_amount")) or Decimal("0")
    down_pmt = parse_dec(data.get("down_payment"))
    gross_inc = parse_dec(data.get("gross_monthly_income"))
    debts = parse_dec(data.get("recurring_monthly_debts"))
    fico = data.get("fico_band", "760+")
    program = data.get("program", "conventional")

    # Estimate rough initial housing payment for screening preview
    if loan_amt > Decimal("0"):
        est_pi = loan_amt * Decimal("0.006")  # approx 6.5% 30yr rate rule of thumb
    else:
        est_pi = Decimal("0")

    dummy_input = ScenarioInput(
        purpose="purchase",
        property_value=property_val,
        loan_amount=loan_amt,
        down_payment=down_pmt,
        fico_band=fico,
        occupancy="primary",
        property_type="single_family",
        state="CA",
        county_fips=None,
        program=program
        if program in ["conventional", "fha", "va", "usda"]
        else "conventional",  # type: ignore
        term_months=360,
        expected_horizon_months=84,
        gross_monthly_income=gross_inc,
        recurring_monthly_debts=debts,
    )

    screening_results = screen_all_programs(dummy_input, est_pi)

    # Calculate DTI % for display
    dti_display = None
    if gross_inc and gross_inc > 0:
        total_debt = est_pi + (debts or Decimal("0"))
        dti_display = round(float((total_debt / gross_inc) * 100), 1)

    ltv_display = None
    if property_val > 0 and loan_amt > 0:
        ltv_display = round(float((loan_amt / property_val) * 100), 1)

    return render(
        request,
        "partials/screening_result.html",
        {
            "screening_results": screening_results,
            "dti_display": dti_display,
            "ltv_display": ltv_display,
        },
    )


def scenario_compare(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(
        ScenarioModel.objects.prefetch_related("loan_options"), id=scenario_id
    )

    # Selected horizon in months (default to scenario's expected_horizon_months)
    horizon_param = request.GET.get("horizon")
    if horizon_param and horizon_param.isdigit():
        horizon_months = int(horizon_param)
    else:
        horizon_months = scenario.expected_horizon_months

    comparison = compare_scenario(scenario.id, horizon_months=horizon_months)

    # Build comparison view models
    options_data = []
    baseline_result = (
        comparison.option_results[0] if comparison.option_results else None
    )

    for opt_res in comparison.option_results:
        opt_model = scenario.loan_options.filter(id=opt_res.option_id).first()
        is_recommended = opt_res.option_id == comparison.recommended_option_id

        # Savings vs baseline
        savings_vs_base = None
        if baseline_result and baseline_result.option_id != opt_res.option_id:
            savings_vs_base = (
                baseline_result.financing_cost_at_horizon
                - opt_res.financing_cost_at_horizon
            )

        options_data.append(
            {
                "model": opt_model,
                "result": opt_res,
                "is_recommended": is_recommended,
                "savings_vs_baseline": savings_vs_base,
                "rate_pct": f"{opt_model.note_rate * 100:.3f}%" if opt_model else "",
                "apr_pct": f"{opt_model.apr * 100:.3f}%"
                if opt_model and opt_model.apr
                else None,
                "points_pct": f"{opt_model.points_pct * 100:.2f}%" if opt_model else "",
                "points_dollars": (opt_model.loan_amount * opt_model.points_pct)
                if opt_model
                else Decimal("0"),
            }
        )

    recommended_opt = None
    rec_savings_text = None
    if comparison.recommended_option_id:
        for item in options_data:
            if item["result"].option_id == comparison.recommended_option_id:
                recommended_opt = item
                break
        if (
            recommended_opt
            and baseline_result
            and baseline_result.option_id != comparison.recommended_option_id
        ):
            diff = (
                baseline_result.financing_cost_at_horizon
                - recommended_opt["result"].financing_cost_at_horizon
            )
            rec_savings_text = f"${diff:,.0f} lower estimated financing cost than {baseline_result.label}"

    context = {
        "scenario": scenario,
        "horizon_months": horizon_months,
        "horizon_years": horizon_months // 12,
        "comparison": comparison,
        "options_data": options_data,
        "recommended_opt": recommended_opt,
        "rec_savings_text": rec_savings_text,
    }

    if request.headers.get("HX-Request") and request.GET.get("partial") == "matrix":
        return render(request, "partials/compare_matrix.html", context)

    return render(request, "compare.html", context)


def scenario_projected_costs(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(
        ScenarioModel.objects.prefetch_related("loan_options"), id=scenario_id
    )

    horizon_param = request.GET.get("horizon")
    if horizon_param and horizon_param.isdigit():
        horizon_months = int(horizon_param)
    else:
        horizon_months = scenario.expected_horizon_months

    disc_rate_param = request.GET.get("discount_rate")
    discount_rate = None
    if disc_rate_param:
        try:
            discount_rate = Decimal(disc_rate_param) / Decimal("100")
        except InvalidOperation:
            discount_rate = None

    comparison = compare_scenario(
        scenario.id,
        horizon_months=horizon_months,
        discount_rate=discount_rate,
    )

    chart_data = build_projected_costs_chart_data(comparison)

    # Key metric calculations matching UI Mockup 1:
    # 1. Option B savings at horizon
    # 2. Points break-even month
    # 3. Monthly P&I difference
    savings_at_horizon = None
    pi_diff = None
    upfront_diff = None
    interest_diff = None
    mi_diff = None
    if len(comparison.option_results) >= 2:
        opt_a = comparison.option_results[0]
        opt_b = comparison.option_results[1]
        savings_at_horizon = (
            opt_a.financing_cost_at_horizon - opt_b.financing_cost_at_horizon
        )
        pi_diff = abs(opt_a.monthly_pi - opt_b.monthly_pi)
        upfront_diff = opt_b.net_upfront - opt_a.net_upfront
        interest_diff = (
            opt_b.cumulative_interest_at_horizon
            - opt_a.cumulative_interest_at_horizon
        )
        mi_diff = (
            opt_b.cumulative_mi_at_horizon - opt_a.cumulative_mi_at_horizon
        )

    # Build monthly cost breakdowns for all options
    monthly_tax = scenario.estimated_property_tax_monthly or Decimal("0")
    monthly_ins = scenario.estimated_homeowners_insurance_monthly or Decimal("0")
    monthly_hoa = scenario.estimated_hoa_monthly or Decimal("0")
    gross_income = scenario.gross_monthly_income or Decimal("0")
    debts = scenario.recurring_monthly_debts or Decimal("0")

    monthly_cost_options = []
    baseline_total = (
        comparison.option_results[0].total_piti_monthly
        if comparison.option_results
        else Decimal("0")
    )

    for idx, opt_res in enumerate(comparison.option_results):
        is_recommended = opt_res.option_id == comparison.recommended_option_id
        monthly_pi = opt_res.monthly_pi
        monthly_mi = opt_res.monthly_mi or Decimal("0")
        total_monthly = opt_res.total_piti_monthly

        pi_pct = (
            round(float((monthly_pi / total_monthly) * 100), 1)
            if total_monthly > 0
            else 0.0
        )
        tax_pct = (
            round(float((monthly_tax / total_monthly) * 100), 1)
            if total_monthly > 0
            else 0.0
        )
        ins_pct = (
            round(float((monthly_ins / total_monthly) * 100), 1)
            if total_monthly > 0
            else 0.0
        )
        mi_pct = (
            round(float((monthly_mi / total_monthly) * 100), 1)
            if total_monthly > 0
            else 0.0
        )
        hoa_pct = (
            round(float((monthly_hoa / total_monthly) * 100), 1)
            if total_monthly > 0
            else 0.0
        )

        front_end_dti = None
        back_end_dti = None
        if gross_income > 0:
            front_end_dti = round(float((total_monthly / gross_income) * 100), 1)
            back_end_dti = round(
                float(((total_monthly + debts) / gross_income) * 100), 1
            )

        monthly_diff_vs_baseline = (
            total_monthly - baseline_total if idx > 0 else Decimal("0")
        )

        monthly_cost_options.append(
            {
                "option_id": str(opt_res.option_id),
                "label": opt_res.label,
                "source_type": opt_res.source_type,
                "is_recommended": is_recommended,
                "rate_pct_display": opt_res.rate_pct_display,
                "apr_pct_display": opt_res.apr_pct_display,
                "monthly_pi": float(monthly_pi),
                "monthly_tax": float(monthly_tax),
                "monthly_ins": float(monthly_ins),
                "monthly_mi": float(monthly_mi),
                "monthly_hoa": float(monthly_hoa),
                "total_monthly": float(total_monthly),
                "pi_pct": pi_pct,
                "tax_pct": tax_pct,
                "ins_pct": ins_pct,
                "mi_pct": mi_pct,
                "hoa_pct": hoa_pct,
                "front_end_dti": front_end_dti,
                "back_end_dti": back_end_dti,
                "monthly_diff_vs_baseline": float(monthly_diff_vs_baseline),
            }
        )

    primary_monthly_cost = (
        monthly_cost_options[0] if monthly_cost_options else None
    )
    for mco in monthly_cost_options:
        if mco["is_recommended"]:
            primary_monthly_cost = mco
            break

    context = {
        "scenario": scenario,
        "horizon_months": horizon_months,
        "horizon_years": horizon_months // 12,
        "discount_rate_display": f"{discount_rate * 100:.1f}"
        if discount_rate
        else "4.0",
        "has_discount_rate": discount_rate is not None,
        "comparison": comparison,
        "chart_data_json": json.dumps(chart_data),
        "savings_at_horizon": savings_at_horizon,
        "pi_diff": pi_diff,
        "upfront_diff": upfront_diff,
        "interest_diff": interest_diff,
        "mi_diff": mi_diff,
        "break_even": comparison.break_even,
        "break_even_month": comparison.break_even.break_even_month
        if comparison.break_even
        else None,
        "break_even_explanation": comparison.break_even.break_even_explanation
        if comparison.break_even
        else "",
        "monthly_cost_options": monthly_cost_options,
        "monthly_cost_options_json": json.dumps(monthly_cost_options),
        "primary_monthly_cost": primary_monthly_cost,
    }

    if request.headers.get("HX-Request") and request.GET.get("partial") == "charts":
        return render(request, "partials/projected_costs_body.html", context)

    return render(request, "projected_costs.html", context)


def option_create(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    if request.method == "POST":
        form = LoanOptionForm(request.POST)
        if form.is_valid():
            opt = form.save(commit=False)
            opt.scenario = scenario
            opt.save()
            return redirect("web:scenario_compare", scenario_id=scenario.id)
    else:
        # Pre-fill loan amount and term from scenario
        form = LoanOptionForm(
            initial={
                "loan_amount": scenario.loan_amount,
                "term_months": scenario.term_months,
                "source_type": "manual",
            }
        )

    return render(
        request,
        "option_form.html",
        {
            "form": form,
            "scenario": scenario,
            "is_create": True,
        },
    )


def option_edit(
    request: HttpRequest, scenario_id: UUID, option_id: UUID
) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    option = get_object_or_404(LoanOptionModel, id=option_id, scenario=scenario)
    if request.method == "POST":
        form = LoanOptionForm(request.POST, instance=option)
        if form.is_valid():
            form.save()
            return redirect("web:scenario_compare", scenario_id=scenario.id)
    else:
        form = LoanOptionForm(instance=option)

    return render(
        request,
        "option_form.html",
        {
            "form": form,
            "scenario": scenario,
            "option": option,
            "is_create": False,
        },
    )


def option_delete(
    request: HttpRequest, scenario_id: UUID, option_id: UUID
) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    option = get_object_or_404(LoanOptionModel, id=option_id, scenario=scenario)
    if request.method == "POST":
        option.delete()
        return redirect("web:scenario_compare", scenario_id=scenario.id)
    return render(
        request,
        "option_confirm_delete.html",
        {
            "scenario": scenario,
            "option": option,
        },
    )


def aggregate_fred_series(
    points_30_dict: dict[Any, float], points_15_dict: dict[Any, float]
) -> dict[str, Any]:
    all_dates = sorted(set(points_30_dict.keys()) | set(points_15_dict.keys()))

    # 1. Weekly (Raw Observations)
    weekly_labels = [d.strftime("%Y-%m-%d") for d in all_dates]
    weekly_30 = [points_30_dict.get(d) for d in all_dates]
    weekly_15 = [points_15_dict.get(d) for d in all_dates]

    # 2. Monthly Averages (Smooth Trend)
    monthly_30_map: dict[str, list[float]] = {}
    monthly_15_map: dict[str, list[float]] = {}
    months_ordered: list[str] = []

    # 3. Quarterly Averages (Macro Trend)
    quarterly_30_map: dict[str, list[float]] = {}
    quarterly_15_map: dict[str, list[float]] = {}
    quarters_ordered: list[str] = []

    for d in all_dates:
        # Month key (e.g., "Aug 2021")
        m_key = d.strftime("%b %Y")
        if m_key not in monthly_30_map:
            monthly_30_map[m_key] = []
            monthly_15_map[m_key] = []
            months_ordered.append(m_key)
        if d in points_30_dict:
            monthly_30_map[m_key].append(points_30_dict[d])
        if d in points_15_dict:
            monthly_15_map[m_key].append(points_15_dict[d])

        # Quarter key (e.g., "Q3 2021")
        q_num = (d.month - 1) // 3 + 1
        q_key = f"Q{q_num} {d.year}"
        if q_key not in quarterly_30_map:
            quarterly_30_map[q_key] = []
            quarterly_15_map[q_key] = []
            quarters_ordered.append(q_key)
        if d in points_30_dict:
            quarterly_30_map[q_key].append(points_30_dict[d])
        if d in points_15_dict:
            quarterly_15_map[q_key].append(points_15_dict[d])

    monthly_30 = [
        round(sum(monthly_30_map[k]) / len(monthly_30_map[k]), 2)
        if monthly_30_map[k]
        else None
        for k in months_ordered
    ]
    monthly_15 = [
        round(sum(monthly_15_map[k]) / len(monthly_15_map[k]), 2)
        if monthly_15_map[k]
        else None
        for k in months_ordered
    ]

    quarterly_30 = [
        round(sum(quarterly_30_map[k]) / len(quarterly_30_map[k]), 2)
        if quarterly_30_map[k]
        else None
        for k in quarters_ordered
    ]
    quarterly_15 = [
        round(sum(quarterly_15_map[k]) / len(quarterly_15_map[k]), 2)
        if quarterly_15_map[k]
        else None
        for k in quarters_ordered
    ]

    return {
        "weekly": {
            "labels": weekly_labels,
            "rates_30": weekly_30,
            "rates_15": weekly_15,
        },
        "monthly": {
            "labels": months_ordered,
            "rates_30": monthly_30,
            "rates_15": monthly_15,
        },
        "quarterly": {
            "labels": quarters_ordered,
            "rates_30": quarterly_30,
            "rates_15": quarterly_15,
        },
    }


def rate_watch(request: HttpRequest) -> HttpResponse:
    force_refresh = request.GET.get("refresh") == "1"

    # If force refresh requested and FRED_API_KEY is available, update FRED benchmarks
    if force_refresh and getattr(settings, "FRED_API_KEY", ""):
        try:
            call_command("fetch_fred_benchmarks", years=5)
        except Exception:
            pass

    latest_30 = (
        BenchmarkPointModel.objects.filter(series="MORTGAGE30US")
        .order_by("-observed_on")
        .first()
    )
    latest_15 = (
        BenchmarkPointModel.objects.filter(series="MORTGAGE15US")
        .order_by("-observed_on")
        .first()
    )

    five_years_ago = timezone.now().date() - timedelta(days=365 * 5 + 30)

    # 1. Historical FRED Timeline (Spanning 5 full years)
    points_30_dict = {
        p.observed_on: float(p.value)
        for p in BenchmarkPointModel.objects.filter(
            series="MORTGAGE30US", observed_on__gte=five_years_ago
        )
    }
    points_15_dict = {
        p.observed_on: float(p.value)
        for p in BenchmarkPointModel.objects.filter(
            series="MORTGAGE15US", observed_on__gte=five_years_ago
        )
    }

    fred_granularity = aggregate_fred_series(points_30_dict, points_15_dict)
    all_dates = sorted(set(points_30_dict.keys()) | set(points_15_dict.keys()))
    chart_dates = [d.strftime("%Y-%m-%d") for d in all_dates]
    chart_30_vals = [points_30_dict.get(d) for d in all_dates]
    chart_15_vals = [points_15_dict.get(d) for d in all_dates]

    # 2. RateAPI Market Data (Product Curve & Credit Union Dispersion)
    adapter = RateApiAdapter()

    # Attempt to fetch/persist latest snapshots if none exist or force_refresh
    if force_refresh or not RateApiSnapshotModel.objects.exists():
        adapter.fetch_and_persist_market_rates(state="CA", force_refresh=force_refresh)

    product_curve = aggregate_product_term_structure()
    product_chart_data = {
        "labels": [p["label"] for p in product_curve],
        "rates": [p["avg_rate"] for p in product_curve],
        "aprs": [p["avg_apr"] for p in product_curve],
    }

    def _format_short_lender(lender: str, product_name: str, product_type: str) -> str:
        short_lender = (
            lender.replace("Federal Credit Union", "FCU")
            .replace("Credit Union", "CU")
            .replace("Community", "Comm.")
            .strip()
        )
        combined = f"{product_name or ''} {product_type or ''}".lower()
        if "30" in combined or "30-year" in combined:
            p_label = "30Y Fixed"
        elif "15" in combined or "15-year" in combined:
            p_label = "15Y Fixed"
        elif "10" in combined or "10-year" in combined:
            p_label = "10Y Fixed"
        elif "7/1" in combined or "7-1" in combined or "7 & 1" in combined:
            p_label = "7/1 ARM"
        elif "5/1" in combined or "5-1" in combined or "5 & 1" in combined:
            p_label = "5/1 ARM"
        elif "3/1" in combined or "3-1" in combined or "3 & 1" in combined:
            p_label = "3/1 ARM"
        elif "arm" in combined:
            p_label = "ARM"
        else:
            p_label = (product_name or product_type).replace("Conforming", "").replace("Rate", "").strip()

        return f"{short_lender} ({p_label})"

    all_lender_snapshots = list(RateApiSnapshotModel.objects.order_by("rate")[:100])
    dispersion_all_items = [
        {
            "lender": s.lender,
            "product_type": s.product_type,
            "product_name": s.product_name,
            "rate": float(s.rate),
            "apr": float(s.apr),
            "points": float(s.points),
            "label": _format_short_lender(s.lender, s.product_name, s.product_type),
            "full_name": f"{s.lender} — {s.product_name or s.product_type}",
            "eligibility_summary": s.eligibility_summary,
        }
        for s in all_lender_snapshots
    ]

    # Unique product types present in the snapshot database
    available_product_types = sorted(list({s.product_type for s in all_lender_snapshots if s.product_type}))

    initial_snapshots = all_lender_snapshots[:10]
    dispersion_chart_data = {
        "labels": [
            _format_short_lender(s.lender, s.product_name, s.product_type)
            for s in initial_snapshots
        ],
        "full_names": [
            f"{s.lender} — {s.product_name or s.product_type}"
            for s in initial_snapshots
        ],
        "rates": [float(s.rate) for s in initial_snapshots],
        "aprs": [float(s.apr) for s in initial_snapshots],
    }

    macro_spread = calculate_fred_vs_cu_spread()
    budget = adapter.get_budget_status()

    last_refresh = None
    is_stale = False
    if latest_30:
        last_refresh = latest_30.fetched_at
        if timezone.now() - latest_30.fetched_at > timedelta(days=14):
            is_stale = True

    context = {
        "latest_30": latest_30,
        "latest_15": latest_15,
        "chart_dates_json": json.dumps(chart_dates),
        "chart_30_json": json.dumps(chart_30_vals),
        "chart_15_json": json.dumps(chart_15_vals),
        "fred_granularity_json": json.dumps(fred_granularity),
        "product_chart_json": json.dumps(product_chart_data),
        "dispersion_chart_json": json.dumps(dispersion_chart_data),
        "dispersion_all_items_json": json.dumps(dispersion_all_items),
        "available_product_types": available_product_types,
        "lender_snapshots": all_lender_snapshots,
        "macro_spread": macro_spread,
        "budget": budget,
        "last_refresh": last_refresh,
        "is_stale": is_stale,
    }
    return render(request, "rate_watch.html", context)


def learn(request: HttpRequest) -> HttpResponse:
    return render(request, "learn.html")


def scenario_enrich_preview(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    force_refresh = request.GET.get("refresh") == "1"
    adapter = RateApiAdapter()

    # If refinance, check if there's an existing APR to compare against
    current_apr = None
    if scenario.purpose == "refinance":
        existing_options = scenario.loan_options.all()
        if existing_options.exists():
            valid_aprs = [opt.apr for opt in existing_options if opt.apr]
            if valid_aprs:
                current_apr = min(valid_aprs)

    county = getattr(scenario, "county_fips", None)

    try:
        result = adapter.fetch_decisions(
            state=scenario.state,
            amount=scenario.loan_amount,
            term_months=scenario.term_months,
            intent=scenario.purpose,
            county=county,
            current_apr=current_apr,
            force_refresh=force_refresh,
        )
        context = {
            "scenario": scenario,
            "offers": result.get("offers", []),
            "from_cache": result.get("from_cache", False),
            "cached_at": result.get("cached_at"),
            "budget": result.get("budget", {}),
            "warning": result.get("warning"),
        }
    except BudgetExhaustedError as e:
        context = {
            "scenario": scenario,
            "offers": [],
            "from_cache": False,
            "budget": adapter.get_budget_status(),
            "warning": str(e),
        }
    except Exception as e:
        context = {
            "scenario": scenario,
            "offers": [],
            "from_cache": False,
            "budget": adapter.get_budget_status(),
            "warning": f"Unable to reach RateAPI.dev: {e}",
        }

    return render(request, "partials/rateapi_offers_modal.html", context)


def scenario_import_rateapi_offer(
    request: HttpRequest, scenario_id: UUID
) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    if request.method == "POST":
        label = request.POST.get("label", "RateAPI Market Offer")
        institution_name = request.POST.get("institution_name", "")
        raw_rate = request.POST.get("note_rate", "0")
        raw_apr = request.POST.get("apr", "")
        raw_points = request.POST.get("points_pct", "0")
        raw_amount = request.POST.get("loan_amount", str(scenario.loan_amount))
        raw_term = request.POST.get("term_months", str(scenario.term_months))
        raw_conf = request.POST.get("confidence_score")

        try:
            note_rate = parse_rate_pct(raw_rate)
            apr = parse_rate_pct(raw_apr) if raw_apr else None
            points_pct = parse_rate_pct(raw_points)
            loan_amount = Decimal(raw_amount)
            term_months = int(raw_term)
            confidence_score = Decimal(raw_conf) if raw_conf else None
        except (InvalidOperation, ValueError):
            return redirect("web:scenario_compare", scenario_id=scenario.id)

        LoanOptionModel.objects.create(
            scenario=scenario,
            label=label,
            institution_name=institution_name,
            source_type="rate_api",
            note_rate=note_rate,
            apr=apr,
            points_pct=points_pct,
            loan_amount=loan_amount,
            term_months=term_months,
            confidence_score=confidence_score,
            lender_credit=Decimal("0.00"),
            lender_fees=Decimal("0.00"),
            notes=f"Imported from live market quote via RateAPI.dev for {institution_name}.",
        )

    return redirect("web:scenario_compare", scenario_id=scenario.id)


def scenario_seed_from_cache(request: HttpRequest, scenario_id: UUID) -> HttpResponse:
    scenario = get_object_or_404(ScenarioModel, id=scenario_id)
    if request.method == "POST":
        target_product = "30-year-fixed" if scenario.term_months >= 300 else "15-year-fixed"
        snapshots = list(
            RateApiSnapshotModel.objects.filter(
                state=scenario.state, product_type=target_product
            ).order_by("rate")[:3]
        )
        if not snapshots:
            snapshots = list(
                RateApiSnapshotModel.objects.filter(state=scenario.state).order_by("rate")[:3]
            )

        for snap in snapshots:
            parsed_rate = parse_rate_pct(snap.rate)
            exists = scenario.loan_options.filter(
                institution_name=snap.lender,
                note_rate=parsed_rate,
            ).exists()
            if not exists:
                raw_rate = parsed_rate
                raw_apr = parse_rate_pct(snap.apr) if snap.apr else None
                raw_points = parse_rate_pct(snap.points) if snap.points else Decimal("0.0000")
                LoanOptionModel.objects.create(
                    scenario=scenario,
                    label=f"{snap.lender} ({snap.product_name or target_product})",
                    institution_name=snap.lender,
                    source_type="rate_api",
                    entered_on=snap.observed_on,
                    loan_amount=scenario.loan_amount,
                    note_rate=raw_rate,
                    apr=raw_apr,
                    points_pct=raw_points,
                    term_months=scenario.term_months,
                    confidence_score=snap.confidence_score or Decimal("0.85"),
                    lender_credit=Decimal("0.00"),
                    lender_fees=Decimal("0.00"),
                    notes=snap.eligibility_summary
                    or f"Seeded from local RateAPI snapshot cache ({snap.product_name or target_product}).",
                )

    return redirect("web:scenario_compare", scenario_id=scenario.id)


def data_sources(request: HttpRequest) -> HttpResponse:
    adapter = RateApiAdapter()
    snapshots_qs = RateApiSnapshotModel.objects.all().order_by("rate")
    cached_queries = RateApiCacheModel.objects.all().order_by("-cached_at")

    all_snapshots = list(snapshots_qs)
    unique_lenders = sorted(list({s.lender for s in all_snapshots if s.lender}))
    unique_products = sorted(list({s.product_type for s in all_snapshots if s.product_type}))
    unique_states = sorted(list({s.state for s in all_snapshots if s.state}))

    snapshots_data = [
        {
            "id": s.id,
            "lender": s.lender,
            "product_type": s.product_type,
            "product_name": s.product_name or s.product_type,
            "loan_program": s.loan_program,
            "state": s.state,
            "rate": float(s.rate),
            "apr": float(s.apr) if s.apr else None,
            "points": float(s.points) if s.points else 0.0,
            "confidence_score": float(s.confidence_score) if s.confidence_score else 0.85,
            "confidence_category": "high" if (s.confidence_score and s.confidence_score >= 0.70) else "warning",
            "observed_on": s.observed_on.isoformat() if s.observed_on else None,
            "fetched_at": s.fetched_at.strftime("%Y-%m-%d %H:%M UTC") if s.fetched_at else None,
            "eligibility_summary": s.eligibility_summary or "Standard conforming eligibility",
        }
        for s in all_snapshots
    ]

    budget_status = adapter.get_budget_status()

    context = {
        "snapshots": all_snapshots,
        "snapshots_json": json.dumps(snapshots_data),
        "total_snapshots": len(all_snapshots),
        "unique_lenders_count": len(unique_lenders),
        "unique_lenders": unique_lenders,
        "unique_products": unique_products,
        "unique_states": unique_states,
        "cached_queries": cached_queries,
        "cached_queries_count": cached_queries.count(),
        "budget": budget_status,
        "cache_ttl_days": adapter.cache_ttl_days,
        "default_state": adapter.default_state,
        "default_county": adapter.default_county,
    }
    return render(request, "data_sources.html", context)



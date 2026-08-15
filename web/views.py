import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import ScenarioInput
from core.screening import screen_all_programs
from web.forms import LoanOptionForm, ScenarioForm
from web.models import BenchmarkPointModel, LoanOptionModel, ScenarioModel
from web.services import (
    build_projected_costs_chart_data,
    compare_scenario,
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
            "scenario": None,
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
    if len(comparison.option_results) >= 2:
        opt_a = comparison.option_results[0]
        opt_b = comparison.option_results[1]
        savings_at_horizon = (
            opt_a.financing_cost_at_horizon - opt_b.financing_cost_at_horizon
        )
        pi_diff = abs(opt_a.monthly_pi - opt_b.monthly_pi)

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
        "break_even_month": comparison.break_even.break_even_month
        if comparison.break_even
        else None,
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


def rate_watch(request: HttpRequest) -> HttpResponse:
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

    points_30 = list(
        BenchmarkPointModel.objects.filter(series="MORTGAGE30US").order_by(
            "observed_on"
        )[:52]
    )
    points_15 = list(
        BenchmarkPointModel.objects.filter(series="MORTGAGE15US").order_by(
            "observed_on"
        )[:52]
    )

    chart_dates = [p.observed_on.strftime("%Y-%m-%d") for p in points_30]
    chart_30_vals = [float(p.value) for p in points_30]
    chart_15_vals = [float(p.value) for p in points_15]

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
        "last_refresh": last_refresh,
        "is_stale": is_stale,
    }
    return render(request, "rate_watch.html", context)


def learn(request: HttpRequest) -> HttpResponse:
    return render(request, "learn.html")

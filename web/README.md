# Web Application Layer (`web/`) — Developer Guide

The `web/` package provides the Django persistence layer, HTML templates, HTMX-driven reactive endpoints, and Chart.js serialization for Mortgage Compass.

---

## Directory Index

```
/Users/alejandrodiaz/Documents/projects/loan/web/
├── [apps.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/apps.py)
│   └── Django AppConfig registration for the web application.
├── [models.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py)
│   └── Django ORM models: [`ScenarioModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L9) (home price, down payment, income/debt context), [`LoanOptionModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L42) (rate, APR, points, confidence metadata), and [`BenchmarkPointModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L106) (historical FRED benchmark series).
├── [forms.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py)
│   └── Django ModelForms: [`ScenarioForm`](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py#L6) and [`LoanOptionForm`](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py#L64) with decimal percentage-to-ratio conversions.
├── [services.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py)
│   └── Domain boundary converters ([`orm_to_scenario_input()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L11), [`orm_to_loan_option_input()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L27)) and Chart.js precomputed serializer ([`build_projected_costs_chart_data()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L65)).
├── [urls.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/urls.py)
│   └── URL routing definitions for scenario management, HTMX live screening, matrix comparisons, projected costs, option CRUD, rate watch, and methodology.
├── [views.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py)
│   └── Request handlers including [`scenario_compare()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L114), [`scenario_projected_costs()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L182), and [`scenario_screen_preview()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L76).
├── management/commands/
│   ├── [fetch_fred_benchmarks.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/fetch_fred_benchmarks.py)
│   │   └── CLI command querying the Federal Reserve Economic Data (FRED) API for weekly 30-year (`MORTGAGE30US`) and 15-year (`MORTGAGE15US`) rate series.
│   └── [seed_demo_data.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/seed_demo_data.py)
│       └── Populates the database with the Section 11 worked fixture ($400k loan), Mountain View purchase scenario, and 52 weeks of benchmark data.
├── static/
│   ├── css/[styles.css](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/css/styles.css)
│   │   └── Custom design system with glassmorphism, responsive grid layouts, and color tokens matching the specification.
│   └── js/
│       ├── [htmx.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/htmx.min.js)
│       │   └── Local vendor bundle powering real-time HTMX reactive form updates without full-page reloads.
│       └── [chart.umd.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/chart.umd.min.js)
│           └── Local vendor bundle rendering cumulative financing cost, payment composition, and loan balance curves.
└── templates/
    ├── [base.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/base.html)
    │   └── Master HTML skeleton with navigation bar, responsive drawer, and methodology footer.
    ├── [compare.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/compare.html)
    │   └── Option comparison matrix page with hold period dropdown.
    ├── [projected_costs.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/projected_costs.html)
    │   └── Interactive holding horizon slider, discount rate input, KPI summary cards, and 3 Chart.js graphs.
    ├── [scenario_form.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_form.html)
    │   └── Scenario creation form with live HTMX reactive preview container.
    ├── [scenario_list.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_list.html)
    │   └── Main dashboard displaying scenario cards, quick stats, and benchmark widget.
    ├── [option_form.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/option_form.html)
    │   └── Loan Option entry form with confidence source selection (Loan Estimate vs advertised quote).
    ├── [option_confirm_delete.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/option_confirm_delete.html)
    │   └── Confirmation modal for deleting a loan option.
    ├── [scenario_confirm_delete.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_confirm_delete.html)
    │   └── Confirmation modal for deleting an entire scenario.
    ├── [rate_watch.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/rate_watch.html)
    │   └── Historical rate tracker displaying 52-week FRED benchmark trends.
    ├── [learn.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/learn.html)
    │   └── Methodology reference on mortgage math, discount points, APR limitations, and MI formulas.
    └── partials/
        ├── [compare_matrix.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/compare_matrix.html)
        │   └── Partial template rendering the side-by-side comparison table and recommendation banner.
        └── [screening_result.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/screening_result.html)
            └── Partial template rendering HTMX-updated LTV, DTI, and program sanity badges.
```

---

## Architectural Conventions

1. **Precomputed Chart Serialization**: Chart.js executes zero financial calculations in the browser. All financial series are precomputed on the server in [`build_projected_costs_chart_data()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L65) and injected as ready-to-render JSON data.
2. **Explicit Decimal Storage**: Rate percentages (e.g. `5.875%`) are stored in `LoanOptionModel.note_rate` with `max_digits=8, decimal_places=6` (`0.058750`) to avoid rounding distortions.

---

## Running Web Tests

```bash
# Run web model and view integration tests
.venv/bin/pytest tests/unit/test_models.py tests/unit/test_services.py tests/unit/test_views.py tests/unit/test_options_views.py -v

# Run Selenium E2E interaction tests
.venv/bin/pytest tests/e2e/ -v
```

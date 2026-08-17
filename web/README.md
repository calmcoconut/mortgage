# Web Application Layer (`web/`) — Developer Guide

The `web/` package provides the Django persistence layer, HTML templates, HTMX-driven reactive endpoints, RateAPI live market offer integration, and Chart.js serialization for Mortgage Compass.

---

## Directory Index

```
/Users/alejandrodiaz/Documents/projects/loan/web/
├── [apps.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/apps.py)
│   └── Django AppConfig registration for the web application.
├── [models.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py)
│   └── Django ORM models: [`ScenarioModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L8), [`LoanOptionModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L126), [`BenchmarkPointModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L179), [`RateApiCacheModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L195), [`RateApiBudgetModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L214), and [`RateApiSnapshotModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L228).
├── [forms.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py)
│   └── Django ModelForms: [`ScenarioForm`](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py#L31) and [`LoanOptionForm`](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py#L286) with decimal percentage-to-ratio conversions and live currency inputs.
├── [services.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py)
│   └── Domain boundary converters ([`scenario_to_input()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L19), [`loan_option_to_input()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L46)), Chart.js precomputed serializer ([`build_projected_costs_chart_data()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L140)), and JSON utilities ([`export_scenario_to_dict()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L283), [`import_or_update_scenario_from_dict()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L383)).
├── integrations/
│   └── [rateapi.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/integrations/rateapi.py)
│       └── RateAPI.dev adapter with $25k amount-bucketed 24-hour caching, 18-call monthly budget guard, and confidence anomaly filtering.
├── [urls.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/urls.py)
│   └── URL routing definitions for scenario management, JSON import/export/edit, HTMX live screening, matrix comparisons, projected costs, option CRUD, RateAPI previews, rate watch, and methodology.
├── [views.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py)
│   └── Request handlers including [`scenario_compare()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L244), [`scenario_projected_costs()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L327), [`scenario_screen_preview()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L177), [`scenario_import_json()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L63), [`scenario_edit_json()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L116), [`scenario_enrich_preview()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L816), [`scenario_import_rateapi_offer()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L870), [`scenario_seed_from_cache()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L913), and [`data_sources()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L958).
├── management/commands/
│   ├── [fetch_fred_benchmarks.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/fetch_fred_benchmarks.py)
│   │   └── CLI command querying the Federal Reserve Economic Data (FRED) API for 5 years of weekly 30-year (`MORTGAGE30US`) and 15-year (`MORTGAGE15US`) rate series.
│   ├── [fetch_market_rates.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/fetch_market_rates.py)
│   │   └── CLI command batch-querying RateAPI.dev for live credit union quotes across 30Y Fixed, 15Y Fixed, 10Y Fixed, 7/1 ARM, and 5/1 ARM products into local durable storage.
│   └── [seed_demo_data.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/seed_demo_data.py)
│       └── Populates the database with the Section 11 worked fixture ($400k loan), Mountain View purchase scenario, 5 years of FRED benchmarks, and RateAPI market snapshots.
├── static/
│   ├── css/[styles.css](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/css/styles.css)
│   │   └── Custom design system with glassmorphism, responsive grid layouts, and color tokens matching the specification.
│   └── js/
│       ├── [htmx.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/htmx.min.js)
│       │   └── Local vendor bundle powering real-time HTMX reactive form updates without full-page reloads.
│       ├── [chart.umd.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/chart.umd.min.js)
│       │   └── Local vendor bundle rendering cumulative financing cost, payment composition, and loan balance curves.
│       ├── [chartjs-plugin-zoom.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/chartjs-plugin-zoom.min.js)
│       │   └── Local vendor bundle powering interactive wheel zoom and pan on FRED historical benchmark timeline.
│       └── [hammer.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/hammer.min.js)
│           └── Local vendor bundle for touch and pinch gesture detection.
└── templates/
    ├── [base.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/base.html)
    │   └── Master HTML skeleton with navigation bar, responsive drawer, and methodology footer.
    ├── [compare.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/compare.html)
    │   └── Option comparison matrix page with hold period dropdown, JSON action buttons, and Live Market Offers modal launcher.
    ├── [data_sources.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/data_sources.html)
    │   └── Raw data inventory and cache dump with live text search, product filters, sortable column headers, CSV/JSON export, and decision query payload inspection.
    ├── [projected_costs.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/projected_costs.html)
    │   └── Interactive holding horizon slider, discount rate input, KPI summary cards, Estimated Monthly Cost / PITI breakdown widget, projection metric mode switcher, and 3 Chart.js graphs.
    ├── [scenario_form.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_form.html)
    │   └── Scenario creation form with live HTMX reactive preview container, escrow fields, and appreciation/tax settings.
    ├── [scenario_import_json.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_import_json.html)
    │   └── Drag-and-drop file upload and interactive JSON editor for importing complete scenario and loan option payloads.
    ├── [scenario_edit_json.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_edit_json.html)
    │   └── Direct in-browser JSON editor for existing scenarios with format prettifier and 1-click clipboard copy.
    ├── [scenario_list.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_list.html)
    │   └── Main dashboard displaying scenario cards, quick stats, Import JSON button, and benchmark widget.
    ├── [option_form.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/option_form.html)
    │   └── Loan Option entry form with confidence source selection (Loan Estimate vs advertised quote).
    ├── [option_confirm_delete.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/option_confirm_delete.html)
    │   └── Confirmation modal for deleting a loan option.
    ├── [scenario_confirm_delete.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_confirm_delete.html)
    │   └── Confirmation modal for deleting an entire scenario.
    ├── [rate_watch.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/rate_watch.html)
    │   └── Historical and live market intelligence page with 5-year FRED trends, RateAPI product yield curves, and credit union dispersion.
    ├── [learn.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/learn.html)
    │   └── Methodology reference on mortgage math, discount points, APR limitations, and MI formulas.
    └── partials/
        ├── [compare_matrix.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/compare_matrix.html)
        │   └── Partial template rendering the side-by-side comparison table and recommendation banner.
        ├── [screening_result.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/screening_result.html)
        │   └── Partial template rendering HTMX-updated LTV, DTI, and program sanity badges.
        └── [rateapi_offers_modal.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/rateapi_offers_modal.html)
            └── Partial template rendering live market credit union quotes drawer with 1-click import.
```

---

## Architectural Conventions

1. **Precomputed Chart Serialization**: Chart.js executes zero financial calculations in the browser. All financial series are precomputed on the server in [`build_projected_costs_chart_data()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L140) and injected as ready-to-render JSON data.
2. **Explicit Decimal Storage**: Rate percentages (e.g. `5.875%`) are stored in `LoanOptionModel.note_rate` with `max_digits=8, decimal_places=6` (`0.058750`) to avoid rounding distortions.

---

## Running Web Tests

```bash
# Run web unit and view integration tests
.venv/bin/pytest tests/unit/test_models.py tests/unit/test_services.py tests/unit/test_views.py tests/unit/test_options_views.py tests/unit/test_rate_watch_view.py tests/unit/test_rateapi_views.py tests/unit/test_rateapi_adapter.py tests/unit/test_rateapi_market_rates.py -v

# Run Selenium E2E interaction tests
.venv/bin/pytest tests/e2e/ -v
```

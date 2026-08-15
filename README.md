# Mortgage Compass (Personal Use) — Developer Onboarding & Architecture Guide

Welcome to **Mortgage Compass**! This guide provides an architectural overview, file-by-file index, testing methodology, and local development setup for developers contributing to the codebase.

---

## 1. Architectural Overview

Mortgage Compass is designed with a strict separation between domain mathematics and web infrastructure:

```
┌───────────────────────────────────────────────────────────────────┐
│                           Web Layer                               │
│  Django Views & Templates  •  HTMX Reactive UI  •  Chart.js       │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ (Converts ORM Models to Frozen Dataclasses)
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Services Boundary Layer                      │
│                  web/services.py (Pure Converters)                │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ (No Django Dependencies)
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Pure Math Core (core/)                       │
│  Decimal Money Quantization  •  Amortization  •  Financing Costs  │
│  Points Break-Even  •  MI Fees  •  Conservative AUS Screening     │
└───────────────────────────────────────────────────────────────────┘
```

1. **Pure Math Core (`core/`)**: Completely decoupled from Django, databases, and frameworks. Uses immutable frozen dataclasses and Python's `Decimal` with cent quantization (`ROUND_HALF_UP`) to ensure mathematical precision without rounding drift.
2. **Persistence & Presentation (`web/`, `mortgage_compass/`)**: Django 6 + SQLite WAL, lightweight HTMX reactivity, server-rendered semantic HTML, and precomputed Chart.js serialization.
3. **Automated Verification (`tests/`)**: Four distinct testing tiers (Golden fixtures, Hypothesis property testing, Unit tests, and Headless Selenium WebDriver E2E interaction tests).

---

## 2. Codebase Directory Index

```
/Users/alejandrodiaz/Documents/projects/loan/
├── compose.yaml
│   └── Multi-container definition for Unraid / Docker Compose self-hosting.
├── Dockerfile
│   └── Lightweight container image configuration with Gunicorn WSGI.
├── manage.py
│   └── Django command-line execution utility.
├── pyproject.toml
│   └── Project metadata and Ruff linter/formatter configuration.
├── pytest.ini
│   └── Pytest configuration with test paths, Django settings, and markers.
├── requirements.txt
│   └── Locked production and testing dependencies.
├── core/
│   ├── [__init__.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/__init__.py)
│   │   └── Package marker for the pure math core module.
│   ├── [models.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py)
│   │   └── Frozen dataclasses defining [`ScenarioInput`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L22), [`LoanOptionInput`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L39), [`AmortizationRow`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L58), and [`ComparisonResult`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L79).
│   ├── [money.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/money.py)
│   │   └── Currency quantization helper [`money()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/money.py#L8) enforcing `ROUND_HALF_UP` to cents and rejecting raw floats.
│   ├── [amortization.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py)
│   │   └── Monthly payment calculator [`calculate_monthly_pi()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py#L7) and full schedule generator [`calculate_amortization()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py#L23) with final-payment balance reconciliation.
│   ├── [financing_cost.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py)
│   │   └── Holding horizon cost engine [`calculate_option_result()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py#L11), points break-even analyzer [`calculate_break_even()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py#L80), and option comparator [`compare_options()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py#L125).
│   ├── [mi_fees.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/mi_fees.py)
│   │   └── Fee estimators for Conventional PMI, FHA upfront/annual MIP, VA funding fee, and USDA guarantee fees.
│   └── [screening.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/screening.py)
│       └── Conservative rule-based screening engine [`screen_all_programs()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/screening.py#L80) checking LTV and DTI against program limits.
├── mortgage_compass/
│   ├── [__init__.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/__init__.py)
│   │   └── Package marker for Django project configuration.
│   ├── [asgi.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/asgi.py)
│   │   └── ASGI entry point for asynchronous deployments.
│   ├── [settings.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/settings.py)
│   │   └── Django settings configured with SQLite WAL, humanize, static asset routing, and template paths.
│   ├── [urls.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/urls.py)
│   │   └── Root URL routing delegating to the web application.
│   └── [wsgi.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/wsgi.py)
│       └── WSGI entry point for Gunicorn web server.
├── web/
│   ├── [apps.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/apps.py)
│   │   └── Django application configuration for the web UI.
│   ├── [forms.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py)
│   │   └── Django forms [`ScenarioForm`](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py#L6) and [`LoanOptionForm`](file:///Users/alejandrodiaz/Documents/projects/loan/web/forms.py#L64) with decimal percentage conversions.
│   ├── [models.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py)
│   │   └── SQLite persistence models [`ScenarioModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L9), [`LoanOptionModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L42), and [`BenchmarkPointModel`](file:///Users/alejandrodiaz/Documents/projects/loan/web/models.py#L106).
│   ├── [services.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py)
│   │   └── Domain boundary converters [`orm_to_scenario_input()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L11), [`orm_to_loan_option_input()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L27), and Chart.js serializer [`build_projected_costs_chart_data()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/services.py#L65).
│   ├── [urls.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/urls.py)
│   │   └── URL dispatch definitions for scenario management, HTMX previews, comparisons, projected costs, and rate watch.
│   ├── [views.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py)
│   │   └── View controllers including [`scenario_compare()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L114), [`scenario_projected_costs()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L182), and [`scenario_screen_preview()`](file:///Users/alejandrodiaz/Documents/projects/loan/web/views.py#L76).
│   ├── management/commands/
│   │   ├── [fetch_fred_benchmarks.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/fetch_fred_benchmarks.py)
│   │   │   └── CLI command fetching weekly Freddie Mac 30Y and 15Y benchmark rates from the FRED API.
│   │   └── [seed_demo_data.py](file:///Users/alejandrodiaz/Documents/projects/loan/web/management/commands/seed_demo_data.py)
│   │       └── Seeds Section 11 worked fixture ($400k loan), Mountain View scenario, and historical benchmark points.
│   ├── static/
│   │   ├── css/[styles.css](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/css/styles.css)
│   │   │   └── Polished responsive styles adhering to the design specification and mockups.
│   │   └── js/
│   │       ├── [htmx.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/htmx.min.js)
│   │       │   └── Local vendor bundle for reactive UI interactions.
│   │       └── [chart.umd.min.js](file:///Users/alejandrodiaz/Documents/projects/loan/web/static/js/chart.umd.min.js)
│   │           └── Local vendor bundle for Chart.js rendering.
│   └── templates/
│       ├── [base.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/base.html)
│       │   └── Base layout with global navigation, mobile responsiveness, and footer disclaimer.
│       ├── [compare.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/compare.html)
│       │   └── Scenario option comparison matrix workspace with hold period selector.
│       ├── [projected_costs.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/projected_costs.html)
│       │   └── Interactive holding horizon slider, discount sensitivity, KPI summary cards, and 3 financial charts.
│       ├── [scenario_form.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_form.html)
│       │   └── Scenario creation form with real-time HTMX program screening preview.
│       ├── [scenario_list.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/scenario_list.html)
│       │   └── Dashboard listing all saved scenarios and benchmark market context.
│       ├── [option_form.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/option_form.html)
│       │   └── Loan Option transcription and editing form.
│       ├── [rate_watch.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/rate_watch.html)
│       │   └── Historical benchmark tracking page with FRED rate charts.
│       ├── [learn.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/learn.html)
│       │   └── In-app documentation and mortgage methodology guide.
│       └── partials/
│           ├── [compare_matrix.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/compare_matrix.html)
│           │   └── Partial template for matrix columns, recommendation banners, and cost savings.
│           └── [screening_result.html](file:///Users/alejandrodiaz/Documents/projects/loan/web/templates/partials/screening_result.html)
│               └── Partial template for HTMX-rendered LTV, DTI, and program sanity badges.
└── tests/
    ├── [conftest.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/conftest.py)
    │   └── Pytest root fixtures and Chrome WebDriver options.
    ├── e2e/
    │   ├── [test_ui_scenario_screening.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_scenario_screening.py)
    │   │   └── Selenium test for scenario creation, live HTMX reactive previews, and screening tags.
    │   ├── [test_ui_compare_matrix.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_compare_matrix.py)
    │   │   └── Selenium test for the compare workspace, recommendation banners, and horizon dropdown switches.
    │   ├── [test_ui_projected_costs.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_projected_costs.py)
    │   │   └── Selenium test for KPI summary cards, Chart.js canvas elements, and discount rate sensitivity.
    │   └── [test_ui_option_crud.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_option_crud.py)
    │       └── Selenium test for adding, editing, and deleting loan options.
    ├── golden/
    │   ├── [test_amortization.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/golden/test_amortization.py)
    │   │   └── Golden tests verifying zero-balance schedule reconciliation over 12 and 360 months.
    │   └── [test_worked_fixture.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/golden/test_worked_fixture.py)
    │       └── Golden fixture verifying Section 11 numbers ($400k loan, Option A vs Option B, month 48 break-even).
    ├── property/
    │   └── [test_amortization_properties.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/property/test_amortization_properties.py)
    │       └── Hypothesis property tests asserting balance non-negativity and interest monotonicity.
    └── unit/
        ├── [test_money.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_money.py)
        │   └── Unit tests for cent quantization and float rejection.
        ├── [test_screening.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_screening.py)
        │   └── Unit tests for conservative Conventional, FHA, VA, and USDA screening logic.
        ├── [test_mi_fees.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_mi_fees.py)
        │   └── Unit tests for PMI, FHA MIP, VA funding fee, and USDA fee formulas.
        ├── [test_models.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_models.py)
        │   └── Unit tests for Django ORM model relationships and property helpers.
        ├── [test_services.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_services.py)
        │   └── Unit tests for ORM-to-Core translation and Chart.js payload construction.
        ├── [test_views.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_views.py)
        │   └── Unit tests for scenario HTTP endpoints and HTMX screening responses.
        ├── [test_options_views.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_options_views.py)
        │   └── Unit tests for loan option creation, editing, and deletion views.
        └── [test_fred_command.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_fred_command.py)
            └── Unit tests for FRED API benchmark fetching with mock responses and error handling.
```

---

## 3. Testing Setup & Categories

Mortgage Compass is built using Test-Driven Development (TDD) with 34 automated tests across four distinct tiers:

### A. Run All Tests
```bash
.venv/bin/pytest -v
```

### B. Pure Mathematical Core & Unit Tests (Offline / Instant)
Runs in `< 0.5s` without launching a browser or external APIs:
```bash
# Run unit tests
.venv/bin/pytest tests/unit/ -v

# Run golden fixture verification (Section 11 worked example)
.venv/bin/pytest tests/golden/ -v

# Run Hypothesis property-based fuzz tests
.venv/bin/pytest tests/property/ -v
```

### C. Selenium Browser Interaction E2E Tests
Launches headless Chrome using Django's `StaticLiveServerTestCase` to test real DOM events, HTMX partial rendering, and Chart.js:
```bash
.venv/bin/pytest tests/e2e/ -v
```

### D. Linting and Formatting (Ruff)
```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

---

## 4. Local Development Setup

### Prerequisites
- Python 3.13+
- Google Chrome & Chromedriver (for Selenium tests)

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Migration & Demo Data Seeding
```bash
python manage.py migrate
python manage.py seed_demo_data
```

### 3. Start Development Server
```bash
python manage.py runserver 0.0.0.0:8080
```
Open your browser at `http://localhost:8080/`.

---

## 5. Deployment (Self-Hosted / Unraid)

### Docker Compose
```bash
docker compose up -d --build
```

The container starts Gunicorn bound to port `8080` with persistent SQLite storage mounted at `/app/db.sqlite3`.

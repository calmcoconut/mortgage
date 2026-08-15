# Automated Test Suite (`tests/`) — Developer Guide

The `tests/` directory contains 34 automated tests across 4 testing tiers, providing 100% verification for the pure math core, Django ORM services, and browser interaction workflows.

---

## Directory Index

```
/Users/alejandrodiaz/Documents/projects/loan/tests/
├── [conftest.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/conftest.py)
│   └── Pytest root fixtures configuring headless Chrome WebDriver options and test database setup.
├── e2e/
│   ├── [test_ui_scenario_screening.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_scenario_screening.py)
│   │   └── Selenium test verifying scenario form submission, real-time HTMX LTV/DTI updates, and conservative AUS screening badges.
│   ├── [test_ui_compare_matrix.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_compare_matrix.py)
│   │   └── Selenium test verifying the Section 11 worked fixture ($400k loan), recommendation banners, and hold period switches (5yr, 7yr, 30yr).
│   ├── [test_ui_projected_costs.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_projected_costs.py)
│   │   └── Selenium test verifying KPI cards, Chart.js canvas elements (`#cumulativeCostChart`, `#paymentCompositionChart`, `#loanBalanceChart`), and discount rate sensitivity.
│   └── [test_ui_option_crud.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/e2e/test_ui_option_crud.py)
│       └── Selenium test verifying the complete Loan Option lifecycle (transcription, editing note rate, live matrix updates, and deletion).
├── golden/
│   ├── [test_amortization.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/golden/test_amortization.py)
│   │   └── Golden tests verifying exact zero-balance reconciliation over 12-month, 360-month, and 0% interest loan schedules.
│   └── [test_worked_fixture.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/golden/test_worked_fixture.py)
│       └── Golden fixture verifying Section 11 numbers: Option A ($2,528.27/mo) vs Option B ($2,398.20/mo + 2 pts), Month 48 break-even, and $6,033 7-year savings.
├── property/
│   └── [test_amortization_properties.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/property/test_amortization_properties.py)
│       └── Hypothesis property tests asserting non-negativity of balances and monotonicity of total interest with respect to note rate.
└── unit/
    ├── [test_money.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_money.py)
    │   └── Unit tests for cent quantization, `ROUND_HALF_UP` behavior, and float rejection.
    ├── [test_screening.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_screening.py)
    │   └── Unit tests for Conventional, FHA, VA, and USDA screening rules and missing-data handling.
    ├── [test_mi_fees.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_mi_fees.py)
    │   └── Unit tests for PMI, FHA MIP, VA funding fee, and USDA guarantee fee estimation formulas.
    ├── [test_models.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_models.py)
    │   └── Unit tests for Django ORM model creation, cascade deletes, and property helpers.
    ├── [test_services.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_services.py)
    │   └── Unit tests for ORM-to-Core translation and Chart.js precomputed dataset generation.
    ├── [test_views.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_views.py)
    │   └── Unit tests for scenario HTTP views and HTMX screening partial responses.
    ├── [test_options_views.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_options_views.py)
    │   └── Unit tests for loan option form validation, creation, editing, and deletion views.
    └── [test_fred_command.py](file:///Users/alejandrodiaz/Documents/projects/loan/tests/unit/test_fred_command.py)
        └── Unit tests for FRED API benchmark fetching with mock responses and network error handling.
```

---

## Test Execution Commands

### 1. Run Complete Suite (34 Tests in ~10.9s)
```bash
.venv/bin/pytest -v
```

### 2. Run Fast Offline Tiers (Instant / No Browser)
```bash
# Unit tests
.venv/bin/pytest tests/unit/ -v

# Golden fixture tests
.venv/bin/pytest tests/golden/ -v

# Hypothesis property-based fuzz tests
.venv/bin/pytest tests/property/ -v
```

### 3. Run Selenium Headless Browser E2E Tests
```bash
.venv/bin/pytest tests/e2e/ -v
```

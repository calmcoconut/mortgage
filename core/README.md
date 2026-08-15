# Pure Mathematical Core (`core/`) — Developer Guide

The `core/` package encapsulates all financial, amortization, holding period, and program screening algorithms. It has **zero external framework dependencies** (no Django, database, or network imports) and uses Python's standard `decimal.Decimal` with immutable dataclasses to guarantee complete precision without floating-point drift.

---

## Directory Index

```
/Users/alejandrodiaz/Documents/projects/loan/core/
├── [__init__.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/__init__.py)
│   └── Package initialization exposing the public core API symbols.
├── [money.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/money.py)
│   └── Decimal quantization utility [`money()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/money.py#L6) enforcing standard banking cent precision (`ROUND_HALF_UP`) and rejecting raw floats.
├── [models.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py)
│   └── Frozen dataclasses defining domain contracts: [`AmortizationRow`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L22), [`ScenarioInput`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L32), [`LoanOptionInput`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L53), [`OptionResult`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L71), and [`ComparisonResult`](file:///Users/alejandrodiaz/Documents/projects/loan/core/models.py#L94).
├── [amortization.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py)
│   └── Monthly payment calculator [`calculate_monthly_pi()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py#L6) and schedule generator [`calculate_amortization()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py#L29) with explicit final-month balance reconciliation to `$0.00`.
├── [financing_cost.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py)
│   └── Holding horizon cost engine [`calculate_option_result()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py#L22), points break-even analyzer [`calculate_break_even()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py#L69), and multi-option comparator [`compare_options()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/financing_cost.py#L141).
├── [mi_fees.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/mi_fees.py)
│   └── Mortgage insurance estimators for Conventional PMI ([`conventional_pmi_monthly()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/mi_fees.py#L6)), FHA MIP ([`fha_mip()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/mi_fees.py#L36)), VA funding fee, and USDA guarantee fees.
└── [screening.py](file:///Users/alejandrodiaz/Documents/projects/loan/core/screening.py)
    └── Conservative rule-based screening engine [`screen_all_programs()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/screening.py#L95) evaluating LTV and DTI limits across Conventional, FHA, VA, and USDA loan programs.
```

---

## Architectural Rules & Conventions

1. **No Float Arithmetic**: All calculations must use `Decimal`. Any attempt to pass a `float` into [`money()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/money.py#L8) raises a `TypeError`.
2. **True Financing Cost Equation**:
   $$\text{Financing Cost}_h = \text{Net Upfront Fees} + \sum_{t=1}^h (\text{Interest}_t + \text{MI}_t)$$
   Principal paid down is accumulated as equity and must never be added to financing cost.
3. **Exact Final Payment Reconciliation**: The final payment in [`calculate_amortization()`](file:///Users/alejandrodiaz/Documents/projects/loan/core/amortization.py#L23) adjusts for cumulative sub-cent rounding so ending balance reaches exactly `0.00`.

---

## Running Core Tests

The core module is tested with unit tests, real-world golden fixtures, and Hypothesis property fuzzing:

```bash
# Run pure math unit tests
.venv/bin/pytest tests/unit/test_money.py tests/unit/test_screening.py tests/unit/test_mi_fees.py -v

# Run golden fixture verification (Section 11 worked fixture)
.venv/bin/pytest tests/golden/ -v

# Run Hypothesis property-based fuzz tests
.venv/bin/pytest tests/property/ -v
```

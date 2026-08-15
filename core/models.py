from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID


class SourceType(StrEnum):
    MANUAL = "manual"
    LOAN_ESTIMATE = "loan_estimate"


class ScreeningState(StrEnum):
    LIKELY = "likely"
    UNLIKELY = "unlikely"
    NEEDS_AUS = "needs_aus"
    MORE_INFO_NEEDED = "more_info_needed"


@dataclass(frozen=True)
class AmortizationRow:
    month: int
    payment: Decimal
    principal: Decimal
    interest: Decimal
    mortgage_insurance: Decimal
    balance: Decimal


@dataclass(frozen=True)
class ScenarioInput:
    purpose: Literal["purchase", "refinance"]
    property_value: Decimal
    loan_amount: Decimal
    down_payment: Decimal | None
    fico_band: str | None
    occupancy: Literal["primary", "second_home", "investment"]
    property_type: Literal["single_family", "condo", "townhome", "multi_unit"]
    state: str
    county_fips: str | None
    program: Literal["conventional", "fha", "va", "usda"]
    term_months: int
    expected_horizon_months: int
    gross_monthly_income: Decimal | None = None
    recurring_monthly_debts: Decimal | None = None
    estimated_property_tax_monthly: Decimal | None = None
    estimated_homeowners_insurance_monthly: Decimal | None = None
    estimated_hoa_monthly: Decimal | None = None


@dataclass(frozen=True)
class LoanOptionInput:
    option_id: UUID
    label: str
    source_type: SourceType
    entered_on: date
    loan_amount: Decimal
    note_rate: Decimal
    apr: Decimal | None
    term_months: int
    points_pct: Decimal
    lender_credit: Decimal
    lender_fees: Decimal
    monthly_mi: Decimal | None = None
    upfront_mi: Decimal | None = None
    notes: str | None = None


@dataclass(frozen=True)
class OptionResult:
    option_id: UUID
    label: str
    source_type: SourceType
    monthly_pi: Decimal
    amortization: tuple[AmortizationRow, ...]
    net_upfront: Decimal
    financing_cost_by_month: tuple[Decimal, ...]
    financing_cost_at_horizon: Decimal
    remaining_balance_at_horizon: Decimal


@dataclass(frozen=True)
class BreakEvenResult:
    candidate_id: UUID
    baseline_id: UUID
    break_even_month: int | None  # None if no break-even within term
    savings_at_horizon: Decimal
    discounted_break_even_month: int | None = None
    discounted_savings_at_horizon: Decimal | None = None


@dataclass(frozen=True)
class ComparisonResult:
    horizon_months: int
    option_results: tuple[OptionResult, ...]
    break_even: BreakEvenResult | None
    recommended_option_id: UUID | None = None


@dataclass(frozen=True)
class ScreeningResult:
    state: ScreeningState
    reason_code: str

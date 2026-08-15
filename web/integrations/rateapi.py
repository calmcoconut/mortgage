from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from web.models import (
    BenchmarkPointModel,
    RateApiBudgetModel,
    RateApiCacheModel,
    RateApiSnapshotModel,
)

RATEAPI_DECISIONS_URL = "https://api.rateapi.dev/v1/decisions"


class BudgetExhaustedError(Exception):
    """Raised when monthly RateAPI budget safety threshold is reached."""


def get_amount_bucket(amount: Decimal, bucket_size: int = 25000) -> int:
    """Rounds loan amount to the nearest bucket size (e.g. $25,000) to optimize caching."""
    if amount <= 0:
        return 0
    return int(round(float(amount) / bucket_size) * bucket_size)


class RateApiAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        bucket_size: int | None = None,
        safety_threshold: int | None = None,
        cache_ttl_days: int | None = None,
    ):
        self.api_key = (
            api_key
            if api_key is not None
            else getattr(settings, "RATEAPI_KEY", "")
        )
        self.bucket_size = (
            bucket_size
            if bucket_size is not None
            else getattr(settings, "RATEAPI_BUCKET_SIZE", 25000)
        )
        self.safety_threshold = (
            safety_threshold
            if safety_threshold is not None
            else getattr(settings, "RATEAPI_SAFETY_THRESHOLD", 18)
        )
        self.cache_ttl_days = (
            cache_ttl_days
            if cache_ttl_days is not None
            else getattr(settings, "RATEAPI_CACHE_TTL_DAYS", 7)
        )

    def get_budget_status(self) -> dict[str, Any]:
        """Returns budget usage info for current month."""
        month_key = timezone.now().strftime("%Y-%m")
        budget, _ = RateApiBudgetModel.objects.get_or_create(
            month_key=month_key,
            defaults={
                "call_count": 0,
                "monthly_limit": 20,
                "safety_threshold": self.safety_threshold,
            },
        )
        return {
            "month_key": month_key,
            "call_count": budget.call_count,
            "monthly_limit": budget.monthly_limit,
            "safety_threshold": budget.safety_threshold,
            "can_call": budget.call_count < budget.safety_threshold,
        }

    def build_payload(
        self,
        state: str,
        amount: Decimal,
        term_months: int,
        intent: str = "purchase",
        county: str | None = None,
        zip_code: str | None = None,
        city: str | None = None,
        current_apr: Decimal | None = None,
    ) -> dict[str, Any]:
        geo: dict[str, Any] = {"state": state.upper()}
        if county:
            geo["county"] = county
        if zip_code:
            geo["zip"] = zip_code
        if city:
            geo["city"] = city

        product_req: dict[str, Any] = {
            "product_type": "mortgage",
            "intent": intent,
            "amount": int(amount),
            "term_months": term_months,
        }

        if intent == "refinance" and current_apr is not None:
            apr_val = float(current_apr)
            if apr_val < 1.0:
                apr_val = apr_val * 100
            product_req["current_offer"] = {"apr": round(apr_val, 4)}

        return {
            "decision_type": "financing",
            "context": {"geo": geo},
            "product_request": product_req,
        }

    def _process_offers(self, raw_offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        processed = []
        for offer in raw_offers:
            # Check confidence score
            eligibility = offer.get("eligibility") or {}
            conf = eligibility.get("confidence")
            if conf is None:
                conf = 0.85  # default confidence when unassigned

            try:
                conf_float = float(conf)
            except (ValueError, TypeError):
                conf_float = 0.85

            # Step 4: Drop offers below 0.5
            if conf_float < 0.5:
                continue

            category = "high" if conf_float >= 0.7 else "warning"

            offer_copy = dict(offer)
            offer_copy["confidence_score"] = conf_float
            offer_copy["confidence_category"] = category
            processed.append(offer_copy)

        return processed

    def fetch_decisions(
        self,
        state: str,
        amount: Decimal,
        term_months: int,
        intent: str = "purchase",
        county: str | None = None,
        zip_code: str | None = None,
        city: str | None = None,
        current_apr: Decimal | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        now = timezone.now()
        amount_bucket = get_amount_bucket(amount, self.bucket_size)
        cache_key = f"{state.upper()}_{intent}_{amount_bucket}_{term_months}"

        # 1. Check Cache
        if not force_refresh:
            cached = (
                RateApiCacheModel.objects.filter(
                    cache_key=cache_key,
                    expires_at__gt=now,
                )
                .order_by("-cached_at")
                .first()
            )
            if cached:
                raw_actions = cached.response_payload.get("actions", [])
                raw_offers = raw_actions[0].get("offers", []) if raw_actions else []
                return {
                    "from_cache": True,
                    "cached_at": cached.cached_at,
                    "offers": self._process_offers(raw_offers),
                    "raw_response": cached.response_payload,
                    "budget": self.get_budget_status(),
                }

        # 2. Check Budget Guard
        budget = self.get_budget_status()
        if not budget["can_call"]:
            # Check if we have an expired cache entry to fall back on
            stale_cached = (
                RateApiCacheModel.objects.filter(cache_key=cache_key)
                .order_by("-cached_at")
                .first()
            )
            if stale_cached:
                raw_actions = stale_cached.response_payload.get("actions", [])
                raw_offers = raw_actions[0].get("offers", []) if raw_actions else []
                return {
                    "from_cache": True,
                    "is_stale": True,
                    "cached_at": stale_cached.cached_at,
                    "offers": self._process_offers(raw_offers),
                    "raw_response": stale_cached.response_payload,
                    "budget": budget,
                    "warning": "Monthly budget limit reached. Serving cached rate data.",
                }
            raise BudgetExhaustedError(
                f"RateAPI monthly safety limit reached ({budget['call_count']}/{budget['safety_threshold']} calls used). Outbound call blocked."
            )

        if not self.api_key:
            raise ValueError("No RATEAPI_KEY configured in environment or settings.")

        # 3. Perform Outbound API Call
        payload = self.build_payload(
            state=state,
            amount=Decimal(amount_bucket),
            term_months=term_months,
            intent=intent,
            county=county,
            zip_code=zip_code,
            city=city,
            current_apr=current_apr,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        resp = requests.post(
            RATEAPI_DECISIONS_URL,
            json=payload,
            headers=headers,
            timeout=10,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"RateAPI error: HTTP {resp.status_code} - {resp.text}"
            )

        data = resp.json()

        # 4. Save to Cache (Configurable TTL, default: 7 days / 1 week)
        RateApiCacheModel.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                "query_state": state.upper(),
                "query_intent": intent,
                "query_amount_bucket": amount_bucket,
                "query_term_months": term_months,
                "response_payload": data,
                "cached_at": now,
                "expires_at": now + timedelta(days=self.cache_ttl_days),
            },
        )

        # 5. Increment Monthly Usage Counter
        month_key = now.strftime("%Y-%m")
        budget_obj, _ = RateApiBudgetModel.objects.get_or_create(
            month_key=month_key,
            defaults={
                "call_count": 0,
                "monthly_limit": 20,
                "safety_threshold": self.safety_threshold,
            },
        )
        budget_obj.call_count += 1
        budget_obj.last_called_at = now
        budget_obj.save(update_fields=["call_count", "last_called_at"])

        raw_actions = data.get("actions", [])
        raw_offers = raw_actions[0].get("offers", []) if raw_actions else []

        # 6. Maximize Data Capture: Ingest returned offers into durable SQLite snapshots
        for off in raw_offers:
            lender_name = off.get("credit_union_name") or off.get("lender")
            if not lender_name:
                continue
            p_name = off.get("product_name") or off.get("display_name") or f"{term_months // 12}Y Fixed"
            p_type = "30-year-fixed" if term_months >= 300 else f"{term_months // 12}-year-fixed"
            elig_obj = off.get("eligibility") or {}
            req_sum = elig_obj.get("requirements_summary", "")

            try:
                r_val = Decimal(str(off.get("rate", 0)))
                a_val = Decimal(str(off.get("apr", r_val)))
                pts_val = Decimal(str(off.get("points", 0)))
                conf_val = Decimal(
                    str(off.get("confidence_score") or elig_obj.get("confidence") or 0.85)
                )
            except (InvalidOperation, ValueError, TypeError):
                continue

            RateApiSnapshotModel.objects.update_or_create(
                lender=lender_name,
                product_type=p_type,
                state=state.upper(),
                observed_on=now.date(),
                defaults={
                    "product_name": p_name,
                    "loan_program": "conventional",
                    "rate": r_val,
                    "apr": a_val,
                    "points": pts_val,
                    "fetched_at": now,
                    "confidence_score": conf_val,
                    "eligibility_summary": req_sum,
                },
            )

        return {
            "from_cache": False,
            "cached_at": now,
            "offers": self._process_offers(raw_offers),
            "raw_response": data,
            "budget": self.get_budget_status(),
        }

    def fetch_and_persist_market_rates(
        self, state: str = "CA", force_refresh: bool = False
    ) -> list[RateApiSnapshotModel]:
        """Fetches raw market rate snapshots and persists them to durable SQLite storage."""
        now = timezone.now()
        today = now.date()

        if not force_refresh:
            min_valid_date = today - timedelta(days=self.cache_ttl_days)
            existing = list(
                RateApiSnapshotModel.objects.filter(
                    state=state.upper(), observed_on__gte=min_valid_date
                )
            )
            if existing:
                return existing

        budget = self.get_budget_status()
        if not budget["can_call"]:
            return list(
                RateApiSnapshotModel.objects.filter(state=state.upper()).order_by("-observed_on")[:10]
            )

        if not self.api_key:
            return list(
                RateApiSnapshotModel.objects.filter(state=state.upper()).order_by("-observed_on")[:10]
            )

        url = "https://api.rateapi.dev/v1/rates"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
        }
        params = {
            "product_type": "mortgage",
            "state": state.upper(),
        }

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                return list(RateApiSnapshotModel.objects.filter(state=state.upper())[:10])

            data = resp.json()
            rates = data.get("rates", [])
            persisted = []

            for r in rates:
                lender = r.get("lender")
                if not lender:
                    continue
                product_type = r.get("product_type", "30-year-fixed")
                product_name = r.get("product_name", product_type)
                loan_program = r.get("loan_program", "conventional")

                try:
                    rate_val = Decimal(str(r.get("rate", 0)))
                    apr_val = Decimal(str(r.get("apr", rate_val)))
                    points_val = Decimal(str(r.get("points", 0)))
                except (InvalidOperation, ValueError, TypeError):
                    continue

                eligibility = r.get("eligibility") or {}
                conf = eligibility.get("confidence")
                conf_score = None
                if conf is not None:
                    try:
                        conf_score = Decimal(str(conf))
                    except (InvalidOperation, ValueError):
                        pass

                req_summary = eligibility.get("requirements_summary", "")

                as_of_str = r.get("as_of")
                obs_date = today
                if as_of_str:
                    try:
                        obs_date = datetime.fromisoformat(as_of_str.replace("Z", "+00:00")).date()
                    except Exception:
                        obs_date = today

                obj, _ = RateApiSnapshotModel.objects.update_or_create(
                    lender=lender,
                    product_type=product_type,
                    state=state.upper(),
                    observed_on=obs_date,
                    defaults={
                        "product_name": product_name,
                        "loan_program": loan_program,
                        "rate": rate_val,
                        "apr": apr_val,
                        "points": points_val,
                        "fetched_at": now,
                        "eligibility_summary": req_summary,
                        "confidence_score": conf_score,
                    },
                )
                persisted.append(obj)

            # Increment budget counter
            month_key = now.strftime("%Y-%m")
            budget_obj, _ = RateApiBudgetModel.objects.get_or_create(
                month_key=month_key,
                defaults={
                    "call_count": 0,
                    "monthly_limit": 20,
                    "safety_threshold": self.safety_threshold,
                },
            )
            budget_obj.call_count += 1
            budget_obj.last_called_at = now
            budget_obj.save(update_fields=["call_count", "last_called_at"])

            return persisted

        except Exception:
            return list(RateApiSnapshotModel.objects.filter(state=state.upper())[:10])


def aggregate_product_term_structure() -> list[dict[str, Any]]:
    """Aggregates latest market snapshots by mortgage product structure."""
    PRODUCT_MAPPINGS = {
        "30-year-fixed": ("30-Year Fixed", 1),
        "15-year-fixed": ("15-Year Fixed", 2),
        "10-year-fixed": ("10-Year Fixed", 3),
        "7-1-arm": ("7/1 ARM", 4),
        "5-1-arm": ("5/1 ARM", 5),
        "3-1-arm": ("3/1 ARM", 6),
        "arm": ("ARM", 7),
    }

    latest_date = (
        RateApiSnapshotModel.objects.order_by("-observed_on")
        .values_list("observed_on", flat=True)
        .first()
    )
    if not latest_date:
        return []

    snapshots = RateApiSnapshotModel.objects.filter(observed_on=latest_date)
    grouped: dict[str, list[RateApiSnapshotModel]] = {}

    for s in snapshots:
        mapping = PRODUCT_MAPPINGS.get(s.product_type)
        label = mapping[0] if mapping else s.product_type
        grouped.setdefault(label, []).append(s)

    results = []
    for p_type, (label, sort_order) in PRODUCT_MAPPINGS.items():
        items = grouped.get(label, [])
        if not items:
            continue
        avg_rate = float(sum(i.rate for i in items) / len(items))
        avg_apr = float(sum(i.apr for i in items) / len(items))
        results.append(
            {
                "label": label,
                "avg_rate": round(avg_rate, 3),
                "avg_apr": round(avg_apr, 3),
                "sample_count": len(items),
                "_sort": sort_order,
            }
        )

    results.sort(key=lambda x: x["_sort"])
    return results


def calculate_fred_vs_cu_spread() -> dict[str, Any]:
    """Calculates spread between FRED national 30Y average and best credit union 30Y rate."""
    latest_fred = (
        BenchmarkPointModel.objects.filter(series="MORTGAGE30US")
        .order_by("-observed_on")
        .first()
    )
    latest_cu = (
        RateApiSnapshotModel.objects.filter(product_type="30-year-fixed")
        .order_by("rate")
        .first()
    )

    if not latest_fred or not latest_cu:
        return {
            "fred_30y": 6.50,
            "top_cu_30y": 6.00,
            "spread_bps": -50,
            "cu_name": "Credit Union Average",
        }

    fred_val = float(latest_fred.value)
    cu_val = float(latest_cu.rate)
    spread_bps = int(round((cu_val - fred_val) * 100))

    return {
        "fred_30y": fred_val,
        "top_cu_30y": cu_val,
        "spread_bps": spread_bps,
        "cu_name": latest_cu.lender,
    }


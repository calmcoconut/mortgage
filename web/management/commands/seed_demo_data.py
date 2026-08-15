from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from web.models import (
    BenchmarkPointModel,
    LoanOptionModel,
    RateApiSnapshotModel,
    ScenarioModel,
)


class Command(BaseCommand):
    help = "Seed database with worked fixture, UI mockup scenarios, and historical benchmark context."

    def handle(self, *args, **options):
        # 1. UI Mockup Scenario (Mountain View purchase)
        mv_scenario, _ = ScenarioModel.objects.update_or_create(
            name="Mountain View purchase",
            defaults={
                "purpose": "purchase",
                "property_value": Decimal("850000.00"),
                "loan_amount": Decimal("680000.00"),
                "down_payment": Decimal("170000.00"),
                "fico_band": "760+",
                "occupancy": "primary",
                "property_type": "single_family",
                "state": "CA",
                "county_fips": "06085",
                "program": "conventional",
                "term_months": 360,
                "expected_horizon_months": 84,  # 7 years
                "gross_monthly_income": Decimal("18000.00"),
                "recurring_monthly_debts": Decimal("1200.00"),
                "estimated_property_tax_monthly": Decimal("850.00"),
                "estimated_homeowners_insurance_monthly": Decimal("140.00"),
                "estimated_hoa_monthly": Decimal("0.00"),
            },
        )

        mv_scenario.loan_options.all().delete()

        LoanOptionModel.objects.create(
            scenario=mv_scenario,
            label="Option A: Advertised Lender",
            source_type="manual",
            entered_on=date.today(),
            loan_amount=Decimal("680000.00"),
            note_rate=Decimal("0.0650"),
            apr=Decimal("0.0650"),
            term_months=360,
            points_pct=Decimal("0.0000"),
            lender_credit=Decimal("0.00"),
            lender_fees=Decimal("1200.00"),
            notes="30% of the escrow credits for observed paths",
        )

        LoanOptionModel.objects.create(
            scenario=mv_scenario,
            label="Option B: Uploaded Loan Estimate",
            source_type="loan_estimate",
            entered_on=date.today(),
            loan_amount=Decimal("680000.00"),
            note_rate=Decimal("0.0600"),
            apr=Decimal("0.0615"),
            term_months=360,
            points_pct=Decimal("0.0150"),  # 1.5 pts
            lender_credit=Decimal("1000.00"),
            lender_fees=Decimal("800.00"),
            notes="50% of the escrow credit for observed paths",
        )

        # Option C: Seeded from top cached RateAPI snapshot if available, otherwise synthetic CU quote
        best_cu_snap = (
            RateApiSnapshotModel.objects.filter(
                state="CA", product_type="30-year-fixed"
            )
            .order_by("rate")
            .first()
        )

        if best_cu_snap:
            raw_rate = best_cu_snap.rate / 100 if best_cu_snap.rate > 1 else best_cu_snap.rate
            raw_apr = (
                (best_cu_snap.apr / 100)
                if (best_cu_snap.apr and best_cu_snap.apr > 1)
                else (raw_rate + Decimal("0.0015"))
            )
            raw_points = (
                (best_cu_snap.points / 100)
                if (best_cu_snap.points and best_cu_snap.points > 1)
                else best_cu_snap.points
            )
            LoanOptionModel.objects.create(
                scenario=mv_scenario,
                label=f"Option C: {best_cu_snap.lender} (RateAPI)",
                institution_name=best_cu_snap.lender,
                source_type="rate_api",
                entered_on=best_cu_snap.observed_on,
                loan_amount=Decimal("680000.00"),
                note_rate=raw_rate,
                apr=raw_apr,
                points_pct=raw_points,
                term_months=360,
                confidence_score=best_cu_snap.confidence_score or Decimal("0.880"),
                lender_credit=Decimal("0.00"),
                lender_fees=Decimal("850.00"),
                notes=best_cu_snap.eligibility_summary
                or "Live credit union quote seeded from RateAPI cache",
            )
        else:
            LoanOptionModel.objects.create(
                scenario=mv_scenario,
                label="Option C: Credit Union Quote",
                source_type="manual",
                entered_on=date.today() - timedelta(days=2),
                loan_amount=Decimal("680000.00"),
                note_rate=Decimal("0.06375"),
                apr=Decimal("0.0640"),
                term_months=360,
                points_pct=Decimal("0.0050"),
                lender_credit=Decimal("0.00"),
                lender_fees=Decimal("950.00"),
                notes="Requires credit union membership",
            )

        # 2. Worked Fixture Scenario (Section 11)
        wf_scenario, _ = ScenarioModel.objects.update_or_create(
            name="Section 11 Worked Fixture ($400k)",
            defaults={
                "purpose": "purchase",
                "property_value": Decimal("500000.00"),
                "loan_amount": Decimal("400000.00"),
                "down_payment": Decimal("100000.00"),
                "fico_band": "760+",
                "occupancy": "primary",
                "property_type": "single_family",
                "state": "CA",
                "program": "conventional",
                "term_months": 360,
                "expected_horizon_months": 84,  # 7 years
                "gross_monthly_income": Decimal("12000.00"),
                "recurring_monthly_debts": Decimal("800.00"),
                "estimated_property_tax_monthly": Decimal("500.00"),
                "estimated_homeowners_insurance_monthly": Decimal("100.00"),
                "estimated_hoa_monthly": Decimal("0.00"),
            },
        )

        wf_scenario.loan_options.all().delete()

        LoanOptionModel.objects.create(
            scenario=wf_scenario,
            label="Option A: 6.50% / 0 pts",
            source_type="manual",
            entered_on=date.today(),
            loan_amount=Decimal("400000.00"),
            note_rate=Decimal("0.0650"),
            apr=Decimal("0.0650"),
            term_months=360,
            points_pct=Decimal("0.0000"),
            lender_credit=Decimal("0.00"),
            lender_fees=Decimal("0.00"),
        )

        LoanOptionModel.objects.create(
            scenario=wf_scenario,
            label="Option B: 6.00% / 2 pts",
            source_type="loan_estimate",
            entered_on=date.today(),
            loan_amount=Decimal("400000.00"),
            note_rate=Decimal("0.0600"),
            apr=Decimal("0.0615"),
            term_months=360,
            points_pct=Decimal("0.0200"),
            lender_credit=Decimal("0.00"),
            lender_fees=Decimal("0.00"),
            notes="Breaks even at month 48; saves $6,033 over 7 years.",
        )

        # 3. Seed 5 years (260 weeks) of historical benchmark points if empty
        base_date = date.today()
        now = timezone.now()

        if BenchmarkPointModel.objects.count() < 100:
            for week in range(260):
                obs_d = base_date - timedelta(weeks=week)
                # Simulated realistic mortgage averages
                val30 = Decimal("6.50") + Decimal(str(round((week * 0.015) % 1.2 - 0.6, 2)))
                val15 = val30 - Decimal("0.75")

                BenchmarkPointModel.objects.update_or_create(
                    series="MORTGAGE30US",
                    observed_on=obs_d,
                    defaults={"value": val30, "fetched_at": now},
                )
                BenchmarkPointModel.objects.update_or_create(
                    series="MORTGAGE15US",
                    observed_on=obs_d,
                    defaults={"value": val15, "fetched_at": now},
                )

        # 4. Seed durable RateAPI credit union market rate snapshots
        cu_snapshots = [
            ("Safe 1 Credit Union", "30-year-fixed", "30-Year Fixed Rate", "6.000", "6.000", "0.000", "Community charter in CA"),
            ("Sacramento Credit Union", "15-year-fixed", "15-Year Fixed", "5.375", "5.375", "0.000", "Community charter: Sacramento, Placer"),
            ("Coast Central Credit Union", "5-1-arm", "5/1 ARM Conforming", "5.125", "5.250", "0.000", "Community charter in CA"),
            ("Coast Central Credit Union", "7-1-arm", "7/1 ARM Conforming", "5.375", "5.450", "0.000", "Community charter in CA"),
            ("Northeast Community CU", "30-year-fixed", "30 Year Fixed - Conforming", "6.125", "6.283", "0.000", "Community charter in CA"),
            ("United Local Credit Union", "10-year-fixed", "10-Year Fixed Conforming", "5.250", "5.300", "0.000", "Local union affiliation"),
            ("F & A Credit Union", "30-year-fixed", "30-Year Fixed Rate", "6.375", "6.375", "0.000", "Employer / community charter"),
            ("Ume Credit Union", "5-1-arm", "5/1 ARM", "5.375", "5.375", "0.000", "Community charter: Burbank"),
        ]

        for lender, p_type, p_name, r, a, pts, elig in cu_snapshots:
            RateApiSnapshotModel.objects.update_or_create(
                lender=lender,
                product_type=p_type,
                state="CA",
                observed_on=base_date,
                defaults={
                    "product_name": p_name,
                    "loan_program": "conventional",
                    "rate": Decimal(r),
                    "apr": Decimal(a),
                    "points": Decimal(pts),
                    "fetched_at": now,
                    "eligibility_summary": elig,
                    "confidence_score": Decimal("0.900"),
                },
            )

        self.stdout.write(
            self.style.SUCCESS("Successfully seeded demo scenarios, 5 years of FRED benchmarks, and RateAPI market snapshots!")
        )

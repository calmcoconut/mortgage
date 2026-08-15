from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from web.models import BenchmarkPointModel, LoanOptionModel, ScenarioModel


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

        # 3. Seed 52 weeks of historical benchmark points
        base_date = date.today()
        now = timezone.now()

        for week in range(52):
            obs_d = base_date - timedelta(weeks=week)
            # Simulated realistic mortgage averages
            val30 = Decimal("6.50") + Decimal(str(round((week * 0.015) % 0.6 - 0.3, 2)))
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

        self.stdout.write(self.style.SUCCESS("Successfully seeded demo scenarios and benchmark data!"))

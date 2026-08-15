from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from web.integrations.rateapi import RateApiAdapter
from web.models import RateApiSnapshotModel


class Command(BaseCommand):
    help = "Fetch live market rate quotes and ARM/Fixed products from RateAPI.dev into local durable storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            type=str,
            default=getattr(settings, "DEFAULT_STATE", "CA"),
            help="State code (e.g. CA, TX, NY)",
        )
        parser.add_argument(
            "--county",
            type=str,
            default=getattr(settings, "DEFAULT_COUNTY", ""),
            help="County name (e.g. Santa Clara)",
        )
        parser.add_argument(
            "--all-terms",
            action="store_true",
            help="Fetch quotes for 30Y Fixed, 15Y Fixed, 7/1 ARM, 5/1 ARM, and 10Y Fixed products",
        )

    def handle(self, *args, **options):
        state = options["state"].upper()
        county = options.get("county") or getattr(settings, "DEFAULT_COUNTY", "")
        all_terms = options.get("all_terms", False)

        adapter = RateApiAdapter()
        if not adapter.api_key:
            self.stdout.write(
                self.style.WARNING(
                    "No RATEAPI_KEY found in .env or settings. Please configure RATEAPI_KEY."
                )
            )
            return

        budget = adapter.get_budget_status()
        self.stdout.write(
            f"Monthly RateAPI Budget: {budget['call_count']} / {budget['safety_threshold']} calls used."
        )

        self.stdout.write(f"Fetching macro market rates for state: {state}...")
        snapshots = adapter.fetch_and_persist_market_rates(state=state, force_refresh=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully ingested {len(snapshots)} state-wide rate snapshots."
            )
        )

        if all_terms:
            # Query candidate credit unions across diverse loan terms & products
            terms_to_query = [
                ("30-Year Fixed", 360),
                ("15-Year Fixed", 180),
                ("7/1 ARM", 84),
                ("5/1 ARM", 60),
                ("10-Year Fixed", 120),
            ]
            for term_label, months in terms_to_query:
                budget = adapter.get_budget_status()
                if not budget["can_call"]:
                    self.stdout.write(
                        self.style.WARNING("Budget safety limit reached. Stopping batch fetch.")
                    )
                    break

                self.stdout.write(f"Fetching localized {term_label} quotes ({months}m)...")
                try:
                    res = adapter.fetch_decisions(
                        state=state,
                        amount=Decimal("680000"),
                        term_months=months,
                        county=county or None,
                        force_refresh=True,
                    )
                    offers_count = len(res.get("offers", []))
                    self.stdout.write(
                        self.style.SUCCESS(f"  -> Ingested {offers_count} {term_label} offers.")
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  -> Error: {e}"))

        total_count = RateApiSnapshotModel.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Done! Local database now holds {total_count} total quotes.")
        )

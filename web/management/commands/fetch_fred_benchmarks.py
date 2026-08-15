from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from web.models import BenchmarkPointModel

FRED_SERIES = ["MORTGAGE30US", "MORTGAGE15US"]
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


class Command(BaseCommand):
    help = "Fetch latest benchmark mortgage rates from the Federal Reserve Economic Data (FRED) API."

    def add_arguments(self, parser):
        parser.add_argument("--api-key", type=str, default="", help="FRED API key")

    def handle(self, *args, **options):
        api_key = options["api_key"] or getattr(settings, "FRED_API_KEY", "")
        if not api_key:
            self.stdout.write(
                self.style.WARNING(
                    "No FRED_API_KEY provided in environment or argument. Skipping fetch."
                )
            )
            return

        now = timezone.now()
        total_upserted = 0

        for series in FRED_SERIES:
            params = {
                "series_id": series,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 52,  # Last 52 weeks
            }
            try:
                resp = requests.get(FRED_API_URL, params=params, timeout=10)
                if resp.status_code != 200:
                    self.stderr.write(
                        self.style.ERROR(
                            f"FRED API error for {series}: HTTP {resp.status_code}"
                        )
                    )
                    continue

                data = resp.json()
                observations = data.get("observations", [])

                for obs in observations:
                    obs_date_str = obs.get("date")
                    obs_val_str = obs.get("value")
                    if not obs_date_str or not obs_val_str or obs_val_str == ".":
                        continue

                    try:
                        obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d").date()
                        obs_val = Decimal(obs_val_str)
                    except (ValueError, InvalidOperation):
                        continue

                    BenchmarkPointModel.objects.update_or_create(
                        series=series,
                        observed_on=obs_date,
                        defaults={
                            "value": obs_val,
                            "fetched_at": now,
                        },
                    )
                    total_upserted += 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to fetch {series}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {total_upserted} benchmark rate observations."
            )
        )

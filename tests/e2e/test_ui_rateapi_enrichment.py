from decimal import Decimal
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from web.integrations.rateapi import RateApiAdapter
from web.models import LoanOptionModel, ScenarioModel


class TestRateApiEnrichmentE2E(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1400,900")
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.driver.implicitly_wait(5)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        self.scenario = ScenarioModel.objects.create(
            name="E2E RateAPI Scenario",
            purpose="purchase",
            property_value=Decimal("850000.00"),
            loan_amount=Decimal("680000.00"),
            down_payment=Decimal("170000.00"),
            fico_band="760+",
            occupancy="primary",
            property_type="single_family",
            state="CA",
            program="conventional",
            term_months=360,
            expected_horizon_months=84,
            gross_monthly_income=Decimal("18000.00"),
            recurring_monthly_debts=Decimal("1200.00"),
        )
        # Add a baseline option
        LoanOptionModel.objects.create(
            scenario=self.scenario,
            label="Baseline Option 6.50%",
            source_type="manual",
            loan_amount=Decimal("680000.00"),
            note_rate=Decimal("0.065000"),
            apr=Decimal("0.065000"),
            term_months=360,
            points_pct=Decimal("0.000000"),
        )

    def test_live_market_offers_modal_and_import_workflow(self):
        mock_result = {
            "from_cache": False,
            "offers": [
                {
                    "rank": 1,
                    "credit_union_name": "Safe 1 Credit Union",
                    "display_name": "30-Year Fixed",
                    "rate": 6.0,
                    "apr": 6.0,
                    "points": 0.0,
                    "monthly_payment": 4076.94,
                    "confidence_score": 0.95,
                    "confidence_category": "high",
                    "eligibility": {
                        "status": "likely_eligible",
                        "requirements_summary": "Community charter: live/work in CA",
                    },
                }
            ],
            "budget": {
                "month_key": "2026-08",
                "call_count": 4,
                "monthly_limit": 20,
                "safety_threshold": 18,
                "can_call": True,
            },
        }

        with patch.object(
            RateApiAdapter, "fetch_decisions", return_value=mock_result
        ):
            # 1. Open Compare page
            self.driver.get(f"{self.live_server_url}/scenarios/{self.scenario.id}/compare/")
            wait = WebDriverWait(self.driver, 10)

            # 2. Click "Live Market Offers" button
            enrich_btn = wait.until(
                EC.element_to_be_clickable((By.ID, "btn-rateapi-enrich"))
            )
            enrich_btn.click()

            # 3. Assert modal appears
            modal = wait.until(
                EC.visibility_of_element_located((By.CLASS_NAME, "rateapi-modal"))
            )
            self.assertIn("Live Market Offers", modal.text)
            self.assertIn("Safe 1 Credit Union", modal.text)
            self.assertIn("Budget: 4 / 18", modal.text)

            # 4. Click "+ Import to Comparison"
            import_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Import to Comparison')]"))
            )
            import_btn.click()

            # 5. Assert redirect back to Compare matrix with imported option
            wait.until(EC.staleness_of(modal))
            matrix = wait.until(
                EC.presence_of_element_located((By.ID, "compare-matrix-wrapper"))
            )
            self.assertIn("Safe 1 Credit Union", matrix.text)

            # Assert database has the imported option
            imported_opt = LoanOptionModel.objects.filter(
                scenario=self.scenario, source_type="rate_api"
            ).first()
            self.assertIsNotNone(imported_opt)
            self.assertEqual(imported_opt.institution_name, "Safe 1 Credit Union")
            self.assertEqual(imported_opt.note_rate, Decimal("0.060000"))

from datetime import date
from decimal import Decimal
import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from web.models import LoanOptionModel, ScenarioModel


class TestCompareMatrixE2E(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1600,1000")
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.driver.implicitly_wait(4)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        # Create Section 11 Worked Fixture Scenario ($400k)
        self.scenario = ScenarioModel.objects.create(
            name="Section 11 Worked Fixture ($400k)",
            purpose="purchase",
            property_value=Decimal("500000.00"),
            loan_amount=Decimal("400000.00"),
            down_payment=Decimal("100000.00"),
            term_months=360,
            expected_horizon_months=84,  # 7 years
            gross_monthly_income=Decimal("12000.00"),
            recurring_monthly_debts=Decimal("800.00"),
        )
        self.opt_a = LoanOptionModel.objects.create(
            scenario=self.scenario,
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
        self.opt_b = LoanOptionModel.objects.create(
            scenario=self.scenario,
            label="Option B: 6.00% / 2 pts",
            source_type="loan_estimate",
            entered_on=date.today(),
            loan_amount=Decimal("400000.00"),
            note_rate=Decimal("0.0600"),
            apr=Decimal("0.0615"),
            term_months=360,
            points_pct=Decimal("0.0200"),  # $8,000 upfront
            lender_credit=Decimal("0.00"),
            lender_fees=Decimal("0.00"),
        )

    def test_compare_matrix_and_horizon_switch(self):
        wait = WebDriverWait(self.driver, 10)
        # Open compare page at 7-year horizon
        self.driver.get(f"{self.live_server_url}/scenarios/{self.scenario.id}/compare/?horizon=84")

        # 1. Assert Recommendation Banner
        rec_banner = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "recommendation-banner")))
        self.assertIn("RECOMMENDED FOR YOUR 7-YEAR HORIZON", rec_banner.text.upper())
        self.assertIn("Option B: 6.00% / 2 pts", rec_banner.text)
        self.assertIn("6,033 lower estimated financing cost", rec_banner.text)

        # 2. Assert Table rows
        matrix = self.driver.find_element(By.CLASS_NAME, "matrix-table")
        table_text = matrix.text
        self.assertIn("2,528", table_text)  # Option A P&I
        self.assertIn("2,398", table_text)  # Option B P&I
        self.assertIn("174,040", table_text)  # Option A 7-year cost ($174,039.84 rounds to 174,040)
        self.assertIn("168,007", table_text)  # Option B 7-year cost ($168,006.52 rounds to 168,007)

        # 3. Change Hold Period to 5 years (60 months)
        select_elem = self.driver.find_element(By.CSS_SELECTOR, "select.form-select")
        select = Select(select_elem)
        select.select_by_value("60")

        # Wait for page reload with horizon=60
        wait.until(EC.url_contains("horizon=60"))
        rec_banner = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "recommendation-banner")))
        self.assertIn("5-YEAR", rec_banner.text.upper())
        self.assertIn("2,031 lower estimated financing cost", rec_banner.text)

        # 4. Change Hold Period to 30 years (360 months)
        select_elem = self.driver.find_element(By.CSS_SELECTOR, "select.form-select")
        select = Select(select_elem)
        select.select_by_value("360")

        wait.until(EC.url_contains("horizon=360"))
        rec_banner = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "recommendation-banner")))
        self.assertIn("30-YEAR", rec_banner.text.upper())
        self.assertIn("38,825 lower estimated financing cost", rec_banner.text)

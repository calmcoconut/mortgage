from datetime import date
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from web.models import LoanOptionModel, ScenarioModel


class TestProjectedCostsE2E(StaticLiveServerTestCase):
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
        self.scenario = ScenarioModel.objects.create(
            name="Worked Fixture Scenario",
            purpose="purchase",
            property_value=Decimal("500000.00"),
            loan_amount=Decimal("400000.00"),
            down_payment=Decimal("100000.00"),
            term_months=360,
            expected_horizon_months=84,
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
            points_pct=Decimal("0.0200"),
        )

    def test_projected_costs_cards_and_canvas(self):
        wait = WebDriverWait(self.driver, 10)
        self.driver.get(
            f"{self.live_server_url}/scenarios/{self.scenario.id}/projected-costs/?horizon=84"
        )

        # 1. Assert KPI Summary Cards
        kpi_grid = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "kpi-grid"))
        )
        grid_text = kpi_grid.text
        self.assertIn("6,033", grid_text)  # Option B savings at 7 years ($6,033)
        self.assertIn("Month 48", grid_text)  # Points break-even Month 48
        self.assertIn("130", grid_text)  # Monthly P&I difference ($130)

        # 2. Assert Chart.js canvas elements
        cost_canvas = self.driver.find_element(By.ID, "cumulativeCostChart")
        comp_canvas = self.driver.find_element(By.ID, "paymentCompositionChart")
        bal_canvas = self.driver.find_element(By.ID, "loanBalanceChart")
        self.assertTrue(cost_canvas.is_displayed())
        self.assertTrue(comp_canvas.is_displayed())
        self.assertTrue(bal_canvas.is_displayed())

        # 3. Assert Right sidebar info
        info_card = self.driver.find_element(By.CLASS_NAME, "info-card")
        self.assertIn("What's included?", info_card.text)
        self.assertIn("Not included", info_card.text)
        self.assertIn("Verified Loan Estimate", info_card.text)
        self.assertIn("Advertised observation", info_card.text)

        # 4. Test Discount rate sensitivity input
        self.driver.execute_script("reloadWithDiscount('5.0');")

        wait.until(EC.url_contains("discount_rate=5.0"))
        kpi_grid = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "kpi-grid"))
        )
        self.assertIn("Month 48", kpi_grid.text)

from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from web.models import ScenarioModel


class TestOptionCrudE2E(StaticLiveServerTestCase):
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
            name="CRUD Test Scenario",
            purpose="purchase",
            property_value=Decimal("600000.00"),
            loan_amount=Decimal("480000.00"),
            term_months=360,
            expected_horizon_months=84,
        )

    def test_option_create_edit_delete_workflow(self):
        wait = WebDriverWait(self.driver, 10)
        self.driver.get(f"{self.live_server_url}/scenarios/{self.scenario.id}/compare/")

        # 1. Click Add Loan Option
        add_btn = wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Add Loan Option"))
        )
        add_btn.click()

        wait.until(EC.url_contains("/options/new/"))

        # 2. Fill in Loan Option details
        label_input = self.driver.find_element(By.NAME, "label")
        label_input.clear()
        label_input.send_keys("Transcribed LE: 5.75% / 1 pt")

        src_select = Select(self.driver.find_element(By.NAME, "source_type"))
        src_select.select_by_value("loan_estimate")

        rate_input = self.driver.find_element(By.NAME, "rate_percent")
        rate_input.clear()
        rate_input.send_keys("5.750")

        pts_input = self.driver.find_element(By.NAME, "points_percent")
        pts_input.clear()
        pts_input.send_keys("1.0")

        fees_input = self.driver.find_element(By.NAME, "lender_fees")
        fees_input.clear()
        fees_input.send_keys("500")

        # Submit form
        save_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.driver.execute_script(
            "arguments[0].scrollIntoView(true); arguments[0].click();", save_btn
        )

        # 3. Assert redirected back to Compare and option column exists
        wait.until(EC.url_contains("/compare/"))
        matrix = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "matrix-table"))
        )
        self.assertIn("Transcribed LE: 5.75% / 1 pt", matrix.text)
        self.assertIn("5.750%", matrix.text)

        # 4. Edit Option
        edit_btn = self.driver.find_element(By.LINK_TEXT, "Edit")
        edit_btn.click()

        wait.until(EC.url_contains("/edit/"))
        rate_input = wait.until(
            EC.presence_of_element_located((By.NAME, "rate_percent"))
        )
        rate_input.clear()
        rate_input.send_keys("5.500")

        save_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView(true); arguments[0].click();", save_btn
        )

        # Assert updated rate in table
        wait.until(EC.url_contains("/compare/"))
        matrix = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "matrix-table"))
        )
        self.assertIn("5.500%", matrix.text)

        # 5. Delete Option
        del_btn = self.driver.find_element(By.LINK_TEXT, "Delete")
        del_btn.click()

        wait.until(EC.url_contains("/delete/"))
        confirm_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-danger"))
        )
        confirm_btn.click()

        # Assert option removed
        wait.until(EC.url_contains("/compare/"))
        matrix = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "matrix-table"))
        )
        self.assertNotIn("Transcribed LE: 5.75% / 1 pt", matrix.text)

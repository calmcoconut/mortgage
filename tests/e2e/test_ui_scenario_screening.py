import time
import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestScenarioScreeningE2E(StaticLiveServerTestCase):
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

    def test_scenario_creation_and_live_htmx_screening(self):
        wait = WebDriverWait(self.driver, 10)
        self.driver.get(f"{self.live_server_url}/scenarios/new/")

        # Fill in Scenario Name
        name_input = wait.until(EC.presence_of_element_located((By.NAME, "name")))
        name_input.clear()
        name_input.send_keys("Automated Test Purchase")

        # Fill in Property Value and Loan Amount (80% LTV)
        prop_val = self.driver.find_element(By.ID, "id_property_value")
        prop_val.clear()
        prop_val.send_keys("500000")

        loan_amt = self.driver.find_element(By.ID, "id_loan_amount")
        loan_amt.clear()
        loan_amt.send_keys("400000")

        # Down payment
        down_pmt = self.driver.find_element(By.NAME, "down_payment")
        down_pmt.clear()
        down_pmt.send_keys("100000")

        # Fill in Income and Debts
        income = self.driver.find_element(By.ID, "id_gross_monthly_income")
        income.clear()
        income.send_keys("10000")

        debts = self.driver.find_element(By.ID, "id_recurring_monthly_debts")
        debts.clear()
        debts.send_keys("500")

        # Trigger HTMX request
        self.driver.execute_script("htmx.trigger('#id_property_value', 'input');")
        time.sleep(0.6)

        # Wait for HTMX reactive preview to update with LTV: 80.0%
        wait.until(lambda d: "80.0%" in d.find_element(By.ID, "screening-preview-container").text)
        container = self.driver.find_element(By.ID, "screening-preview-container")
        self.assertIn("LIKELY", container.text)

        # Now change loan amount to 490000 (98% LTV -> UNLIKELY for conventional)
        loan_amt.clear()
        loan_amt.send_keys("490000")
        self.driver.execute_script("htmx.trigger('#id_loan_amount', 'input');")
        time.sleep(0.6)

        wait.until(lambda d: "UNLIKELY" in d.find_element(By.ID, "screening-preview-container").text)

        # Change back to 400000 and submit
        loan_amt.clear()
        loan_amt.send_keys("400000")
        
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", submit_btn)

        wait.until(EC.url_contains("/compare/"))
        header = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page-title")))
        self.assertIn("Compare", header.text)

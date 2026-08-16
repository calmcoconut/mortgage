import json

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from web.models import ScenarioModel


class TestJsonImportEditE2E(StaticLiveServerTestCase):
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

    def test_json_import_and_edit_full_workflow(self):
        wait = WebDriverWait(self.driver, 10)

        # 1. Start from Scenario List page
        self.driver.get(f"{self.live_server_url}/")

        import_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "btnImportJson"))
        )
        import_btn.click()

        wait.until(EC.url_contains("/scenarios/import-json/"))

        # 2. Enter JSON payload
        payload = {
            "scenario": {
                "name": "E2E JSON Imported Scenario",
                "purpose": "purchase",
                "property_value": 750000,
                "loan_amount": 600000,
                "down_payment": 150000,
                "fico_band": "760+",
                "occupancy": "primary",
                "property_type": "single_family",
                "state": "CA",
                "program": "conventional",
                "term_months": 360,
                "expected_horizon_months": 84,
                "gross_monthly_income": 16000,
                "recurring_monthly_debts": 1200,
            },
            "loan_options": [
                {
                    "label": "Option A (30Y Fixed 6.25%)",
                    "source_type": "loan_estimate",
                    "loan_amount": 600000,
                    "note_rate": 0.0625,
                    "apr": 0.0628,
                    "term_months": 360,
                    "points_pct": 0.0,
                    "lender_fees": 1200,
                },
                {
                    "label": "Option B (30Y Fixed 5.875% 2pts)",
                    "source_type": "loan_estimate",
                    "loan_amount": 600000,
                    "note_rate": 0.05875,
                    "apr": 0.0602,
                    "term_months": 360,
                    "points_pct": 0.0200,
                    "lender_fees": 800,
                },
            ],
        }

        # Clear and fill textarea
        json_area = self.driver.find_element(By.ID, "jsonPayloadArea")
        self.driver.execute_script(
            "arguments[0].value = arguments[1];", json_area, json.dumps(payload, indent=2)
        )

        submit_btn = self.driver.find_element(By.ID, "btnSubmitImport")
        submit_btn.click()

        # 3. Assert redirected to compare page for imported scenario
        wait.until(EC.url_contains("/compare/"))
        header = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "page-title"))
        )
        self.assertIn("Compare", header.text)

        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        self.assertIn("E2E JSON Imported Scenario", body_text)
        self.assertIn("Option A (30Y Fixed 6.25%)", body_text)
        self.assertIn("Option B (30Y Fixed 5.875% 2pts)", body_text)

        # 4. Click "Edit JSON"
        edit_json_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "btnEditJson"))
        )
        edit_json_btn.click()

        wait.until(EC.url_contains("/edit-json/"))

        # 5. Modify scenario via JSON editor
        edit_area = wait.until(
            EC.presence_of_element_located((By.ID, "jsonPayloadArea"))
        )
        current_val = edit_area.get_attribute("value")
        self.assertIn("E2E JSON Imported Scenario", current_val)

        modified_payload = json.loads(current_val)
        modified_payload["scenario"]["name"] = "E2E JSON Scenario (Modified)"
        modified_payload["scenario"]["property_value"] = 800000
        modified_payload["scenario"]["loan_amount"] = 640000

        self.driver.execute_script(
            "arguments[0].value = arguments[1];",
            edit_area,
            json.dumps(modified_payload, indent=2),
        )

        save_btn = self.driver.find_element(By.ID, "btnSaveJson")
        save_btn.click()

        # 6. Verify redirected back to compare with modified data
        wait.until(EC.url_contains("/compare/"))
        updated_text = self.driver.find_element(By.TAG_NAME, "body").text
        self.assertIn("E2E JSON Scenario (Modified)", updated_text)

        scenario = ScenarioModel.objects.get(name="E2E JSON Scenario (Modified)")
        self.assertEqual(scenario.property_value, 800000)
        self.assertEqual(scenario.loan_amount, 640000)

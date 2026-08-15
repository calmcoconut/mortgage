from datetime import timedelta
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from web.models import RateApiCacheModel, RateApiSnapshotModel


class TestDataSourcesE2E(StaticLiveServerTestCase):
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

    def test_data_sources_table_filter_and_sort_interactions(self):
        # Create diverse snapshot data
        RateApiSnapshotModel.objects.create(
            lender="Safe 1 Credit Union",
            product_type="30-year-fixed",
            product_name="30-Year Fixed Conforming",
            rate=Decimal("6.000"),
            apr=Decimal("6.000"),
            points=Decimal("0.000"),
            state="CA",
            confidence_score=Decimal("0.950"),
            eligibility_summary="Community charter in CA",
        )
        RateApiSnapshotModel.objects.create(
            lender="Coast Central Credit Union",
            product_type="7-1-arm",
            product_name="7/1 Adjustable Rate Mortgage",
            rate=Decimal("5.375"),
            apr=Decimal("5.450"),
            points=Decimal("0.000"),
            state="CA",
            confidence_score=Decimal("0.900"),
            eligibility_summary="Humboldt, Del Norte, Trinity counties",
        )
        RateApiSnapshotModel.objects.create(
            lender="United Local Credit Union",
            product_type="10-year-fixed",
            product_name="10-Year Fixed Conforming",
            rate=Decimal("5.250"),
            apr=Decimal("5.300"),
            points=Decimal("0.000"),
            state="CA",
            confidence_score=Decimal("0.850"),
            eligibility_summary="Fresno and Madera counties",
        )

        RateApiCacheModel.objects.create(
            cache_key="CA_purchase_680000_360",
            query_state="CA",
            query_intent="purchase",
            query_amount_bucket=675000,
            query_term_months=360,
            response_payload={"actions": [{"offers": [{"credit_union_name": "Safe 1 CU"}]}]},
            expires_at=timezone.now() + timedelta(days=7),
        )

        driver = self.driver
        driver.get(f"{self.live_server_url}/data-sources/")

        wait = WebDriverWait(driver, 10)
        wait.until(
            EC.presence_of_element_located((By.ID, "rawDataTable"))
        )

        # 1. Verify initial render has 3 rows
        rows = driver.find_elements(By.CSS_SELECTOR, "#rawDataTableBody tr")
        assert len(rows) == 3

        # 2. Filter by Product: 7/1 ARM
        product_select = Select(driver.find_element(By.ID, "snapshotProductFilter"))
        product_select.select_by_value("7-1-arm")

        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#rawDataTableBody tr")) == 1)
        filtered_row = driver.find_element(By.CSS_SELECTOR, "#rawDataTableBody tr")
        assert "Coast Central Credit Union" in filtered_row.text
        assert "5.375%" in filtered_row.text

        # 3. Reset product and search for "United"
        product_select.select_by_value("all")
        search_input = driver.find_element(By.ID, "snapshotSearchInput")
        search_input.clear()
        search_input.send_keys("United")

        # 4. Click Reset and test sorting by Rate
        btn_reset = driver.find_element(By.ID, "btnResetFilters")
        btn_reset.click()
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#rawDataTableBody tr")) == 3)

        rate_header = driver.find_element(By.CSS_SELECTOR, 'th[data-sort="rate"]')
        # Initial sort was rate ascending (5.250% lowest first: United Local CU)
        # Clicking header toggles to descending (6.000% highest first: Safe 1 CU)
        rate_header.click()
        first_row_text = driver.find_element(By.CSS_SELECTOR, "#rawDataTableBody tr:first-child").text
        assert "Safe 1 Credit Union" in first_row_text

        # 5. Switch to Decision Cache tab
        tab_cache = driver.find_element(By.ID, "tabCacheBtn")
        tab_cache.click()

        cache_section = driver.find_element(By.ID, "sectionCache")
        assert cache_section.is_displayed()
        assert "CA_purchase_680000_360" in cache_section.text

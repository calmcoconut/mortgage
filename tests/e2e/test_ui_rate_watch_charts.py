from datetime import date, timedelta
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from web.models import BenchmarkPointModel, RateApiSnapshotModel


class TestRateWatchChartsE2E(StaticLiveServerTestCase):
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
        today = date.today()
        five_years_ago = today - timedelta(days=365 * 5)
        BenchmarkPointModel.objects.create(
            series="MORTGAGE30US",
            observed_on=five_years_ago,
            value=Decimal("3.100"),
        )
        BenchmarkPointModel.objects.create(
            series="MORTGAGE30US",
            observed_on=today,
            value=Decimal("6.500"),
        )
        BenchmarkPointModel.objects.create(
            series="MORTGAGE15US",
            observed_on=five_years_ago,
            value=Decimal("2.400"),
        )
        BenchmarkPointModel.objects.create(
            series="MORTGAGE15US",
            observed_on=today,
            value=Decimal("5.750"),
        )

        RateApiSnapshotModel.objects.create(
            lender="Safe 1 Credit Union",
            state="CA",
            product_type="30-year-fixed",
            product_name="30-Year Fixed Rate",
            rate=Decimal("6.000"),
            apr=Decimal("6.000"),
            points=Decimal("0.000"),
            observed_on=today,
        )
        RateApiSnapshotModel.objects.create(
            lender="Coast Central Credit Union",
            state="CA",
            product_type="5-1-arm",
            product_name="5/1 ARM",
            rate=Decimal("5.125"),
            apr=Decimal("5.250"),
            points=Decimal("0.000"),
            observed_on=today,
        )

    def test_rate_watch_all_three_charts_and_kpis(self):
        self.driver.get(f"{self.live_server_url}/rate-watch/")
        wait = WebDriverWait(self.driver, 10)

        # 1. Assert Title and KPI headers
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page-title")))
        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        self.assertIn("Rate Watch & Market Intelligence", body_text)
        self.assertIn("Credit Union Spread vs FRED 30Y", body_text)
        self.assertIn("RateAPI Monthly Quota Guard", body_text)

        # 2. Assert Canvas Elements Rendered
        fred_canvas = wait.until(EC.presence_of_element_located((By.ID, "fredChart")))
        self.assertTrue(fred_canvas.is_displayed())

        prod_canvas = wait.until(EC.presence_of_element_located((By.ID, "productCurveChart")))
        self.assertTrue(prod_canvas.is_displayed())

        disp_canvas = wait.until(EC.presence_of_element_located((By.ID, "dispersionChart")))
        self.assertTrue(disp_canvas.is_displayed())

        # 3. Assert Chart.js instances exist on window
        has_fred = self.driver.execute_script("return !!window.fredChart;")
        has_prod = self.driver.execute_script("return !!window.productCurveChart;")
        has_disp = self.driver.execute_script("return !!window.dispersionChart;")
        self.assertTrue(has_fred)
        self.assertTrue(has_prod)
        self.assertTrue(has_disp)

        # 4. Assert short label formatting and ample Y-axis margin to prevent text clipping
        disp_labels = self.driver.execute_script("return window.dispersionChart.data.labels;")
        self.assertIn("Safe 1 CU (30Y Fixed)", disp_labels)
        self.assertIn("Coast Central CU (5/1 ARM)", disp_labels)

        # 5. Assert Zoom & Pan is enabled on 5-Year FRED timeline chart only, and disabled on secondary charts
        fred_zoom_enabled = self.driver.execute_script(
            "return !!(window.fredChart.options.plugins && window.fredChart.options.plugins.zoom && window.fredChart.options.plugins.zoom.pan && window.fredChart.options.plugins.zoom.pan.enabled);"
        )
        prod_zoom_disabled = self.driver.execute_script(
            "return window.productCurveChart.options.plugins?.zoom === false || !window.productCurveChart.options.plugins?.zoom?.pan?.enabled;"
        )
        disp_zoom_disabled = self.driver.execute_script(
            "return window.dispersionChart.options.plugins?.zoom === false || !window.dispersionChart.options.plugins?.zoom?.pan?.enabled;"
        )
        self.assertTrue(fred_zoom_enabled, "FRED timeline chart should have zoom & pan enabled")
        self.assertTrue(prod_zoom_disabled, "Product curve chart should have zoom & pan disabled")
        self.assertTrue(disp_zoom_disabled, "Dispersion chart should have zoom & pan disabled")

        # 6. Assert FRED timeline extends 5 years back
        first_date = self.driver.execute_script("return window.fredChart.data.labels[0];")
        expected_year_prefix = str((date.today() - timedelta(days=365 * 5)).year)
        self.assertTrue(
            expected_year_prefix in first_date,
            f"FRED chart timeline should extend 5 years back to {expected_year_prefix}, got {first_date}",
        )

        # 7. Assert Granularity Unit Toggle (Weekly, Monthly Avg, Quarterly Avg)
        weekly_btn = self.driver.find_element(By.ID, "granularityWeeklyBtn")
        monthly_btn = self.driver.find_element(By.ID, "granularityMonthlyBtn")
        quarterly_btn = self.driver.find_element(By.ID, "granularityQuarterlyBtn")

        # Test switching to Quarterly
        quarterly_btn.click()
        q_label = self.driver.execute_script("return window.fredChart.data.labels[0];")
        self.assertTrue(q_label.startswith("Q"), f"Quarterly label should start with 'Q', got {q_label}")

        # Test switching to Weekly
        weekly_btn.click()
        w_label = self.driver.execute_script("return window.fredChart.data.labels[0];")
        self.assertTrue("-" in w_label, f"Weekly label should be date format YYYY-MM-DD, got {w_label}")

        # Test switching back to Monthly
        monthly_btn.click()
        m_label = self.driver.execute_script("return window.fredChart.data.labels[0];")
        self.assertTrue(expected_year_prefix in m_label, f"Monthly label should contain {expected_year_prefix}, got {m_label}")

        # 8. Assert Dispersion canvas cursor is default and Table view toggle enables selectable text
        disp_cursor = self.driver.execute_script("return window.getComputedStyle(document.getElementById('dispersionChart')).cursor;")
        self.assertNotEqual(disp_cursor, "grab", "Dispersion chart canvas should not have grab cursor")

        disp_table_btn = self.driver.find_element(By.ID, "dispersionTableBtn")
        disp_table_btn.click()

        table_wrapper = self.driver.find_element(By.ID, "dispersionTableWrapper")
        self.assertTrue(table_wrapper.is_displayed(), "Dispersion table view should be visible")
        self.assertIn("Safe 1 Credit Union", table_wrapper.text)

        disp_chart_btn = self.driver.find_element(By.ID, "dispersionChartBtn")
        disp_chart_btn.click()
        self.assertTrue(disp_canvas.is_displayed(), "Dispersion chart view should be visible after toggle back")



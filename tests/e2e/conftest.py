import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


@pytest.fixture(scope="function")
def driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1600,1000")
    chrome_options.add_argument("--remote-debugging-port=9222")

    try:
        service = Service(ChromeDriverManager().install())
        drv = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        # Fallback to system chrome
        drv = webdriver.Chrome(options=chrome_options)

    drv.implicitly_wait(4)
    yield drv
    drv.quit()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def init_driver():
    options = Options()

    # ✅ MUST USE THIS (not --headless)
    options.add_argument("--headless=new")

    # stability
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # anti-detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)

    return driver
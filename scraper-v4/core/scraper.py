import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_google(query, driver):
    try:
        url = "https://duckduckgo.com/?q=" + query
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='result-title-a']"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")

        results = []

        for item in soup.select("a[data-testid='result-title-a']"):
            title = item.get_text(strip=True)
            link = item.get("href")

            if title and link:
                results.append({
                    "title": title,
                    "link": link
                })

        if results:
            return results[0]

        return {"title": "N/A", "link": "#"}

    except Exception as e:
        print("[ERROR]", e)
        return None

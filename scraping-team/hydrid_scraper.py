import os
import json
import logging
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
import undetected_chromedriver as uc

# ==================== JUNIOR CONFIGURATION ====================
CONFIG = {
    "JSON_TASKS": "requests.json",
    "GOOGLE_SHEET_ID": "14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg",
    "SERVICE_ACCOUNT": "service-account.json",
    "THREADS": 10,               # Number of detail pages to scrape at once
    "MAX_PAGES_PER_TASK": 50,    # Default limit per area
    "LIST_PAGE_WAIT": 8,         # Seconds to wait for browser to load list
    "DETAIL_DELAY": (1.0, 2.5),  # Random delay between detail requests
}
# ==============================================================

class OptimizedHybridScraper:
    def __init__(self):
        self._setup_logging()
        self.gc = self._setup_gspread()
        self.session = requests.Session()
        self.driver = None

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[logging.FileHandler("scraper.log", encoding='utf-8'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_gspread(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(CONFIG["SERVICE_ACCOUNT"], scope)
            return gspread.authorize(creds).open_by_key(CONFIG["GOOGLE_SHEET_ID"])
        except Exception as e:
            self.logger.error(f"GSpread Setup Error: {e}")
            return None

    def _get_or_create_sheet(self, sheet_name):
        try:
            return self.gc.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.gc.add_worksheet(title=sheet_name, rows="100", cols="10")
            ws.append_row(["Area", "Name", "URL", "Address", "Access", "Phone"])
            return ws

    def init_browser(self):
        """Starts a browser that bypasses bot detection."""
        if self.driver: self.driver.quit()
        options = uc.ChromeOptions()
        # options.add_argument("--headless") # Uncomment to hide browser
        self.driver = uc.Chrome(options=options, version_main=122) 
        self.logger.info("🚀 Browser started and ready.")

    def sync_session(self):
        """Copies cookies from Browser to Requests session for speed."""
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])
        self.session.headers.update({
            "User-Agent": self.driver.execute_script("return navigator.userAgent"),
            "Referer": "https://beauty.hotpepper.jp/"
        })

    def extract_links(self):
        """Finds all salon links on the current browser page."""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        # Selector for Hot Pepper Salon links
        links = []
        for a in soup.select("h3.slnHdrAlphabet a, h3.slnHdr a"):
            href = a.get('href')
            if href:
                links.append(href.split('?')[0])
        return list(set(links))

    def fetch_detail(self, url, area_name):
        """Fast worker that scrapes one salon using Requests."""
        try:
            time.sleep(random.uniform(*CONFIG["DETAIL_DELAY"]))
            res = self.session.get(url, timeout=15)
            if res.status_code != 200: return None

            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Hot Pepper Selectors (Junior: Change these if the site changes)
            name = soup.select_one(".nameDetail") or soup.select_one("h1")
            addr = soup.find("th", string="住所")
            access = soup.find("th", string="アクセス")
            
            return [
                area_name,
                name.get_text(strip=True) if name else "N/A",
                url,
                addr.find_next_sibling("td").get_text(strip=True) if addr else "",
                access.find_next_sibling("td").get_text(strip=True) if access else "",
                "Scraped: " + time.strftime("%Y-%m-%d")
            ]
        except Exception as e:
            self.logger.debug(f"Detail error on {url}: {e}")
            return None

    def run(self):
        with open(CONFIG["JSON_TASKS"], 'r', encoding='utf-8') as f:
            tasks = json.load(f)

        self.init_browser()

        for task in tasks:
            area = task['area']
            base_url = task['url']
            sheet_name = task['sheet']
            
            self.logger.info(f"🔎 Starting Area: {area}")
            worksheet = self._get_or_create_sheet(sheet_name)
            
            for page in range(1, CONFIG["MAX_PAGES_PER_TASK"] + 1):
                page_url = f"{base_url}PN{page}/" if "salon/" in base_url else f"{base_url}?PN={page}"
                
                self.driver.get(page_url)
                time.sleep(CONFIG["LIST_PAGE_WAIT"]) # Wait for Cloudflare/Loading
                
                links = self.extract_links()
                if not links:
                    self.logger.info(f"Done with {area} (No more links found).")
                    break

                self.sync_session()
                page_results = []
                
                # Multi-threaded detail scraping
                with ThreadPoolExecutor(max_workers=CONFIG["THREADS"]) as executor:
                    futures = [executor.submit(self.fetch_detail, url, area) for url in links]
                    for future in as_completed(futures):
                        res = future.result()
                        if res: page_results.append(res)

                if page_results:
                    worksheet.append_rows(page_results)
                    self.logger.info(f"✅ Saved {len(page_results)} salons from {area} - Page {page}")

        self.driver.quit()
        self.logger.info("🏁 ALL TASKS COMPLETED.")

if __name__ == '__main__':
    scraper = OptimizedHybridScraper()
    scraper.run()
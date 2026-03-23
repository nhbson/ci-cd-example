import os
import re
import requests
import gspread
import random
from time import sleep
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from oauth2client.service_account import ServiceAccountCredentials
from chatwork import Chatwork

# =========================================================
# JUNIOR CONFIGURATION AREA (Update this for each request)
# =========================================================
CONFIG = {
    "TARGET_SITE": "BEAUTY", 
    "SHEET_ID": "14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg",
    "SHEET_NAME": "東北ヘアサロン",  # Changed as requested
    "AREAS": {
        "青森・八戸・弘前": "https://beauty.hotpepper.jp/svcSE/macEF/salon/", # Tohoku URL
    },
    # Mapping: [Excel Header Name, Key to find on Website]
    "MAPPING": [
        ["店舗名", "店名"], 
        ["会社住所", "住所"],
        ["電話番号", "電話"] 
    ],
    "MAX_WORKERS": 5  # Keep low to avoid being blocked by HotPepper
}
# =========================================================

def site_scraping():
    with Scraper() as scraper:
        for area_name, area_url in CONFIG["AREAS"].items():
            print(f"--- Starting Process: {area_name} ---")
            
            # 1. Get all shop URLs from list pages
            urls = scraper.get_job_links(area_url)
            
            if not urls:
                print("No shop links found. The website might be blocking us. Check headers/IP.")
                continue

            # 2. Get shop details (Names, Addresses, Phone Numbers)
            print(f"Found {len(urls)} shops. Extracting details...")
            jobs = scraper.get_jobs(urls, CONFIG["SHEET_NAME"])
            
            # 3. Update Google Sheets
            scraper.update_spreadsheet(jobs, CONFIG["SHEET_NAME"])

class Scraper():
    def __init__(self):
        # Auth Chatwork
        self.chatwork = Chatwork(
            os.environ.get('CHATWORK_RID', '258334146'),
            os.environ.get('METHOD_NAME', 'hotpepper'),
            os.environ.get('CHATWORK_TOKEN', 'aa07226db4f595140cde0323e30948a7')
        )
        # Auth Google Sheets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('service-account.json', scope)
        self.gc = gspread.authorize(creds)
        self.sheet_id = CONFIG["SHEET_ID"]
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, trace): self.session.close()

    def get_job_links(self, area_url):
        """Finds all shop URLs by scanning result pages (PN1, PN2...)."""
        res = self.session.get(area_url)
        soup = BeautifulSoup(res.content, 'html.parser')
        count_elem = soup.select_one(".numberOfResult") or soup.select_one(".fcLRed")
        
        if not count_elem: return []
        
        all_nums = int(re.search(r'\d+', count_elem.text.replace(',', '')).group())
        pages = (all_nums // 20) + 1
        print(f"Total: {all_nums} shops across {pages} pages.")

        links_found = set()
        list_urls = [f"{area_url.rstrip('/')}/PN{i}.html" if i > 1 else area_url for i in range(1, pages + 1)]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(lambda u: self.session.get(u).content, u) for u in list_urls]
            for i, future in enumerate(as_completed(futures)):
                s = BeautifulSoup(future.result(), 'html.parser')
                for a in s.select(".slnName a, .shopDetailStoreName a"):
                    href = a.get('href')
                    if href:
                        url = href if href.startswith('http') else "https://beauty.hotpepper.jp" + href
                        links_found.add(url.split('?')[0])
                print(f"Scanned list page {i+1}/{pages}")
        return list(links_found)

    def get_jobs(self, urls, sheet_name):
        """Scrapes detailed info. Includes retry logic and sub-page phone scraping."""
        existing_urls = self.get_existing_urls(sheet_name)
        header = ["URL"] + [c[0] for c in CONFIG["MAPPING"]]
        results = [header]

        def process_url(url):
            if any(url in s for s in existing_urls): return None
            
            # Retry up to 3 times per shop to ensure data isn't missed
            for attempt in range(3):
                try:
                    sleep(random.uniform(0.5, 1.2)) # Anti-bot delay
                    res = self.session.get(url, timeout=15)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    
                    info_map = {}
                    for tr in soup.select("table tr"):
                        th, td = tr.find("th"), tr.find("td")
                        if th and td:
                            info_map[th.get_text(strip=True)] = td.get_text(strip=True)

                    title_elem = soup.select_one(".detailTitle")
                    web_title = title_elem.get_text(strip=True) if title_elem else ""

                    row = [url]
                    for header_name, key in CONFIG["MAPPING"]:
                        # Look for key (like '住所' or '店名') in the info table
                        val = next((v for k, v in info_map.items() if key in k), "")
                        
                        # Fallback for Shop Name
                        if "店舗名" in header_name and not val: val = web_title
                        
                        # Fallback for Hidden Phone Number
                        if "電話" in header_name and (not val or "番号" in val):
                            val = self.scrape_real_phone_from_link(soup)
                        
                        row.append(val.strip().replace('\xa0', ' '))
                    
                    if row[1] or row[2]: # Ensure we didn't get a blank page
                        return row
                except:
                    continue
            return None

        with ThreadPoolExecutor(max_workers=CONFIG["MAX_WORKERS"]) as executor:
            futures = [executor.submit(process_url, u) for u in urls]
            for i, f in enumerate(as_completed(futures)):
                res = f.result()
                if res: results.append(res)
                if (i+1) % 10 == 0: print(f"Scraped {i+1}/{len(urls)} details...")
        return results

    def scrape_real_phone_from_link(self, soup):
        """Clicks the phone link, visits the sub-page, and gets digits from td.fs16.b"""
        tel_link = soup.find('a', href=re.compile("/tel/")) or \
                   soup.find('a', onclick=re.compile("telinfo|doTelPopup"))
        if not tel_link: return ""
        
        try:
            target_url = tel_link['href']
            if not target_url.startswith('http'):
                target_url = "https://beauty.hotpepper.jp" + target_url
            
            res = self.session.get(target_url, timeout=10)
            tel_soup = BeautifulSoup(res.content, 'html.parser')
            
            # Target the specific cell shown in your HTML snippet
            phone = tel_soup.select_one("td.fs16.b") or tel_soup.select_one(".telephoneNumber")
            return phone.get_text(strip=True) if phone else ""
        except: pass
        return ""

    def get_existing_urls(self, sheet_name):
        try:
            worksheet = self.gc.open_by_key(self.sheet_id).worksheet(sheet_name)
            return [row[0] for row in worksheet.get_all_values() if row]
        except: return []

    def update_spreadsheet(self, jobs, sheet_name):
        if len(jobs) <= 1: return

        try:
            sheet = self.gc.open_by_key(self.sheet_id)
            try: ws = sheet.worksheet(sheet_name)
            except: ws = sheet.add_worksheet(title=sheet_name, rows="2000", cols="10")
            
            existing = [r[0] for r in ws.get_all_values() if r]
            new_rows = [j for j in jobs if j[0] not in existing and j[0] != "URL"]

            if not existing: ws.append_row(jobs[0]) # Header
            if new_rows:
                ws.append_rows(new_rows)
                print(f"Added {len(new_rows)} shops to {sheet_name}.")
                self.chatwork.send_alert(True, f"【{sheet_name}】に{len(new_rows)}件追加しました。")
        except Exception as e: print(f"Spreadsheet error: {e}")

if __name__ == '__main__':
    # Ensure PC clock is synced for Auth
    site_scraping()
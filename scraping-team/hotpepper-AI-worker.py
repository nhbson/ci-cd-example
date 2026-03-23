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
# JUNIOR CONFIGURATION AREA
# =========================================================
CONFIG = {
    "TARGET_SITE": "BEAUTY", 
    "SHEET_ID": "14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg",
    "SHEET_NAME": "北信越ヘアサロンNewOpen",
    "AREAS": {
        "福井": "https://beauty.hotpepper.jp/svcSH/macHG/salon/",
    },
    # Columns: [Excel Header Name, Key to find on Website]
    "MAPPING": [
        ["店舗名", "店名"], 
        ["会社住所", "住所"],
        ["電話番号", "電話"] 
    ],
    "MAX_WORKERS": 5  # Reduced to prevent blocking
}
# =========================================================

def site_scraping():
    with Scraper() as scraper:
        for area_name, area_url in CONFIG["AREAS"].items():
            print(f"--- Starting: {area_name} ---")
            urls = scraper.get_job_links(area_url)
            
            if not urls:
                print("Could not find shop links. The site might be blocking us.")
                continue

            print(f"Found {len(urls)} shops. Extraction started...")
            jobs = scraper.get_jobs(urls, CONFIG["SHEET_NAME"])
            scraper.update_spreadsheet(jobs, CONFIG["SHEET_NAME"])

class Scraper():
    def __init__(self):
        # Auth Chatwork
        self.chatwork = Chatwork(
            os.environ.get('CHATWORK_RID', '258334146'),
            os.environ.get('METHOD_NAME', 'hotpepper'),
            os.environ.get('CHATWORK_TOKEN', 'aa07226db4f595140cde0323e30948a7')
        )
        # Auth Sheets
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
        """Fetches all individual shop URLs from the list pages."""
        res = self.session.get(area_url)
        soup = BeautifulSoup(res.content, 'html.parser')
        count_elem = soup.select_one(".numberOfResult") or soup.select_one(".fcLRed")
        
        if not count_elem: return []
        
        all_nums = int(re.search(r'\d+', count_elem.text.replace(',', '')).group())
        pages = (all_nums // 20) + 1
        
        links_found = set()
        list_urls = [f"{area_url.rstrip('/')}/PN{i}.html" if i > 1 else area_url for i in range(1, pages + 1)]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(lambda u: self.session.get(u).content, u) for u in list_urls]
            for future in as_completed(futures):
                s = BeautifulSoup(future.result(), 'html.parser')
                for a in s.select(".slnName a, .shopDetailStoreName a"):
                    href = a.get('href')
                    if href:
                        url = href if href.startswith('http') else "https://beauty.hotpepper.jp" + href
                        links_found.add(url.split('?')[0])
        return list(links_found)

    def get_jobs(self, urls, sheet_name):
        """Extracts table data with retry logic and enhanced phone scraping."""
        existing_urls = self.get_existing_urls(sheet_name)
        header = ["URL"] + [c[0] for c in CONFIG["MAPPING"]]
        results = [header]

        def process_url(url):
            if any(url in s for s in existing_urls): return None
            
            # Retry logic: tries 3 times if data is empty
            for attempt in range(3):
                try:
                    sleep(random.uniform(0.5, 1.5))
                    res = self.session.get(url, timeout=15)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    
                    # 1. Map all tables
                    info_map = {}
                    for tr in soup.select("table tr"):
                        th, td = tr.find("th"), tr.find("td")
                        if th and td:
                            info_map[th.get_text(strip=True)] = td.get_text(strip=True)

                    # 2. Get Shop Name from Title
                    title_elem = soup.select_one(".detailTitle")
                    web_title = title_elem.get_text(strip=True) if title_elem else ""

                    row = [url]
                    for header_name, key in CONFIG["MAPPING"]:
                        # Find value in map (partial match supported)
                        val = next((v for k, v in info_map.items() if key in k), "")
                        
                        if "店舗名" in header_name and not val: val = web_title
                        
                        # PHONE LOGIC
                        if "電話" in header_name:
                            # If table is empty or says "番号を表示", go to the hidden link
                            if not val or "番号" in val:
                                val = self.scrape_hidden_phone(soup)
                        
                        row.append(val.strip().replace('\xa0', ' '))
                    
                    # If we got at least the name or address, return it
                    if row[1] or row[2]:
                        return row
                except Exception as e:
                    print(f"Attempt {attempt+1} failed for {url}")
                    continue
            return None

        with ThreadPoolExecutor(max_workers=CONFIG["MAX_WORKERS"]) as executor:
            futures = [executor.submit(process_url, u) for u in urls]
            for i, f in enumerate(as_completed(futures)):
                res = f.result()
                if res: results.append(res)
                if (i+1) % 10 == 0: print(f"Progress: {i+1}/{len(urls)} scraped.")
        return results

    def scrape_hidden_phone(self, soup):
        """Visits the /tel/ sub-page and captures the number from td.fs16.b"""
        tel_link = soup.find('a', href=re.compile("/tel/")) or \
                   soup.find('a', onclick=re.compile("telinfo|doTelPopup"))
        if not tel_link: return ""
        
        try:
            target_url = tel_link['href']
            if not target_url.startswith('http'):
                target_url = "https://beauty.hotpepper.jp" + target_url
            
            res = self.session.get(target_url, timeout=10)
            tel_soup = BeautifulSoup(res.content, 'html.parser')
            
            # Try to find the number in the specific td shown in your snippet
            phone = tel_soup.select_one("td.fs16.b") or tel_soup.select_one(".telephoneNumber")
            if phone:
                return phone.get_text(strip=True)
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
            except: ws = sheet.add_worksheet(title=sheet_name, rows="1000", cols="10")
            
            existing = [r[0] for r in ws.get_all_values() if r]
            new_rows = [j for j in jobs if j[0] not in existing and j[0] != "URL"]

            if not existing: ws.append_row(jobs[0])
            if new_rows:
                ws.append_rows(new_rows)
                print(f"Added {len(new_rows)} shops.")
                self.chatwork.send_alert(True, f"【{sheet_name}】に{len(new_rows)}件追加しました。")
        except Exception as e: print(f"Sheets Error: {e}")

if __name__ == '__main__':
    site_scraping()
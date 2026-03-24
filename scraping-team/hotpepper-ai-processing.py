import os
import re
import json
import requests
import gspread
import random
from time import sleep
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from chatwork import Chatwork

# =========================================================
# GLOBAL CONFIGURATION
# =========================================================
SHEET_ID = '14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg'
MAX_WORKERS = 5 

def site_scraping():
    # Load all requests from JSON
    if not os.path.exists('requests.json'):
        print("Error: requests.json file not found.")
        return

    with open('requests.json', 'r', encoding='utf-8') as f:
        request_list = json.load(f)

    with ScraperEngine() as engine:
        for req in request_list:
            print(f"\n>>> Processing: {req['area']} -> Sheet: {req['sheet']}")
            
            # 1. Get Salon URLs from result pages
            shop_links = engine.get_shop_links(req['url'])
            if not shop_links:
                print(f"Skipping {req['area']} - No links found. Check if URL is correct.")
                continue

            # 2. Extract Data (URL, Name, Address, Phone)
            print(f"Found {len(shop_links)} shops. Scraping details...")
            results = engine.get_shop_details(shop_links, req['sheet'])
            
            # 3. Save to Sheet (Creates sheet if missing)
            engine.update_spreadsheet(results, req['sheet'])

class ScraperEngine():
    def __init__(self):
        # Auth Chatwork
        self.chatwork = Chatwork(
            os.environ.get('CHATWORK_RID', '258334146'),
            os.environ.get('METHOD_NAME', 'hotpepper'),
            os.environ.get('CHATWORK_TOKEN', 'aa07226db4f595140cde0323e30948a7')
        )
        
        # Modern Auth to prevent JWT Signature Errors
        # Make sure 'service-account.json' is in the same folder and computer time is synced.
        try:
            self.gc = gspread.service_account(filename='service-account.json')
        except Exception as e:
            print(f"Auth Error: service-account.json missing or Time is not synced. {e}")
            raise

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, trace): self.session.close()

    def get_shop_links(self, area_url):
        """Finds all PN1, PN2... list pages and extracts shop URLs."""
        try:
            res = self.session.get(area_url, timeout=15)
            soup = BeautifulSoup(res.content, 'html.parser')
            count_elem = soup.select_one(".numberOfResult")
            if not count_elem: return []
            
            total = int(re.search(r'\d+', count_elem.text.replace(',', '')).group())
            pages = (total // 20) + 1
            
            links = set()
            base = area_url.rstrip('/')
            list_urls = [f"{base}/PN{i}.html" if i > 1 else area_url for i in range(1, pages + 1)]

            with ThreadPoolExecutor(max_workers=3) as exe:
                futures = [exe.submit(lambda u: self.session.get(u).content, u) for u in list_urls]
                for f in as_completed(futures):
                    s = BeautifulSoup(f.result(), 'html.parser')
                    for a in s.select(".slnName a"):
                        href = a.get('href')
                        if href:
                            # Build full URL and remove tracking parameters
                            full = href if href.startswith('http') else "https://beauty.hotpepper.jp" + href
                            links.add(full.split('?')[0])
            return list(links)
        except: return []

    def get_shop_details(self, urls, sheet_name):
        """Scrapes details from individual pages."""
        existing_urls = self.get_existing_urls(sheet_name)
        data_to_insert = [] 

        def scrape_one(url):
            if url in existing_urls: return None
            try:
                sleep(random.uniform(0.5, 1.2)) # Anti-bot delay
                res = self.session.get(url, timeout=15)
                soup = BeautifulSoup(res.content, 'html.parser')
                
                # Extract Name
                title = soup.select_one(".detailTitle")
                name = title.get_text(strip=True) if title else ""
                
                # Extract Table Info (Address)
                info = {}
                for tr in soup.select("table.slnDataTbl tr, table.infoTable tr"):
                    th, td = tr.find("th"), tr.find("td")
                    if th and td: info[th.get_text(strip=True)] = td.get_text(strip=True)
                
                address = info.get("住所", "").replace('\xa0', ' ')
                
                # Phone Logic: Follow link to get real digits
                phone = self.get_real_phone(soup)
                
                if name or address:
                    # Structure: [URL, Name, Address, Phone]
                    return [url, name, address, phone]
            except: pass
            return None

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            futures = [exe.submit(scrape_one, u) for u in urls]
            for i, f in enumerate(as_completed(futures)):
                res = f.result()
                if res: data_to_insert.append(res)
                if (i+1) % 20 == 0: print(f"Scraped {i+1}/{len(urls)} details...")
        
        return data_to_insert

    def get_real_phone(self, soup):
        """Visits the /tel/ sub-page to extract the number from td.fs16.b"""
        tel_link = soup.find('a', href=re.compile("/tel/"))
        if not tel_link: return ""
        try:
            target = tel_link['href']
            if not target.startswith('http'): target = "https://beauty.hotpepper.jp" + target
            res = self.session.get(target, timeout=10)
            s = BeautifulSoup(res.content, 'html.parser')
            num = s.select_one("td.fs16.b") or s.select_one(".telephoneNumber")
            return num.get_text(strip=True) if num else ""
        except: return ""

    def get_existing_urls(self, sheet_name):
        """Checks URL column to prevent duplicates."""
        try:
            ws = self.gc.open_by_key(SHEET_ID).worksheet(sheet_name)
            return [row[0] for row in ws.get_all_values() if row]
        except: return []

    def update_spreadsheet(self, results, sheet_name):
        """Saves data to Google Sheets. Adds URL as the first column."""
        if not results: 
            print(f"No new data for {sheet_name}.")
            return

        try:
            doc = self.gc.open_by_key(SHEET_ID)
            
            # Create sheet if it doesn't exist
            try:
                ws = doc.worksheet(sheet_name)
            except:
                print(f"Creating new sheet: {sheet_name}")
                ws = doc.add_worksheet(title=sheet_name, rows="2000", cols="6")
                # Set New Header (Now includes URL)
                ws.append_row(["URL", "店舗名", "会社住所", "電話番号"])
            
            existing = [r[0] for r in ws.get_all_values() if r]
            
            # Collect unique data (full list including URL)
            final_rows = [j for j in results if j[0] not in existing]

            if final_rows:
                ws.append_rows(final_rows)
                print(f"Successfully added {len(final_rows)} shops to {sheet_name}.")
                self.chatwork.send_alert(True, f"【{sheet_name}】に{len(final_rows)}件のデータを追加しました。")
            else:
                print("All shops already exist in the sheet.")

        except Exception as e:
            print(f"Spreadsheet Error: {e}")

if __name__ == '__main__':
    # Make sure computer clock is synced for Google Auth!
    site_scraping()
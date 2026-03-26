import os
import re
import json
import requests
import gspread
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from chatwork import Chatwork

# =========================================================
# SCRAPER ENGINE (Mynavi Tenshoku Logic)
# =========================================================
class UniversalEngine():
    def __init__(self, sheet_id):
        self.sheet_id = sheet_id
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })
        self.chatwork = Chatwork(os.environ.get('CHATWORK_RID'), os.environ.get('METHOD_NAME'), os.environ.get('CHATWORK_TOKEN'))
        self.gc = gspread.service_account(filename='service-account.json')

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, trace): self.session.close()

    def get_job_links(self, base_url):
        """Scrapes search results for job detail URLs."""
        try:
            res = self.session.get(base_url, timeout=15)
            soup = BeautifulSoup(res.content, 'html.parser')
            
            links = []
            if "tenshoku.mynavi.jp" in base_url:
                # Find total count
                try:
                    count_txt = soup.select_one(".m-listHeader_count > span").get_text()
                    total = int(re.search(r'\d+', count_txt.replace(',', '')).group())
                except: total = 50 
                
                pages = (total // 50) + 1
                for p in range(1, pages + 1):
                    p_url = base_url.replace("/?", f"/pg{p}/?") if "/?" in base_url else f"{base_url.rstrip('/')}/pg{p}/"
                    page_res = self.session.get(p_url)
                    page_soup = BeautifulSoup(page_res.content, 'html.parser')
                    for a in page_soup.select(".m-cassetteRecruit_content > a"):
                        links.append("https://tenshoku.mynavi.jp" + a['href'].split('?')[0])
            return list(set(links))
        except: return []

    def scrape_mynavi_details(self, url):
        """Logic: Scrapes details, skips MT-D, checks for Employee Interview."""
        try:
            res = self.session.get(url, timeout=15)
            soup = BeautifulSoup(res.content, 'html.parser')
            
            # 1. MT-Type Detection
            mt_result = "Unknown"
            body = soup.find("body")
            if body and body.has_attr('class'):
                body_class = "".join(body.get('class', []))
                mt_match = re.search(r'mtEx(MT-[SABCDE])', body_class)
                if mt_match: mt_result = mt_match.group(1)
            
            # Skip MT-D as requested
            if mt_result == "MT-D": return None

            # 2. Employee Interview Check (Must have at least 1)
            # Mynavi usually has a specific section/button for '社員インタビュー'
            interview_section = soup.find(string=re.compile("社員インタビュー"))
            if not interview_section: return None

            # 3. Extraction
            # Company Name
            company_elem = soup.select_one(".m-jobHeader_companyName")
            company_name = company_elem.get_text(strip=True) if company_elem else ""
            
            # Table info
            info_map = {}
            for tr in soup.select("table tr"):
                th, td = tr.find("th"), tr.find("td")
                if th and td: info_map[th.get_text(strip=True)] = td.get_text(strip=True)

            address = info_map.get("本社所在地", "")
            capital = info_map.get("資本金", "")
            employees = info_map.get("従業員数", "")
            
            # HP Link
            hp_elem = soup.find('a', string=re.compile("企業ホームページ"))
            hp_url = hp_elem['href'] if hp_elem else ""

            # Phone (Regex in '問い合わせ' section)
            phone = ""
            contact = soup.select_one(".m-jobContact") or soup.find(id="corpProfile")
            if contact:
                phone_match = re.search(r'\d{2,4}-\d{2,4}-\d{4}', contact.get_text())
                if phone_match: phone = phone_match.group()

            return [url, company_name, address, phone, hp_url, capital, employees, mt_result]
        except: return None

    def get_existing_urls(self, sheet_name):
        try:
            ws = self.gc.open_by_key(self.sheet_id).worksheet(sheet_name)
            return [row[0] for row in ws.get_all_values() if row]
        except: return []

    def update_spreadsheet(self, results, sheet_name):
        """Main thread handles the sheet update."""
        if not results: return 0
        doc = self.gc.open_by_key(self.sheet_id)
        try:
            ws = doc.worksheet(sheet_name)
        except:
            ws = doc.add_worksheet(title=sheet_name, rows="2000", cols="10")
            ws.append_row(["URL", "会社名", "住所", "電話番号", "企業HP", "資本金", "従業員数", "Python判別結果"])

        existing = [r[0] for r in ws.get_all_values() if r]
        final_rows = [j for j in results if j[0] not in existing]
        
        if final_rows:
            ws.append_rows(final_rows)
            return len(final_rows)
        return 0

# =========================================================
# UI (STREAMLIT)
# =========================================================
def main():
    st.set_page_config(page_title="Scraping Dashboard", layout="wide")
    st.title("📊 Recruitment Scraping Dashboard (Mynavi)")

    # Sidebar
    st.sidebar.header("Settings")
    sheet_id = st.sidebar.text_input("Spreadsheet ID", value="14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg")
    max_workers = st.sidebar.slider("Threads", 1, 10, 5)

    uploaded_file = st.file_uploader("Upload requests.json", type=['json'])

    if uploaded_file and st.button("🚀 Start Scraping"):
        request_list = json.load(uploaded_file)
        
        # UI Progress Area
        progress_text = st.empty()
        log_area = st.container()
        
        with st.status("Initializing Engine...", expanded=True) as status:
            with UniversalEngine(sheet_id) as engine:
                for req in request_list:
                    progress_text.markdown(f"### Current Task: {req['area']}")
                    
                    # 1. Get Links (Main Thread)
                    links = engine.get_job_links(req['url'])
                    st.write(f"🔗 Found {len(links)} shops in {req['area']}")
                    
                    if not links: continue

                    # 2. Extract Data (Threaded - No UI calls inside)
                    extracted_data = []
                    detail_progress = st.progress(0)
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as exe:
                        futures = [exe.submit(engine.scrape_mynavi_details, u) for u in links]
                        for i, f in enumerate(as_completed(futures)):
                            res = f.result()
                            if res: extracted_data.append(res)
                            # Update progress in Main Thread
                            detail_progress.progress((i + 1) / len(links))

                    # 3. Update Sheets (Main Thread)
                    count = engine.update_spreadsheet(extracted_data, req['sheet'])
                    st.write(f"✅ Added {count} new shops to **{req['sheet']}**")

            status.update(label="Scraping Process Finished!", state="complete")
        
        st.balloons()
        st.success("All requests processed successfully.")

if __name__ == '__main__':
    main()
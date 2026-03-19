import json
import os
import re
import requests
from time import sleep
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from chatwork import Chatwork

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # script directory
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

# ---------------------
# Load config
# ---------------------
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

AREAS = CONFIG['areas']
SPREADSHEET_ID = CONFIG['spreadsheet_id']
MAX_THREADS = CONFIG.get('max_threads', 10)
CHATWORK_CONFIG = CONFIG['chatwork']

# ---------------------
# Google Sheet setup
# ---------------------
gc = gspread.authorize(
    ServiceAccountCredentials.from_json_keyfile_name(
        'service-account.json',
        ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )
)

# ---------------------
# Chatwork setup
# ---------------------
chatwork = Chatwork(
    CHATWORK_CONFIG['room_id'],
    CHATWORK_CONFIG['method_name'],
    CHATWORK_CONFIG['token']
)

# ---------------------
# Helper Functions
# ---------------------
def fetch_page(url):
    response = requests.get(url)
    return response.content

def extract_job_links(page_content, existing_links):
    soup = BeautifulSoup(page_content, 'html.parser')
    job_urls_elem = soup.select(".shopDetailStoreName > a")
    job_urls = [
        "https://www.hotpepper.jp/" + url_elem['href']
        for url_elem in job_urls_elem
        if 'href' in url_elem.attrs and "https://www.hotpepper.jp/" + url_elem['href'] not in existing_links
    ]
    return job_urls

def get_job_links(area_url):
    session = requests.Session()
    response = session.get(area_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    total_jobs = int(soup.select_one(".fcLRed.bold.fs18.padLR3").text.replace(',', ''))
    pages = (total_jobs // 20) + 1
    job_list_links = [f"{area_url}bgn{page}" for page in range(1, pages + 1)]

    job_links = set()
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(fetch_page, url): url for url in job_list_links}
        for future in as_completed(futures):
            try:
                page_content = future.result()
                job_links.update(extract_job_links(page_content, job_links))
            except Exception as e:
                print(f"Error fetching page {futures[future]}: {e}")
    return list(job_links)

def fetch_job_info(url, existing_urls):
    if url in existing_urls:
        return None

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        table_list = [
            {
                "column_list": ["総席数", "営業時間", "平均予算", "電話", "店名", "住所"],
                "th_selector": "table.infoTable tr th",
                "td_selector": "table.infoTable tr td"
            }
        ]

        job_data = []
        for table in table_list:
            th_tags = soup.select(table["th_selector"])
            td_tags = soup.select(table["td_selector"])
            headers = [th.get_text(strip=True) for th in th_tags]
            values = [td.get_text(strip=True) for td in td_tags]

            for col in table["column_list"]:
                if col in headers:
                    val = values[headers.index(col)]
                    # Filter small shops
                    if col == "総席数":
                        num = re.findall(r'\d+', val)
                        if num and int(num[0]) < 15:
                            return None
                    # Extract phone link
                    elif col == "電話":
                        tel_link = soup.find('a', onclick="customLinkLog('telinfo_disp')")['href']
                        tel_page = requests.get("https://www.hotpepper.jp/" + tel_link)
                        tel_soup = BeautifulSoup(tel_page.content, 'html.parser')
                        val = tel_soup.select_one('.telephoneNumber').get_text(strip=True)
                        sleep(1)
                    job_data.append(val)
        if job_data:
            job_data.insert(0, url)
        return job_data
    except Exception as e:
        print(f"Error fetching job {url}: {e}")
        return None

def update_sheet(sheet_name, jobs):
    worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
    existing_urls = [row[0] for row in worksheet.get_all_values()]
    new_jobs = [job for job in jobs if job and job[0] not in existing_urls]
    if new_jobs:
        worksheet.insert_rows(new_jobs, len(existing_urls) + 1)
        chatwork.send_alert(True, f"{sheet_name} updated with {len(new_jobs)} new jobs")
        print(f"{sheet_name} updated with {len(new_jobs)} jobs")

# ---------------------
# Main Scraping
# ---------------------
def site_scraping():
    for area_name, area_url in AREAS.items():
        print(f"Scraping {area_name}...")
        job_links = get_job_links(area_url)

        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(area_name)
        existing_urls = [row[0] for row in worksheet.get_all_values()]

        jobs = []
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [executor.submit(fetch_job_info, url, existing_urls) for url in job_links]
            for future in as_completed(futures):
                job = future.result()
                if job:
                    jobs.append(job)
        update_sheet(area_name, jobs)

if __name__ == '__main__':
    site_scraping()
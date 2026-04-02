import os
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
import undetected_chromedriver as uc

# ==================== CONFIG ====================
CONFIG = {
    "JSON_TASKS": "request-20260401.json",
    "GOOGLE_SHEET_ID": "14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg",
    "SERVICE_ACCOUNT": "service-account.json",
    "THREADS": 5,           # 安定性のために5スレッドを推奨
    "MAX_PAGES_PER_TASK": 60, # 1,473件(約50ページ)をカバー
    "LIST_PAGE_WAIT": 5,
    "DETAIL_DELAY": (1.5, 3.0),
}
# =================================================

class MachbaitoScraper:
    def __init__(self):
        self._setup_logging()
        self.gc = self._setup_gspread()
        self.session = requests.Session()
        self.driver = None
        self.seen_urls = set()

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
            self.logger.error(f"❌ GSpread設定エラー: {e}")
            return None

    def _get_or_create_sheet(self, sheet_name):
        try:
            return self.gc.worksheet(sheet_name)
        except:
            ws = self.gc.add_worksheet(title=sheet_name, rows="1000", cols="5")
            # リクエストに基づいたヘッダー
            ws.append_row(["会社名", "住所", "求人URL", "求人タイトル"])
            return ws

    def init_browser(self):
        if self.driver: self.driver.quit()
        options = uc.ChromeOptions()
        self.driver = uc.Chrome(options=options, version_main=146)
        self.logger.info("🚀 ブラウザを起動しました")

    def sync_session(self):
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])
        self.session.headers.update({
            "User-Agent": self.driver.execute_script("return navigator.userAgent"),
            "Referer": self.driver.current_url
        })

    def extract_links(self):
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        # 各求人カードのメインリンクを取得
        cards = soup.select("a.p-works-card-wrapper-link")
        links = []
        for a in cards:
            href = a.get("href")
            if href:
                full_url = "https://machbaito.jp" + href.split('?')[0]
                links.append(full_url)
        return list(set(links))

    # ==================== 詳細ページの抽出ロジック ====================
    def fetch_detail(self, url):
        if url in self.seen_urls: return None
        try:
            time.sleep(random.uniform(*CONFIG["DETAIL_DELAY"]))
            res = self.session.get(url, timeout=15)
            if res.status_code != 200: return None
            soup = BeautifulSoup(res.text, 'html.parser')

            # 1. 会社名 (店舗名) 
            # 企業情報のブロックにある名前を正確に取得
            company_el = soup.select_one(".p-detail-company-text-item-name p")
            company = company_el.get_text(strip=True) if company_el else "N/A"

            # 2. 住所
            # 勤務地・面接地のテキストを改行を保持（スペース置換）して取得
            address_el = soup.select_one(".js-detail-access")
            address = address_el.get_text(" ", strip=True) if address_el else "N/A"

            # 3. 求人タイトル
            # ご提示の「☆ランチタイム大募集...」の箇所（メイン見出し）を取得
            title_el = soup.select_one(".p-detail-main-heading")
            title = title_el.get_text(strip=True) if title_el else "N/A"

            self.seen_urls.add(url)
            # リクエスト順: A:会社名, B:住所, C:求人URL, D:タイトル
            return [company, address, url, title]

        except Exception as e:
            self.logger.debug(f"詳細取得エラー {url}: {e}")
            return None

    def run(self):
        with open(CONFIG["JSON_TASKS"], 'r', encoding='utf-8') as f:
            tasks = json.load(f)

        self.init_browser()

        for task in tasks:
            name = task.get('area', 'JobTask')
            base_url = task['url']
            sheet_name = task['sheet']

            self.logger.info(f"🔎 抽出開始: {name}")
            worksheet = self._get_or_create_sheet(sheet_name)
            self.seen_urls = set()

            for page in range(1, CONFIG["MAX_PAGES_PER_TASK"] + 1):
                connector = "&" if "?" in base_url else "?"
                page_url = f"{base_url}{connector}page={page}"
                
                self.logger.info(f"📄 ページ {page} をロード中...")
                self.driver.get(page_url)
                time.sleep(CONFIG["LIST_PAGE_WAIT"])

                links = self.extract_links()
                if not links:
                    self.logger.info("✅ 次のリンクが見つかりません。タスク完了。")
                    break

                self.sync_session()

                results = []
                with ThreadPoolExecutor(max_workers=CONFIG["THREADS"]) as executor:
                    futures = [executor.submit(self.fetch_detail, url) for url in links]
                    for future in as_completed(futures):
                        res = future.result()
                        if res: results.append(res)

                if results:
                    worksheet.append_rows(results)
                    self.logger.info(f"💾 ページ {page} から {len(results)} 件保存しました")

                # 次のページボタンがない場合は終了
                if "p-works-pager-next" not in self.driver.page_source:
                    break

        self.driver.quit()
        self.logger.info("🏁 すべてのタスクが完了しました")

if __name__ == "__main__":
    scraper = MachbaitoScraper()
    scraper.run()
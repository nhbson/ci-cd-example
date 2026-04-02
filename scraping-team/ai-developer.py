import os
import json
import random
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
import undetected_chromedriver as uc

# ==================== CONFIG ====================
SERVICE_ACCOUNT_FILE = "service-account.json"
# ================================================

class DynamicScraper:
    def __init__(self, log_func):
        self.log = log_func
        self.driver = None
        self.session = requests.Session()
        self.seen_urls = set()

    def init_browser(self):
        if self.driver: return
        self.log("[BROWSER] 🛠 Starting Chrome...")
        options = uc.ChromeOptions()
        self.driver = uc.Chrome(options=options)

    def sync_session(self):
        self.log("[SESSION] 🔄 Syncing cookies...")
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])
        self.session.headers.update({
            "User-Agent": self.driver.execute_script("return navigator.userAgent"),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })

    def fetch_detail(self, url, selectors):
        """Extracts data using dynamic CSS selectors provided by the user."""
        if url in self.seen_urls: return None
        try:
            time.sleep(random.uniform(1.0, 2.0))
            res = self.session.get(url, timeout=15)
            if res.status_code != 200: return None
            soup = BeautifulSoup(res.text, 'html.parser')

            # Dynamic Extraction
            def get_data(css):
                if not css: return "N/A"
                el = soup.select_one(css)
                return el.get_text(" ", strip=True) if el else "N/A"

            title = get_data(selectors['s_title'])
            company = get_data(selectors['s_company'])
            address = get_data(selectors['s_address'])

            self.seen_urls.add(url)
            self.log(f"[DETAIL] 🔍 Scraped: {company[:15]}...")
            return [company, address, url, title]
        except Exception as e:
            return None

    def process_task(self, task, gc):
        self.log(f"[TASK] 🚀 Starting Task: {task['name']}")
        
        # Google Sheet Connection
        try:
            sh = gc.open_by_key(task['sheet_id'])
            try:
                ws = sh.worksheet(task['tab'])
            except:
                ws = sh.add_worksheet(title=task['tab'], rows="1000", cols="5")
                ws.append_row(["会社名", "住所", "求人URL", "求人タイトル"])
        except Exception as e:
            self.log(f"[ERROR] ❌ GSheet Access Denied: {e}")
            return

        self.init_browser()
        self.seen_urls = set()

        for page in range(1, 51):
            self.log(f"[PAGE] 📄 Loading page {page}...")
            connector = "&" if "?" in task['url'] else "?"
            self.driver.get(f"{task['url']}{connector}page={page}")
            time.sleep(5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 1. Dynamic Link Extraction
            raw_links = soup.select(task['s_link'])
            links = []
            for a in raw_links:
                href = a.get("href")
                if href:
                    if href.startswith("/") and task['prefix']:
                        href = task['prefix'].rstrip('/') + href
                    links.append(href.split('?')[0])
            
            links = list(set(links))
            if not links:
                self.log("[PAGE] 🛑 No links found with current selector.")
                break

            self.sync_session()

            # 2. Concurrent Processing
            results = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self.fetch_detail, l, task) for l in links]
                for f in as_completed(futures):
                    res = f.result()
                    if res: results.append(res)

            if results:
                ws.append_rows(results)
                self.log(f"[SHEET] 💾 Saved {len(results)} rows.")

            # 3. Dynamic Pagination Stop (Optional: check if next button exists)
            if task['s_next'] and task['s_next'] not in self.driver.page_source:
                self.log("[PAGE] 🔚 Next button not found. Stopping.")
                break

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dynamic Scraper Trainer")
        self.geometry("1100x850")
        self.tasks = self.load_tasks()
        self.setup_ui()

    def setup_ui(self):
        # Container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Top Section: Task Config ---
        input_frame = ttk.LabelFrame(main_frame, text=" 1. Site Configuration (Inspect & Input) ")
        input_frame.pack(fill="x", pady=5)

        # Row 0: General
        ttk.Label(input_frame, text="Task Name:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.e_name = ttk.Entry(input_frame, width=20); self.e_name.grid(row=0, column=1, padx=5)
        
        ttk.Label(input_frame, text="Search URL:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.e_url = ttk.Entry(input_frame, width=40); self.e_url.grid(row=0, column=3, columnspan=3, sticky="we", padx=5)

        # Row 1: Selectors
        ttk.Label(input_frame, text="Link CSS:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.e_s_link = ttk.Entry(input_frame, width=25); self.e_s_link.grid(row=1, column=1, padx=5)
        self.e_s_link.insert(0, "a.p-works-card-wrapper-link") # Machbaito default

        ttk.Label(input_frame, text="URL Prefix:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.e_prefix = ttk.Entry(input_frame, width=25); self.e_prefix.grid(row=1, column=3, padx=5)
        self.e_prefix.insert(0, "https://machbaito.jp")

        # Row 2: Detail Selectors
        ttk.Label(input_frame, text="Title CSS:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.e_s_title = ttk.Entry(input_frame, width=25); self.e_s_title.grid(row=2, column=1, padx=5)
        
        ttk.Label(input_frame, text="Company CSS:").grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.e_s_comp = ttk.Entry(input_frame, width=25); self.e_s_comp.grid(row=2, column=3, padx=5)

        ttk.Label(input_frame, text="Address CSS:").grid(row=2, column=4, padx=5, pady=2, sticky="w")
        self.e_s_addr = ttk.Entry(input_frame, width=25); self.e_s_addr.grid(row=2, column=5, padx=5)

        # Row 3: Google Sheets
        ttk.Label(input_frame, text="Sheet ID:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.e_sid = ttk.Entry(input_frame, width=40); self.e_sid.grid(row=3, column=1, columnspan=3, sticky="we", padx=5)

        ttk.Label(input_frame, text="Tab Name:").grid(row=3, column=4, padx=5, pady=2, sticky="w")
        self.e_tab = ttk.Entry(input_frame, width=15); self.e_tab.grid(row=3, column=5, padx=5)

        btn_add = ttk.Button(input_frame, text="➕ Add Task to List", command=self.add_task)
        btn_add.grid(row=4, column=0, columnspan=6, pady=10)

        # --- Middle Section: Table ---
        self.tree = ttk.Treeview(main_frame, columns=("Name", "SheetID", "Tab"), show='headings', height=6)
        self.tree.heading("Name", text="Task Name"); self.tree.heading("SheetID", text="Sheet ID"); self.tree.heading("Tab", text="Tab")
        self.tree.pack(fill="x", pady=5)

        # --- Bottom Section: Logs ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")
        self.run_btn = ttk.Button(btn_frame, text="▶ RUN ALL TASKS", command=self.start_thread)
        self.run_btn.pack(side="left", pady=5)
        ttk.Button(btn_frame, text="🗑 Clear Tasks", command=self.clear_tasks).pack(side="left", padx=10)

        self.log_box = scrolledtext.ScrolledText(main_frame, height=20, bg="#111", fg="#0f0", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, pady=10)
        self.refresh_table()

    def log(self, msg):
        self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see(tk.END)

    def add_task(self):
        task = {
            "name": self.e_name.get(),
            "url": self.e_url.get(),
            "s_link": self.e_s_link.get(),
            "prefix": self.e_prefix.get(),
            "s_title": self.e_s_title.get(),
            "s_company": self.e_s_comp.get(),
            "s_address": self.e_s_addr.get(),
            "sheet_id": self.e_sid.get(),
            "tab": self.e_tab.get(),
            "s_next": "p-works-pager-next" # Default machbaito pagination check
        }
        if not task['name'] or not task['url']:
            messagebox.showwarning("Error", "Name and URL are required!")
            return
        self.tasks.append(task)
        self.save_tasks()
        self.refresh_table()

    def load_tasks(self):
        if os.path.exists("training_config.json"):
            with open("training_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_tasks(self):
        with open("training_config.json", "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=4, ensure_ascii=False)

    def clear_tasks(self):
        self.tasks = []; self.save_tasks(); self.refresh_table()

    def refresh_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in self.tasks: self.tree.insert("", "end", values=(t['name'], t['sheet_id'], t['tab']))

    def start_thread(self):
        self.run_btn.config(state="disabled")
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        scraper = None
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
            gc = gspread.authorize(creds)
            scraper = DynamicScraper(self.log)
            for task in self.tasks:
                scraper.process_task(task, gc)
            messagebox.showinfo("Done", "Scraping complete!")
        except Exception as e:
            self.log(f"[CRITICAL] {e}")
        finally:
            self.run_btn.config(state="normal")
            if scraper and scraper.driver: scraper.driver.quit()

if __name__ == "__main__":
    App().mainloop()
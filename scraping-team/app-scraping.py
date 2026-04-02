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

# ==================== SETTINGS ====================
SERVICE_ACCOUNT_FILE = "service-account.json"
# ==================================================

class UniversalScraper:
    def __init__(self, log_func):
        self.log = log_func
        self.driver = None
        self.session = requests.Session()
        self.seen_urls = set()

    def init_browser(self):
        if self.driver:
            return
        options = uc.ChromeOptions()
        # options.add_argument('--headless') # Uncomment for headless
        self.driver = uc.Chrome(options=options)
        self.log("🚀 Browser initialized.")

    def sync_session(self):
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])
        self.session.headers.update({
            "User-Agent": self.driver.execute_script("return navigator.userAgent"),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })

    def fetch_detail(self, url, site_type):
        if url in self.seen_urls: return None
        try:
            time.sleep(random.uniform(1.0, 2.0))
            res = self.session.get(url, timeout=15)
            if res.status_code != 200: return None
            soup = BeautifulSoup(res.text, 'html.parser')

            company, address, title = "N/A", "N/A", "N/A"

            if site_type == "Machbaito":
                comp_el = soup.select_one(".p-detail-company-text-item-name p")
                addr_el = soup.select_one(".js-detail-access")
                ttl_el = soup.select_one(".p-detail-main-heading")
                
                company = comp_el.get_text(strip=True) if comp_el else "N/A"
                address = addr_el.get_text(" ", strip=True) if addr_el else "N/A"
                title = ttl_el.get_text(strip=True) if ttl_el else "N/A"

            elif site_type == "Gigabaito":
                title_el = soup.select_one("h1, .job_detail_ttl_txt")
                title = title_el.get_text(strip=True) if title_el else "N/A"
                # Gigabaito usually uses table rows for data
                for row in soup.select("table tr"):
                    th = row.find("th")
                    td = row.find("td")
                    if th and td:
                        label = th.get_text()
                        if "会社名" in label or "店舗名" in label:
                            company = td.get_text(strip=True)
                        elif "所在地" in label or "勤務地" in label:
                            address = td.get_text(" ", strip=True)

            self.seen_urls.add(url)
            return [company, address, url, title]
        except Exception as e:
            return None

    def process_task(self, task, gc):
        site = task['site']
        url = task['url']
        sheet_id = task['sheet_id']
        tab_name = task['tab']

        self.log(f"--- Task Started: {task['name']} ---")
        
        # Connect to Sheet
        try:
            sh = gc.open_by_key(sheet_id)
            try:
                ws = sh.worksheet(tab_name)
            except:
                ws = sh.add_worksheet(title=tab_name, rows="1000", cols="5")
                ws.append_row(["会社名", "住所", "求人URL", "求人タイトル"])
        except Exception as e:
            self.log(f"❌ Google Sheet Error: {e}")
            return

        self.init_browser()
        self.seen_urls = set()

        for page in range(1, 101): # Safety limit 100 pages
            self.log(f"📄 Scraping {site} Page {page}...")
            connector = "&" if "?" in url else "?"
            self.driver.get(f"{url}{connector}page={page}")
            time.sleep(5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Link Extraction Logic
            if site == "Machbaito":
                links = ["https://machbaito.jp" + a.get("href").split('?')[0] for a in soup.select("a.p-works-card-wrapper-link")]
            else: # Gigabaito
                links = [a.get("href") for a in soup.select("a[href*='/detail/']") if "gigabaito.com" in a.get("href")]

            links = list(set(links))
            if not links:
                self.log("✅ No more links found.")
                break

            self.sync_session()
            results = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self.fetch_detail, l, site) for l in links]
                for f in as_completed(futures):
                    res = f.result()
                    if res: results.append(res)

            if results:
                ws.append_rows(results)
                self.log(f"💾 Saved {len(results)} rows to {tab_name}")

            # Check for next page
            page_src = self.driver.page_source
            if "次へ" not in page_src and "p-works-pager-next" not in page_src:
                break

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Job Scraper Pro")
        self.geometry("900x700")
        self.tasks = self.load_tasks()
        self.setup_ui()

    def setup_ui(self):
        # Entry Area
        input_frame = ttk.LabelFrame(self, text=" Task Management ")
        input_frame.pack(fill="x", padx=10, pady=5)

        # Site Selection
        ttk.Label(input_frame, text="Site:").grid(row=0, column=0, sticky="w", padx=5)
        self.site_cb = ttk.Combobox(input_frame, values=["Machbaito", "Gigabaito"], state="readonly", width=12)
        self.site_cb.set("Machbaito")
        self.site_cb.grid(row=0, column=1, padx=5, pady=5)

        # Name
        ttk.Label(input_frame, text="Task Name:").grid(row=0, column=2, sticky="w", padx=5)
        self.name_ent = ttk.Entry(input_frame, width=20)
        self.name_ent.grid(row=0, column=3, padx=5)

        # URL
        ttk.Label(input_frame, text="Search URL:").grid(row=1, column=0, sticky="w", padx=5)
        self.url_ent = ttk.Entry(input_frame, width=50)
        self.url_ent.grid(row=1, column=1, columnspan=3, sticky="we", padx=5, pady=5)

        # Sheet ID
        ttk.Label(input_frame, text="Google Sheet ID:").grid(row=2, column=0, sticky="w", padx=5)
        self.sid_ent = ttk.Entry(input_frame, width=50)
        self.sid_ent.grid(row=2, column=1, columnspan=3, sticky="we", padx=5, pady=5)

        # Tab Name
        ttk.Label(input_frame, text="Tab Name:").grid(row=2, column=4, sticky="w", padx=5)
        self.tab_ent = ttk.Entry(input_frame, width=15)
        self.tab_ent.grid(row=2, column=5, padx=5)

        btn_add = ttk.Button(input_frame, text="➕ Add Task", command=self.add_task)
        btn_add.grid(row=1, column=4, columnspan=2, sticky="we", padx=5)

        # Table
        self.tree = ttk.Treeview(self, columns=("Name", "Site", "SheetID", "Tab"), show='headings', height=6)
        self.tree.heading("Name", text="Name")
        self.tree.heading("Site", text="Site")
        self.tree.heading("SheetID", text="Sheet ID")
        self.tree.heading("Tab", text="Tab")
        self.tree.column("SheetID", width=300)
        self.tree.pack(fill="x", padx=10, pady=5)

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10)
        
        self.run_btn = ttk.Button(btn_frame, text="▶ START ALL TASKS", command=self.start_thread)
        self.run_btn.pack(side="left", pady=10)

        ttk.Button(btn_frame, text="🗑 Delete Selected", command=self.delete_task).pack(side="left", padx=10)

        # Logs
        self.log_box = scrolledtext.ScrolledText(self, height=20, bg="#1e1e1e", fg="#00ff00")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_table()

    def log(self, msg):
        self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see(tk.END)

    def load_tasks(self):
        if os.path.exists("tasks_config.json"):
            with open("tasks_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_tasks(self):
        with open("tasks_config.json", "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=4, ensure_ascii=False)

    def add_task(self):
        data = {
            "name": self.name_ent.get(),
            "site": self.site_cb.get(),
            "url": self.url_ent.get(),
            "sheet_id": self.sid_ent.get(),
            "tab": self.tab_ent.get()
        }
        if not all(data.values()):
            messagebox.showwarning("Error", "Please fill all fields")
            return
        self.tasks.append(data)
        self.save_tasks()
        self.refresh_table()

    def delete_task(self):
        selected = self.tree.selection()
        for s in selected:
            idx = self.tree.index(s)
            del self.tasks[idx]
        self.save_tasks()
        self.refresh_table()

    def refresh_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in self.tasks:
            self.tree.insert("", "end", values=(t['name'], t['site'], t['sheet_id'], t['tab']))

    def start_thread(self):
        self.run_btn.config(state="disabled")
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
            gc = gspread.authorize(creds)
            
            scraper = UniversalScraper(self.log)
            for task in self.tasks:
                scraper.process_task(task, gc)
            
            messagebox.showinfo("Success", "All scraping tasks finished!")
        except Exception as e:
            self.log(f"CRITICAL ERROR: {e}")
        finally:
            self.run_btn.config(state="normal")
            if scraper.driver: scraper.driver.quit()

if __name__ == "__main__":
    app = App()
    app.mainloop()
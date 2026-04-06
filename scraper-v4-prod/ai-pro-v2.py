import os
import json
import random
import time
import threading
import re
import math
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse, urljoin

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

# ================= CONFIG =================
SERVICE_ACCOUNT_FILE = "service-account.json"
CONFIG_FILE = "scraper_config.json"

# ================= UI COLORS =================
COLORS = {
    "bg": "#f5f6fa",
    "panel": "#ffffff",
    "fg": "#2d3436",
    "accent": "#0984e3",
    "success": "#00b894",
    "error": "#d63031"
}

# ================= SCRAPER ENGINE =================
class DynamicScraper:
    def __init__(self, log_func):
        self.log = log_func
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.seen_urls = set()

    def safe_get(self, url):
        try:
            r = self.session.get(url, timeout=15)
            return r if r.status_code == 200 else None
        except:
            return None

    def fetch_detail(self, url, fields):
        if url in self.seen_urls: return None
        time.sleep(random.uniform(0.5, 1.0))
        
        res = self.safe_get(url)
        if not res: return None
        
        soup = BeautifulSoup(res.text, "html.parser")
        data = {"URL": url}
        for k, sel in fields.items():
            el = soup.select_one(sel)
            data[k] = el.get_text(strip=True) if el else "N/A"
        
        self.seen_urls.add(url)
        return data

    def process_task(self, task, gc, stop_check):
        self.log(f"🚀 Starting: {task['name']}")
        
        # 1. Fetch Page 1 to calculate total pages
        base_url = task['url']
        res = self.safe_get(base_url)
        if not res:
            self.log("❌ Failed to load initial page", "error")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # 2. Auto-Calculate Total Pages
        total_pages = 1
        items_per_page = 20
        stats_sel = task.get('stats_sel', '.sg-pager-display')
        stats_el = soup.select_one(stats_sel)

        if stats_el:
            text = stats_el.get_text(strip=True) # "1件～20件（全3187件中）"
            nums = re.findall(r'\d+', text)
            if len(nums) >= 3:
                start_idx = int(nums[0])
                end_idx = int(nums[1])
                total_items = int(nums[2])
                
                items_per_page = (end_idx - start_idx) + 1
                total_pages = math.ceil(total_items / items_per_page)
                self.log(f"📊 Detected: {total_items} items total. Calculation: {total_pages} pages.")
            else:
                self.log("⚠️ Could not parse paging numbers. Defaulting to 1 page.", "error")

        # Limit by user settings
        max_user_pages = int(task.get('max_pages', 10))
        final_page_count = min(total_pages, max_user_pages)

        # 3. Iterate through pages
        for p in range(1, final_page_count + 1):
            if stop_check(): break
            
            # Build URL for current page (e.g. site.com?p=2)
            u = urlparse(base_url)
            query = parse_qs(u.query)
            query[task.get('page_param', 'p')] = [str(p)]
            new_query = urlencode(query, doseq=True)
            current_page_url = urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))

            self.log(f"📄 Page {p}/{final_page_count}: {current_page_url}")
            
            # Fetch page content (already have page 1)
            if p > 1:
                res = self.safe_get(current_page_url)
                if not res: break
                soup = BeautifulSoup(res.text, "html.parser")

            # 4. Extract detail links
            links = [urljoin(current_page_url, a.get("href")) 
                     for a in soup.select(task['s_link']) if a.get("href")]

            # 5. Fetch details in parallel
            results = []
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(self.fetch_detail, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    if stop_check(): break
                    r = f.result()
                    if r: results.append(r)

            # 6. Save to Google Sheets
            if results:
                try:
                    sh = gc.open_by_key(task['sheet_id'])
                    try:
                        ws = sh.worksheet(task['tab'])
                    except:
                        ws = sh.add_worksheet(title=task['tab'], rows="1000", cols="20")
                    
                    headers = ["URL"] + list(task['fields'].keys())
                    rows = [[r.get(h, "") for h in headers] for r in results]
                    ws.append_rows(rows)
                    self.log(f"✅ Saved {len(results)} items from page {p}", "success")
                except Exception as e:
                    self.log(f"❌ Google Sheets Error: {e}", "error")

# ================= UI APPLICATION =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SCRAPER PRO v2 (AUTO-PAGING)")
        self.geometry("1200x900")
        self.configure(bg=COLORS["bg"])
        
        self.tasks = self.load_tasks()
        self.dynamic_fields = {}
        self.selected_task_index = None
        self.running = False
        self.stop_flag = False
        
        self.setup_ui()
        self.refresh_tasks_list()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=20, pady=20)
        
        # --- LEFT: CONFIGURATION ---
        left = ttk.Frame(main, width=450)
        left.pack(side="left", fill="y", padx=10)

        ttk.Label(left, text="Saved Tasks", font=("Arial", 10, "bold")).pack(anchor="w")
        self.task_list = tk.Listbox(left, height=6, bg="#ffffff", bd=1)
        self.task_list.pack(fill="x", pady=5)
        self.task_list.bind("<<ListboxSelect>>", self.on_select_task)

        # Basic Fields
        self.e_name = self.entry(left, "Task Name (Identifier)")
        self.e_url = self.entry(left, "Initial URL (Page 1)")
        self.e_link = self.entry(left, "Job Link Selector (e.g. .job-card a)")
        
        # Paging Logic Frame
        p_frame = ttk.LabelFrame(left, text="Auto-Paging Calculation")
        p_frame.pack(fill="x", pady=10, padx=2)
        
        ttk.Label(p_frame, text="Stats Selector (e.g. .sg-pager-display)").pack(anchor="w", padx=5)
        self.e_stats_sel = tk.Entry(p_frame)
        self.e_stats_sel.pack(fill="x", padx=5, pady=2)
        self.e_stats_sel.insert(0, ".sg-pager-display")

        ttk.Label(p_frame, text="Page Param Name (e.g. p or page)").pack(anchor="w", padx=5)
        self.e_page_param = tk.Entry(p_frame)
        self.e_page_param.pack(fill="x", padx=5, pady=2)
        self.e_page_param.insert(0, "p")

        ttk.Label(p_frame, text="Max Pages to Scrape (Safety Limit)").pack(anchor="w", padx=5)
        self.e_max_pages = tk.Entry(p_frame)
        self.e_max_pages.pack(fill="x", padx=5, pady=2)
        self.e_max_pages.insert(0, "100")

        # Sheet Fields
        self.e_sid = self.entry(left, "Google Sheet ID")
        self.e_tab = self.entry(left, "Tab Name")

        # Selectors
        sel_box = ttk.LabelFrame(left, text="Data Selectors (Detail Page)")
        sel_box.pack(fill="x", pady=10)
        self.f_name = tk.Entry(sel_box); self.f_name.pack(fill="x", padx=5, pady=2)
        self.f_sel = tk.Entry(sel_box); self.f_sel.pack(fill="x", padx=5, pady=2)
        
        f_btn_f = ttk.Frame(sel_box)
        f_btn_f.pack(fill="x")
        ttk.Button(f_btn_f, text="Add Field", command=self.add_field).pack(side="left", expand=True, fill="x")
        ttk.Button(f_btn_f, text="Clear Fields", command=self.clear_fields).pack(side="left", expand=True, fill="x")
        
        self.listbox = tk.Listbox(sel_box, height=4)
        self.listbox.pack(fill="x", padx=5, pady=5)

        ttk.Button(left, text="SAVE TASK", command=self.save_task).pack(fill="x", pady=5)
        tk.Button(left, text="DELETE TASK", bg=COLORS["error"], fg="white", command=self.remove_task).pack(fill="x")

        # --- RIGHT: LOGGING ---
        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True, padx=10)
        
        ctrls = ttk.Frame(right)
        ctrls.pack(fill="x")
        ttk.Button(ctrls, text="▶ START RUN", command=self.run).pack(side="left", expand=True, fill="x")
        ttk.Button(ctrls, text="🛑 STOP", command=self.stop).pack(side="left", expand=True, fill="x")
        
        self.log_box = scrolledtext.ScrolledText(right, bg="#2d3436", fg="#dfe6e9", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, pady=10)

    # --- UI HELPERS ---
    def entry(self, parent, label):
        ttk.Label(parent, text=label).pack(anchor="w")
        e = tk.Entry(parent); e.pack(fill="x", pady=2); return e

    def add_field(self):
        n, s = self.f_name.get().strip(), self.f_sel.get().strip()
        if n and s: 
            self.dynamic_fields[n] = s
            self.refresh_fields_ui()
            self.f_name.delete(0, tk.END); self.f_sel.delete(0, tk.END)

    def clear_fields(self):
        self.dynamic_fields = {}
        self.refresh_fields_ui()

    def refresh_fields_ui(self):
        self.listbox.delete(0, tk.END)
        for k, v in self.dynamic_fields.items(): self.listbox.insert(tk.END, f"{k}: {v}")

    def on_select_task(self, event):
        if not self.task_list.curselection(): return
        idx = self.task_list.curselection()[0]
        task = self.tasks[idx]
        self.selected_task_index = idx
        
        self.e_name.delete(0, tk.END); self.e_name.insert(0, task['name'])
        self.e_url.delete(0, tk.END); self.e_url.insert(0, task['url'])
        self.e_link.delete(0, tk.END); self.e_link.insert(0, task.get('s_link', ''))
        self.e_stats_sel.delete(0, tk.END); self.e_stats_sel.insert(0, task.get('stats_sel', '.sg-pager-display'))
        self.e_page_param.delete(0, tk.END); self.e_page_param.insert(0, task.get('page_param', 'p'))
        self.e_max_pages.delete(0, tk.END); self.e_max_pages.insert(0, task.get('max_pages', '100'))
        self.e_sid.delete(0, tk.END); self.e_sid.insert(0, task.get('sheet_id', ''))
        self.e_tab.delete(0, tk.END); self.e_tab.insert(0, task.get('tab', ''))
        self.dynamic_fields = task['fields'].copy()
        self.refresh_fields_ui()

    def save_task(self):
        name = self.e_name.get().strip()
        if not name: return messagebox.showwarning("Error", "Task name is required")
        task = {
            "name": name,
            "url": self.e_url.get().strip(),
            "s_link": self.e_link.get().strip(),
            "stats_sel": self.e_stats_sel.get().strip(),
            "page_param": self.e_page_param.get().strip(),
            "max_pages": self.e_max_pages.get().strip(),
            "fields": self.dynamic_fields.copy(),
            "sheet_id": self.e_sid.get().strip(),
            "tab": self.e_tab.get().strip()
        }
        if self.selected_task_index is not None: self.tasks[self.selected_task_index] = task
        else: self.tasks.append(task)
        self.save_tasks(); self.refresh_tasks_list(); self.log(f"💾 Task Saved: {name}")

    def remove_task(self):
        if self.selected_task_index is not None:
            del self.tasks[self.selected_task_index]
            self.save_tasks(); self.refresh_tasks_list(); self.log("🗑 Task Deleted")

    def refresh_tasks_list(self):
        self.task_list.delete(0, tk.END)
        for t in self.tasks: self.task_list.insert(tk.END, t['name'])

    def log(self, msg, tag="info"):
        self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def stop(self): 
        self.stop_flag = True
        self.log("🛑 Stop command sent...", "error")

    def run(self):
        if self.running: return
        self.running = True; self.stop_flag = False
        threading.Thread(target=self.start_scraping, daemon=True).start()

    def start_scraping(self):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                SERVICE_ACCOUNT_FILE, 
                ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
            )
            gc = gspread.authorize(creds)
            scraper = DynamicScraper(self.log)
            
            for task in self.tasks:
                if self.stop_flag: break
                scraper.process_task(task, gc, lambda: self.stop_flag)
            
            self.log("🏁 RUN COMPLETE")
        except Exception as e:
            self.log(f"❌ Error: {e}", "error")
        finally:
            self.running = False

    def load_tasks(self):
        return json.load(open(CONFIG_FILE)) if os.path.exists(CONFIG_FILE) else []

    def save_tasks(self):
        json.dump(self.tasks, open(CONFIG_FILE, "w"), indent=2)

if __name__ == "__main__":
    App().mainloop()
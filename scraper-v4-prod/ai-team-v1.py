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

COLORS = {
    "bg": "#f5f6fa",
    "panel": "#ffffff",
    "fg": "#2d3436",
    "accent": "#0984e3",
    "success": "#00b894",
    "error": "#d63031",
    "warning": "#f1c40f"
}

# ================= SCRAPER ENGINE =================
class DynamicScraper:
    def __init__(self, log_func, check_status_func):
        self.log = log_func
        self.check_status = check_status_func
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })
        self.seen_urls = set()

    def safe_get(self, url):
        if not self.check_status(): return None
        try:
            time.sleep(random.uniform(1.5, 3.0)) # Increased delay to avoid N/A (anti-bot)
            r = self.session.get(url, timeout=15)
            # Check for redirect to login
            if "/login/" in r.url:
                self.log(f"⚠️ Login Wall Detected: Data hidden for {url}", "warning")
            return r if r.status_code == 200 else None
        except:
            return None

    def fetch_detail(self, url, fields):
        if not self.check_status(): return None
        if url in self.seen_urls: return None
        
        res = self.safe_get(url)
        if not res: return None
        
        soup = BeautifulSoup(res.text, "html.parser")
        data = {"URL": url}
        
        # --- ROBUST EXTRACTION LOGIC ---
        # 1. Company Name
        name_selectors = [
            ".pg-job-detail-jobcassette-name", 
            ".pg-job-headhunter-search-company li a", 
            ".pg-job-headhunter-search-company li",
            "h1.huge"
        ]
        company_name = "N/A"
        for sel in name_selectors:
            el = soup.select_one(sel)
            if el and "会員登録" not in el.text:
                company_name = el.get_text(strip=True)
                break
        data["企業名"] = company_name

        # 2. Headquarters (HQ)
        hq_data = "N/A"
        # Search for address inside overview paragraphs
        overview = soup.select_one(".pg-job-company-info-detail, .sg-table")
        if overview:
            text = overview.get_text("|", strip=True)
            match = re.search(r'(?:【本社所在地】|本社所在地|所在地)[：:]?([^|]+)', text)
            if match:
                hq_data = match.group(1).strip()
            else:
                # Fallback: find any text that looks like an address in the info section
                addr_match = re.search(r'(東京都|大阪府|京都府|..[県]).+[0-9-]{3,}', text)
                if addr_match: hq_data = addr_match.group(0).strip()
        data["本社所在地"] = hq_data

        # 3. Scale
        scale_el = soup.select_one(".pg-job-detail-company-capital, .sg-tag-style-blue")
        data["会社規模"] = scale_el.get_text(strip=True).replace("会社規模", "").strip() if scale_el else "N/A"

        # 4. Process user-defined fields if any
        for k, sel in fields.items():
            if k in data: continue # Skip hardcoded fields
            el = soup.select_one(sel)
            data[k] = el.get_text(strip=True) if el else "N/A"
        
        self.seen_urls.add(url)
        return data

    def process_task(self, task, gc):
        self.log(f"🚀 Starting: {task['name']}")
        
        base_url = task['url']
        res = self.safe_get(base_url)
        if not res: return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # Paging Logic
        total_pages = 1
        stats_el = soup.select_one(task.get('stats_sel', '.sg-pager-display'))
        if stats_el:
            nums = re.findall(r'\d+', stats_el.get_text(strip=True))
            if len(nums) >= 3:
                total_pages = math.ceil(int(nums[2]) / 20)

        max_user_pages = int(task.get('max_pages', 10))
        final_page_count = min(total_pages, max_user_pages)

        for p in range(1, final_page_count + 1):
            if not self.check_status(): break
            
            u = urlparse(base_url)
            query = parse_qs(u.query)
            query[task.get('page_param', 'p')] = [str(p)]
            current_page_url = urlunparse(u._replace(query=urlencode(query, doseq=True)))

            self.log(f"📄 Page {p}/{final_page_count}: {current_page_url}")
            
            if p > 1:
                res = self.safe_get(current_page_url)
                if not res: break
                soup = BeautifulSoup(res.text, "html.parser")

            links = []
            for a in soup.find_all("a", href=True):
                href = a['href']
                if "/job/view/" in href:
                    links.append(urljoin("https://www.bizreach.jp", href).split('?')[0])
            
            links = list(set(links))
            self.log(f"🔗 Found {len(links)} links on page {p}")

            results = []
            # Safety: use smaller workers (2-3) to avoid being blocked with N/A
            with ThreadPoolExecutor(max_workers=3) as ex:
                futures = [ex.submit(self.fetch_detail, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    if not self.check_status(): break
                    r = f.result()
                    if r: 
                        results.append(r)
                        self.log(f"✅ Extracted: {r.get('企業名', 'N/A')[:15]}...")

            if results and self.check_status():
                try:
                    sh = gc.open_by_key(task['sheet_id'])
                    ws = sh.worksheet(task['tab'])
                    headers = ["URL", "企業名", "本社所在地", "会社規模"]
                    rows = [[r.get(h, "N/A") for h in headers] for r in results]
                    ws.append_rows(rows)
                    self.log(f"💾 Saved {len(results)} items to Sheets.", "success")
                except Exception as e:
                    self.log(f"❌ Sheets Error: {e}", "error")

# ================= UI APPLICATION (PAUSE/RESUME LOGIC INTACT) =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BIZREACH PRO v2 (PAUSE/STOP)")
        self.geometry("1200x950")
        self.configure(bg=COLORS["bg"])
        
        self.tasks = self.load_tasks()
        self.dynamic_fields = {}
        self.selected_task_index = None
        self.running = False
        self.paused = False
        self.stop_flag = False
        self.pause_condition = threading.Condition()

        self.setup_ui()
        self.refresh_tasks_list()

    def setup_ui(self):
        style = ttk.Style(); style.theme_use('clam')
        main = ttk.Frame(self); main.pack(fill="both", expand=True, padx=20, pady=20)
        
        # --- LEFT PANEL ---
        left = ttk.Frame(main, width=450); left.pack(side="left", fill="y", padx=10)
        ttk.Label(left, text="Saved Tasks", font=("Arial", 10, "bold")).pack(anchor="w")
        self.task_list = tk.Listbox(left, height=6, bg="#ffffff", bd=1); self.task_list.pack(fill="x", pady=5)
        self.task_list.bind("<<ListboxSelect>>", self.on_select_task)

        self.e_name = self.entry(left, "Task Name")
        self.e_url = self.entry(left, "Initial URL")
        self.e_link = self.entry(left, "Job Link Selector")
        
        p_frame = ttk.LabelFrame(left, text="Auto-Paging Calculation")
        p_frame.pack(fill="x", pady=10, padx=2)
        self.e_stats_sel = self.entry_in_frame(p_frame, "Stats Selector", ".sg-pager-display")
        self.e_page_param = self.entry_in_frame(p_frame, "Page Param Name", "p")
        self.e_max_pages = self.entry_in_frame(p_frame, "Max Pages Limit", "100")

        self.e_sid = self.entry(left, "Google Sheet ID")
        self.e_tab = self.entry(left, "Tab Name")

        sel_box = ttk.LabelFrame(left, text="Data Selectors (Detail Page)")
        sel_box.pack(fill="x", pady=10)
        self.f_name = tk.Entry(sel_box); self.f_name.pack(fill="x", padx=5, pady=2)
        self.f_sel = tk.Entry(sel_box); self.f_sel.pack(fill="x", padx=5, pady=2)
        f_btn_f = ttk.Frame(sel_box); f_btn_f.pack(fill="x")
        ttk.Button(f_btn_f, text="Add Field", command=self.add_field).pack(side="left", expand=True, fill="x")
        ttk.Button(f_btn_f, text="Clear Fields", command=self.clear_fields).pack(side="left", expand=True, fill="x")
        self.listbox = tk.Listbox(sel_box, height=4); self.listbox.pack(fill="x", padx=5, pady=5)

        ttk.Button(left, text="SAVE TASK", command=self.save_task).pack(fill="x", pady=5)
        tk.Button(left, text="DELETE TASK", bg=COLORS["error"], fg="white", command=self.remove_task).pack(fill="x")

        # --- RIGHT PANEL ---
        right = ttk.Frame(main); right.pack(side="right", fill="both", expand=True, padx=10)
        btn_bar = ttk.Frame(right); btn_bar.pack(fill="x", pady=5)
        
        self.btn_start = tk.Button(btn_bar, text="▶ START", bg=COLORS["success"], fg="white", font=("Arial", 9, "bold"), command=self.run, width=10)
        self.btn_start.pack(side="left", padx=2)
        self.btn_pause = tk.Button(btn_bar, text="⏸ PAUSE", bg=COLORS["warning"], fg="white", font=("Arial", 9, "bold"), command=self.pause, width=10)
        self.btn_pause.pack(side="left", padx=2)
        self.btn_resume = tk.Button(btn_bar, text="⏯ RESUME", bg=COLORS["accent"], fg="white", font=("Arial", 9, "bold"), command=self.resume, width=10)
        self.btn_resume.pack(side="left", padx=2)
        self.btn_stop = tk.Button(btn_bar, text="🛑 STOP", bg=COLORS["error"], fg="white", font=("Arial", 9, "bold"), command=self.stop, width=10)
        self.btn_stop.pack(side="left", padx=2)
        
        self.log_box = scrolledtext.ScrolledText(right, bg="#2d3436", fg="#dfe6e9", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, pady=10)

    # --- CONTROL LOGIC ---
    def check_status(self):
        with self.pause_condition:
            while self.paused and not self.stop_flag:
                self.pause_condition.wait()
            if self.stop_flag: return False
        return True

    def run(self):
        if self.running: return
        self.running = True; self.stop_flag = False; self.paused = False
        threading.Thread(target=self.start_scraping, daemon=True).start()

    def pause(self): self.paused = True; self.log("⏸ Scraping PAUSED.", "warning")
    def resume(self):
        self.paused = False
        with self.pause_condition: self.pause_condition.notify_all()
        self.log("⏯ Scraping RESUMED.", "success")
    def stop(self):
        self.stop_flag = True; self.paused = False
        with self.pause_condition: self.pause_condition.notify_all()
        self.log("🛑 STOPPING...", "error")

    # --- UI HELPERS (Original) ---
    def entry(self, parent, label):
        ttk.Label(parent, text=label).pack(anchor="w")
        e = tk.Entry(parent); e.pack(fill="x", pady=2); return e
    def entry_in_frame(self, parent, label, default):
        ttk.Label(parent, text=label).pack(anchor="w", padx=5)
        e = tk.Entry(parent); e.pack(fill="x", padx=5, pady=2); e.insert(0, default); return e
    def add_field(self):
        n, s = self.f_name.get().strip(), self.f_sel.get().strip()
        if n and s: 
            self.dynamic_fields[n] = s
            self.refresh_fields_ui()
            self.f_name.delete(0, tk.END); self.f_sel.delete(0, tk.END)
    def clear_fields(self): self.dynamic_fields = {}; self.refresh_fields_ui()
    def refresh_fields_ui(self):
        self.listbox.delete(0, tk.END)
        for k, v in self.dynamic_fields.items(): self.listbox.insert(tk.END, f"{k}: {v}")
    def on_select_task(self, event):
        if not self.task_list.curselection(): return
        idx = self.task_list.curselection()[0]
        task = self.tasks[idx]; self.selected_task_index = idx
        self.e_name.delete(0, tk.END); self.e_name.insert(0, task['name'])
        self.e_url.delete(0, tk.END); self.e_url.insert(0, task['url'])
        self.e_sid.delete(0, tk.END); self.e_sid.insert(0, task.get('sheet_id', ''))
        self.e_tab.delete(0, tk.END); self.e_tab.insert(0, task.get('tab', ''))
        self.dynamic_fields = task['fields'].copy(); self.refresh_fields_ui()
    def save_task(self):
        name = self.e_name.get().strip()
        if not name: return messagebox.showwarning("Error", "Task name required")
        task = {
            "name": name, "url": self.e_url.get().strip(), "s_link": self.e_link.get().strip(),
            "stats_sel": self.e_stats_sel.get().strip(), "page_param": self.e_page_param.get().strip(),
            "max_pages": self.e_max_pages.get().strip(), "fields": self.dynamic_fields.copy(),
            "sheet_id": self.e_sid.get().strip(), "tab": self.e_tab.get().strip()
        }
        if self.selected_task_index is not None: self.tasks[self.selected_task_index] = task
        else: self.tasks.append(task)
        self.save_tasks(); self.refresh_tasks_list(); self.log(f"💾 Task Saved: {name}")
    def remove_task(self):
        if self.selected_task_index is not None:
            del self.tasks[self.selected_task_index]; self.save_tasks(); self.refresh_tasks_list()
    def refresh_tasks_list(self):
        self.task_list.delete(0, tk.END)
        for t in self.tasks: self.task_list.insert(tk.END, t['name'])
    def log(self, msg, tag="info"):
        self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def start_scraping(self):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive'])
            gc = gspread.authorize(creds)
            scraper = DynamicScraper(self.log, self.check_status)
            for task in self.tasks:
                if self.stop_flag: break
                scraper.process_task(task, gc)
            self.log("🏁 RUN COMPLETE")
        except Exception as e: self.log(f"❌ Error: {e}", "error")
        finally: self.running = False; self.paused = False

    def load_tasks(self): return json.load(open(CONFIG_FILE)) if os.path.exists(CONFIG_FILE) else []
    def save_tasks(self): json.dump(self.tasks, open(CONFIG_FILE, "w"), indent=2)

if __name__ == "__main__": App().mainloop()
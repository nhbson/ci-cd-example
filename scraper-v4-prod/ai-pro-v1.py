import os
import json
import random
import time
import threading
import csv
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# Constants
SERVICE_ACCOUNT_FILE = "service-account.json"
CACHE_FILE = "cache.json"
CONFIG_FILE = "scraper_config.json"

# ================= THEME / STYLING =================
def apply_style(root):
    style = ttk.Style()
    root.configure(bg="#1e1e24")
    
    style.theme_use('clam')
    style.configure("TFrame", background="#1e1e24")
    style.configure("TLabel", background="#1e1e24", foreground="#e0e0e0", font=("Segoe UI", 10))
    style.configure("TLabelframe", background="#1e1e24", foreground="#61afef", font=("Segoe UI", 10, "bold"))
    style.configure("TLabelframe.Label", background="#1e1e24", foreground="#61afef")
    
    style.configure("TButton", font=("Segoe UI", 10), padding=5)
    style.configure("Treeview", background="#2d2d34", foreground="white", fieldbackground="#2d2d34", borderwidth=0)
    style.map("Treeview", background=[('selected', '#3e4451')])

# ================= SCRAPER ENGINE =================
class DynamicScraper:
    def __init__(self, log_func):
        self.log = log_func
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        })
        self.seen_urls = set()
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.seen_urls = set(json.load(f))
            except: self.seen_urls = set()

    def save_cache(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(self.seen_urls), f)

    def safe_get(self, url):
        try:
            res = self.session.get(url, timeout=15)
            return res if res.status_code == 200 else None
        except:
            return None

    def fetch_detail(self, url, fields):
        if url in self.seen_urls:
            return None

        time.sleep(random.uniform(0.5, 1.2))
        res = self.safe_get(url)
        if not res: return None

        soup = BeautifulSoup(res.text, "html.parser")
        data = {"URL": url}
        
        # Dynamic Extraction
        for field_name, selector in fields.items():
            el = soup.select_one(selector) if selector else None
            data[field_name] = el.get_text(" ", strip=True) if el else "N/A"

        self.seen_urls.add(url)
        self.log(f"[FETCHED] {url[:50]}...")
        return data

    def process_task(self, task, gc):
        self.log(f"🚀 Starting Task: {task['name']}")
        
        # Prepare Google Sheet
        try:
            sh = gc.open_by_key(task['sheet_id'])
            ws = sh.worksheet(task['tab'])
        except:
            sh = gc.open_by_key(task['sheet_id'])
            ws = sh.add_worksheet(title=task['tab'], rows="1000", cols="20")
            headers = ["URL"] + list(task['fields'].keys())
            ws.append_row(headers)

        url = task['url']
        page = 1
        
        while url and page <= 50:
            res = self.safe_get(url)
            if not res: break
            
            soup = BeautifulSoup(res.text, "html.parser")
            links = []
            for a in soup.select(task['s_link']):
                href = a.get("href")
                if href:
                    if href.startswith("/") and task['prefix']:
                        href = task['prefix'].rstrip("/") + href
                    links.append(href.split("?")[0])

            links = list(set(links))
            self.log(f"Page {page}: Found {len(links)} links")

            results = []
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(self.fetch_detail, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    r = f.result()
                    if r: results.append(r)

            if results:
                # Convert dict to list based on headers for GSheets
                headers = ["URL"] + list(task['fields'].keys())
                rows_to_upload = [[res.get(h, "N/A") for h in headers] for res in results]
                ws.append_rows(rows_to_upload)
                
                # Local CSV Backup
                file_exists = os.path.isfile("output.csv")
                with open("output.csv", "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    if not file_exists: writer.writeheader()
                    writer.writerows(results)

            # Pagination (simplified)
            next_btn = soup.select_one("a[rel=next], .next")
            if next_btn and page < 50:
                url = next_btn.get("href")
                if url.startswith("/") and task['prefix']:
                    url = task['prefix'].rstrip("/") + url
                page += 1
            else:
                url = None

        self.save_cache()
        self.log(f"✅ Task {task['name']} Finished.")

# ================= MODERN UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI DYNAMIC SCRAPER PRO")
        self.geometry("1200x900")
        apply_style(self)
        
        self.tasks = self.load_tasks()
        self.dynamic_fields = {} # Temporary store for fields being added
        
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg="#282c34", height=60)
        header.pack(fill="x", side="top")
        tk.Label(header, text="🔍 DYNAMIC SCRAPER ENGINE", font=("Segoe UI", 16, "bold"), bg="#282c34", fg="#61afef").pack(pady=15)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # LEFT SIDE: Configuration
        left_panel = ttk.Frame(container)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Basic Config
        config_frame = ttk.LabelFrame(left_panel, text=" 1. Global Config ", padding=15)
        config_frame.pack(fill="x", pady=(0, 10))

        self.create_input(config_frame, "Task Name:", "e_name", 0)
        self.create_input(config_frame, "Base URL:", "e_url", 1)
        self.create_input(config_frame, "List Item CSS:", "e_s_link", 2)
        self.create_input(config_frame, "URL Prefix:", "e_prefix", 3)

        # Dynamic Fields Config
        fields_frame = ttk.LabelFrame(left_panel, text=" 2. Scraped Fields (Dynamic) ", padding=15)
        fields_frame.pack(fill="x", pady=10)

        field_input_row = ttk.Frame(fields_frame)
        field_input_row.pack(fill="x")
        
        self.f_name = ttk.Entry(field_input_row, width=15)
        self.f_name.insert(0, "FieldName")
        self.f_name.pack(side="left", padx=2)
        
        self.f_selector = ttk.Entry(field_input_row, width=25)
        self.f_selector.insert(0, "CSS Selector")
        self.f_selector.pack(side="left", padx=2, fill="x", expand=True)

        ttk.Button(field_input_row, text="Add Field", command=self.add_field_to_list).pack(side="left", padx=5)

        self.fields_display = tk.Text(fields_frame, height=5, bg="#21252b", fg="#98c379", font=("Consolas", 10))
        self.fields_display.pack(fill="x", pady=5)

        # GSheets Config
        gs_frame = ttk.LabelFrame(left_panel, text=" 3. Destination (Google Sheets) ", padding=15)
        gs_frame.pack(fill="x", pady=10)
        self.create_input(gs_frame, "Sheet ID:", "e_sid", 0)
        self.create_input(gs_frame, "Tab Name:", "e_tab", 1)

        ttk.Button(left_panel, text="➕ ADD TASK TO QUEUE", command=self.add_task).pack(fill="x", pady=10)

        # RIGHT SIDE: Queue and Logs
        right_panel = ttk.Frame(container)
        right_panel.pack(side="right", fill="both", expand=True)

        self.tree = ttk.Treeview(right_panel, columns=("Name", "Fields"), show="headings", height=8)
        self.tree.heading("Name", text="Task Name")
        self.tree.heading("Fields", text="Fields Count")
        self.tree.pack(fill="x", pady=(0, 10))

        btn_row = ttk.Frame(right_panel)
        btn_row.pack(fill="x", pady=5)
        ttk.Button(btn_row, text="▶️ RUN SCRAPER", command=self.start_thread).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(btn_row, text="🧹 CLEAR LOGS", command=lambda: self.log_box.delete("1.0", tk.END)).pack(side="left", padx=2)

        self.log_box = scrolledtext.ScrolledText(right_panel, bg="#1e1e1e", fg="#abb2bf", font=("Consolas", 10), insertbackground="white")
        self.log_box.pack(fill="both", expand=True)

        self.refresh_table()

    def create_input(self, parent, label, var_name, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        entry = ttk.Entry(parent)
        entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(10, 0))
        parent.columnconfigure(1, weight=1)
        setattr(self, var_name, entry)

    def add_field_to_list(self):
        name = self.f_name.get().strip()
        sel = self.f_selector.get().strip()
        if name and sel:
            self.dynamic_fields[name] = sel
            self.fields_display.insert(tk.END, f"{name}: {sel}\n")
            self.f_name.delete(0, tk.END)
            self.f_selector.delete(0, tk.END)

    def add_task(self):
        task = {
            "name": self.e_name.get(),
            "url": self.e_url.get(),
            "s_link": self.e_s_link.get(),
            "prefix": self.e_prefix.get(),
            "fields": self.dynamic_fields.copy(),
            "sheet_id": self.e_sid.get(),
            "tab": self.e_tab.get(),
        }
        if not task["name"] or not task["fields"]:
            messagebox.showerror("Error", "Task Name and at least one field required!")
            return
        
        self.tasks.append(task)
        self.save_tasks()
        self.refresh_table()
        # Reset dynamic fields for next task
        self.dynamic_fields = {}
        self.fields_display.delete("1.0", tk.END)

    def log(self, msg):
        self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see(tk.END)

    def refresh_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in self.tasks:
            self.tree.insert("", "end", values=(t['name'], len(t['fields'])))

    def load_tasks(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_tasks(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=2)

    def start_thread(self):
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
            gc = gspread.authorize(creds)
            
            scraper = DynamicScraper(self.log)
            for task in self.tasks:
                scraper.process_task(task, gc)
            
            messagebox.showinfo("Success", "All tasks completed!")
        except Exception as e:
            self.log(f"CRITICAL ERROR: {str(e)}")

if __name__ == "__main__":
    app = App()
    app.mainloop()
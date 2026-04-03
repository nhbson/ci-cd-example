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

# Constants
SERVICE_ACCOUNT_FILE = "service-account.json"
CACHE_FILE = "cache.json"
CONFIG_FILE = "scraper_config.json"

# ================= MODERN THEME COLORS =================
COLORS = {
    "bg_dark": "#1e1e1e",
    "bg_panel": "#252526",
    "bg_input": "#3c3c3c",
    "fg_main": "#cccccc",
    "accent": "#007acc",
    "success": "#4ec9b0",
    "warning": "#dcdcaa",
    "error": "#f44747",
    "selection": "#264f78"
}

def apply_style(root):
    style = ttk.Style()
    style.theme_use('clam')
    root.configure(bg=COLORS["bg_dark"])

    style.configure("TFrame", background=COLORS["bg_dark"])
    style.configure("TLabel", background=COLORS["bg_dark"], foreground=COLORS["fg_main"], font=("Segoe UI", 10))

    style.configure("TLabelframe", background=COLORS["bg_dark"], foreground=COLORS["accent"])
    style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)

    style.configure("Treeview", background=COLORS["bg_panel"], foreground=COLORS["fg_main"], fieldbackground=COLORS["bg_panel"], rowheight=28)
    style.map("Treeview", background=[('selected', COLORS["selection"])])

# ================= SCRAPER ENGINE =================
class DynamicScraper:
    def __init__(self, log_func):
        self.log = log_func
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.seen_urls = set()
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.seen_urls = set(json.load(f))
            except:
                self.seen_urls = set()

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
        if not res:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        data = {
            "会社名": "N/A",
            "電話番号": "N/A",
            "住所": "N/A",
            "求人URL": url,
            "求人タイトル": "N/A",
            "会社URL": "N/A"
        }

        try:
            # 求人タイトル
            title = soup.select_one("h1")
            if title:
                data["求人タイトル"] = title.get_text(strip=True)

            # 会社名
            company = soup.select_one(".company-name, .corp-name")
            if company:
                data["会社名"] = company.get_text(strip=True)

            # 住所
            address = soup.select_one(".company-info .address, .location")
            if address:
                data["住所"] = address.get_text(strip=True)

            # 会社URL
            company_link = soup.select_one("a[href*='company'], a[href*='corp']")
            if company_link:
                href = company_link.get("href")
                data["会社URL"] = href

                # 🔥 OPTIONAL: go deeper to get TEL
                company_res = self.safe_get(href)
                if company_res:
                    company_soup = BeautifulSoup(company_res.text, "html.parser")

                    tel = company_soup.find(text=lambda x: x and "TEL" in x)
                    if tel:
                        data["電話番号"] = tel.strip()

        except Exception as e:
            self.log(f"Parse error: {e}", "error")

        self.seen_urls.add(url)
        self.log(f"FETCHED: {url[:60]}...", "success")

        return data

    def process_task(self, task, gc):
        self.log(f"🚀 Starting Task: {task['name']}", "info")

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
            if not res:
                break

            soup = BeautifulSoup(res.text, "html.parser")

            links = []
            for a in soup.select(task['s_link']):
                href = a.get("href")
                if href:
                    if href.startswith("/") and task['prefix']:
                        href = task['prefix'].rstrip("/") + href
                    links.append(href.split("?")[0])

            links = list(set(links))
            self.log(f"Page {page}: Found {len(links)} links", "info")

            results = []
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(self.fetch_detail, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    r = f.result()
                    if r:
                        results.append(r)

            if results:
                headers = ["URL"] + list(task['fields'].keys())
                rows = [[r.get(h, "N/A") for h in headers] for r in results]
                ws.append_rows(rows)

            next_btn = soup.select_one("a[rel=next], .next")
            if next_btn and page < 50:
                url = next_btn.get("href")
                if url.startswith("/") and task['prefix']:
                    url = task['prefix'].rstrip("/") + url
                page += 1
            else:
                url = None

        self.save_cache()
        self.log(f"✅ Task {task['name']} Finished.", "success")

# ================= UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI DYNAMIC SCRAPER PRO")
        self.geometry("1300x850")
        apply_style(self)

        self.tasks = self.load_tasks()
        self.dynamic_fields = {}

        self.setup_ui()

    def setup_ui(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(container, width=450)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # TASK INPUTS
        self.e_name = tk.Entry(left)
        self.e_url = tk.Entry(left)
        self.e_s_link = tk.Entry(left)
        self.e_prefix = tk.Entry(left)
        self.e_sid = tk.Entry(left)
        self.e_tab = tk.Entry(left)

        for label, entry in [
            ("Task Name", self.e_name),
            ("Base URL", self.e_url),
            ("List Selector", self.e_s_link),
            ("Prefix", self.e_prefix),
            ("Sheet ID", self.e_sid),
            ("Tab", self.e_tab)
        ]:
            ttk.Label(left, text=label).pack(anchor="w")
            entry.pack(fill="x", pady=2)

        # FIELD INPUT
        ttk.Separator(left).pack(fill="x", pady=10)

        self.field_name = tk.Entry(left)
        self.field_selector = tk.Entry(left)

        ttk.Label(left, text="Field Name").pack(anchor="w")
        self.field_name.pack(fill="x")

        ttk.Label(left, text="Selector").pack(anchor="w")
        self.field_selector.pack(fill="x")

        ttk.Button(left, text="➕ Add Field", command=self.add_field).pack(fill="x", pady=5)

        self.tree = ttk.Treeview(left, columns=("name", "selector"), show="headings", height=6)
        self.tree.heading("name", text="Field")
        self.tree.heading("selector", text="Selector")
        self.tree.pack(fill="x")

        ttk.Button(left, text="🗑 Remove Selected", command=self.remove_field).pack(fill="x", pady=5)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="ADD TASK", command=self.add_task).pack(fill="x", pady=5)
        ttk.Button(left, text="START", command=self.start_thread).pack(fill="x")

        # LOG
        right = ttk.Frame(container)
        right.pack(side="right", fill="both", expand=True)

        self.log_box = scrolledtext.ScrolledText(right)
        self.log_box.pack(fill="both", expand=True)

    def log(self, msg, tag="info"):
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)

    def add_field(self):
        name = self.field_name.get().strip()
        selector = self.field_selector.get().strip()

        if not name or not selector:
            messagebox.showwarning("Warning", "Fill field")
            return

        self.dynamic_fields[name] = selector
        self.tree.insert("", "end", values=(name, selector))

        self.field_name.delete(0, tk.END)
        self.field_selector.delete(0, tk.END)

    def remove_field(self):
        selected = self.tree.selection()
        if not selected:
            return

        for item in selected:
            values = self.tree.item(item, "values")
            if values:
                name = values[0]
                self.dynamic_fields.pop(name, None)
            self.tree.delete(item)

    def add_task(self):
        task = {
            "name": self.e_name.get(),
            "url": self.e_url.get(),
            "s_link": self.e_s_link.get(),
            "prefix": self.e_prefix.get(),
            "sheet_id": self.e_sid.get(),
            "tab": self.e_tab.get(),
            "fields": self.dynamic_fields.copy()
        }
        self.tasks.append(task)
        self.save_tasks()
        self.log("Task added")

    def load_tasks(self):
        if os.path.exists(CONFIG_FILE):
            return json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
        return []

    def save_tasks(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=2)

    def start_thread(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
        gc = gspread.authorize(creds)

        scraper = DynamicScraper(self.log)

        for task in self.tasks:
            scraper.process_task(task, gc)

if __name__ == "__main__":
    app = App()
    app.mainloop()

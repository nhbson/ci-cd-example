import os
import json
import random
import time
import threading
import csv
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import gspread
import requests
import urllib3
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# Suppress insecure request warnings from verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SERVICE_ACCOUNT_FILE = "service-account.json"
CACHE_FILE = "cache.json"

# ================= LEVEL 5 CORE =================
class SmartFetcher:
    def __init__(self, log):
        self.log = log
        self.session = requests.Session()

    def fetch(self, url):
        try:
            # Added verify=False to fix SSL errors and added realistic headers
            res = self.session.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }, verify=False)
            
            if res.status_code == 200:
                # Fix for Japanese characters
                res.encoding = res.apparent_encoding
                return res
        except Exception as e:
            self.log(f"[ERROR] Fetch {url}: {e}")
        return None


class AISelector:
    def extract(self, soup, keywords):
        # CLEANUP: Remove script and style elements so we don't scrape JS code
        for script_or_style in soup(["script", "style", "header", "footer", "nav", "noscript"]):
            script_or_style.decompose()

        # Target specific tags to avoid capturing large blocks of irrelevant text
        potential_tags = ["td", "th", "p", "span", "div", "h1", "h2", "dt", "dd"]

        for kw in keywords:
            # Search for the keyword in visible text
            el = soup.find(potential_tags, string=lambda t: t and kw.lower() in t.lower())
            if el:
                # Get the text, clean it, and ensure it's not a massive block of code
                val = el.get_text(strip=True)
                if 2 < len(val) < 200:
                    return val

        # Fallback to Title/H1
        for tag in ["h1", "title"]:
            el = soup.find(tag)
            if el:
                val = el.get_text(strip=True)
                if val and len(val) < 200:
                    return val

        return "N/A"


def extract_links(base_url, soup):
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        if any(x in full for x in ["javascript:", "#", "tel:", "mailto:"]):
            continue
        links.add(full.split("?")[0])
    return list(links)


class Level5Scraper:
    def __init__(self, log):
        self.log = log
        self.fetcher = SmartFetcher(log)
        self.ai = AISelector()
        self.seen = set()

    def scrape(self, url):
        res = self.fetcher.fetch(url)
        if not res:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        links = extract_links(url, soup)
        self.log(f"[LINKS FOUND] {len(links)}")

        results = []
        # Limit to 20 links per task to prevent long hangs
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(self.scrape_detail, l) for l in links[:20]]
            for f in as_completed(futures):
                r = f.result()
                if r:
                    results.append(r)

        return results

    def scrape_detail(self, url):
        if url in self.seen:
            return None

        res = self.fetcher.fetch(url)
        if not res:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Specific Japanese keywords added for better extraction on Mynavi
        title = self.ai.extract(soup, ["title", "job", "職種", "求人"])
        company = self.ai.extract(soup, ["company", "会社名", "企業名", "商号"])
        address = self.ai.extract(soup, ["address", "所在地", "住所", "アクセス"])

        # String Cleanup: Remove newlines, tabs, and excess spaces for GSheets compatibility
        def clean_str(s):
            return " ".join(str(s).split())

        title = clean_str(title)
        company = clean_str(company)
        address = clean_str(address)

        # Safety check: If company name looks like code, ignore it
        if "{" in company or "function" in company or "dataLayer" in company:
            company = "N/A (Script Block)"

        self.seen.add(url)
        self.log(f"[DETAIL] {company[:40]}...")

        return [company, address, url, title]


# ================= DEVTOOLS =================
class DevToolsWindow(tk.Toplevel):
    def __init__(self, master, log_func):
        super().__init__(master)
        self.title("DevTools")
        self.geometry("1200x800")

        self.log = log_func
        self.driver = None

        self.setup_ui()

    def setup_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=5, pady=5)

        self.url_entry = ttk.Entry(top)
        self.url_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(top, text="Open", command=self.open_browser).pack(side="left")
        ttk.Button(top, text="Get Links", command=self.extract_links).pack(side="left")

        self.result_box = scrolledtext.ScrolledText(self)
        self.result_box.pack(fill="both", expand=True)

    def open_browser(self):
        try:
            if self.driver:
                self.driver.quit()

            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            self.driver = uc.Chrome(options=options)
            self.driver.get(self.url_entry.get())

        except Exception as e:
            self.log(f"[ERROR] Browser: {e}")

    def extract_links(self):
        try:
            els = self.driver.find_elements(By.CSS_SELECTOR, "a")
            links = list(set([e.get_attribute("href") for e in els if e.get_attribute("href")]))

            self.result_box.delete("1.0", tk.END)
            self.result_box.insert(tk.END, "\n".join(links[:100]))

        except Exception as e:
            self.log(f"[ERROR] Link Extraction: {e}")


# ================= MAIN APP =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🔥 AI Scraper Level 5 (Fixed)")
        self.geometry("1100x800")

        self.tasks = self.load_tasks()
        self.setup_ui()

    def setup_ui(self):
        frame = ttk.LabelFrame(self, text="Task Config")
        frame.pack(fill="x", padx=10, pady=10)

        self.entries = {}
        fields = [
            "name", "url", "link_css", "prefix",
            "title", "company", "address",
            "sheet_id", "tab"
        ]

        for i, f in enumerate(fields):
            ttk.Label(frame, text=f).grid(row=i, column=0, sticky="w", padx=5)
            e = ttk.Entry(frame, width=60)
            e.grid(row=i, column=1, pady=2)
            self.entries[f] = e

        btn_container = ttk.Frame(frame)
        btn_container.grid(row=len(fields), column=1, sticky="e", pady=10)
        ttk.Button(btn_container, text="Add Task", command=self.add_task).pack(side="left", padx=5)
        ttk.Button(btn_container, text="Delete Task", command=self.delete_task).pack(side="left")

        self.tree = ttk.Treeview(self, columns=("Name", "URL"), show="headings", height=8)
        self.tree.heading("Name", text="Name")
        self.tree.heading("URL", text="URL")
        self.tree.pack(fill="x", padx=10)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=10)

        ttk.Button(btns, text="▶ RUN ALL TASKS", command=self.run).pack(side="left", padx=5)
        ttk.Button(btns, text="🛠 DevTools", command=self.open_devtools).pack(side="left")

        self.log_box = scrolledtext.ScrolledText(self, height=20, bg="#1e1e1e", fg="#00ff00")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=5)

        self.refresh()

    def log(self, msg):
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)

    def add_task(self):
        task = {k: v.get() for k, v in self.entries.items()}
        if not task["name"] or not task["url"] or not task["sheet_id"]:
            messagebox.showwarning("Warning", "Fill in Name, URL, and Sheet ID")
            return
        self.tasks.append(task)
        self.save_tasks()
        self.refresh()

    def delete_task(self):
        selected = self.tree.selection()
        if not selected: return
        index = self.tree.index(selected[0])
        if messagebox.askyesno("Confirm", "Delete selected task?"):
            self.tasks.pop(index)
            self.save_tasks()
            self.refresh()

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in self.tasks: self.tree.insert("", "end", values=(t["name"], t["url"]))

    def save_tasks(self):
        with open("training_config.json", "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=2, ensure_ascii=False)

    def load_tasks(self):
        if os.path.exists("training_config.json"):
            with open("training_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def run(self):
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                self.log(f"[ERROR] {SERVICE_ACCOUNT_FILE} not found!")
                return

            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
            gc = gspread.authorize(creds)
            scraper = Level5Scraper(self.log)

            for task in self.tasks:
                self.log(f"\n[TASK] Starting: {task['name']}")
                results = scraper.scrape(task["url"])

                if results:
                    try:
                        sh = gc.open_by_key(task["sheet_id"])
                        ws = sh.worksheet(task["tab"])
                        ws.append_rows(results)
                        self.log(f"[SUCCESS] Uploaded {len(results)} rows to {task['name']}")
                    except Exception as sheet_err:
                        self.log(f"[ERROR] Google Sheet Sync: {sheet_err}")
                else:
                    self.log(f"[INFO] No valid data extracted for {task['name']}")

            self.log("\n[FINISHED] All tasks completed.")
            messagebox.showinfo("Done", "All tasks completed!")

        except Exception as e:
            self.log(f"[CRITICAL ERROR] {e}")

    def open_devtools(self):
        DevToolsWindow(self, self.log)


if __name__ == "__main__":
    App().mainloop()
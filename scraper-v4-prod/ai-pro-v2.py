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
    
    style.configure("TLabelframe", background=COLORS["bg_dark"], foreground=COLORS["accent"], bordercolor=COLORS["bg_input"])
    style.configure("TLabelframe.Label", background=COLORS["bg_dark"], foreground=COLORS["accent"], font=("Segoe UI", 10, "bold"))
    
    style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6, background=COLORS["bg_input"], foreground="white")
    style.map("TButton", background=[('active', COLORS["accent"]), ('pressed', COLORS["selection"])])
    
    style.configure("Treeview", 
                    background=COLORS["bg_panel"], 
                    foreground=COLORS["fg_main"], 
                    fieldbackground=COLORS["bg_panel"], 
                    rowheight=30,
                    borderwidth=0)
    style.map("Treeview", background=[('selected', COLORS["selection"])])
    style.configure("Treeview.Heading", background=COLORS["bg_input"], foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0)

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
        for field_name, selector in fields.items():
            el = soup.select_one(selector) if selector else None
            data[field_name] = el.get_text(" ", strip=True) if el else "N/A"
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
            self.log(f"Page {page}: Found {len(links)} links", "info")
            results = []
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(self.fetch_detail, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    r = f.result()
                    if r: results.append(r)
            if results:
                headers = ["URL"] + list(task['fields'].keys())
                rows_to_upload = [[res.get(h, "N/A") for h in headers] for res in results]
                ws.append_rows(rows_to_upload)
            next_btn = soup.select_one("a[rel=next], .next")
            if next_btn and page < 50:
                url = next_btn.get("href")
                if url.startswith("/") and task['prefix']:
                    url = task['prefix'].rstrip("/") + url
                page += 1
            else: url = None
        self.save_cache()
        self.log(f"✅ Task {task['name']} Finished.", "success")

# ================= MODERN UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI DYNAMIC SCRAPER PRO")
        self.geometry("1200x850")
        apply_style(self)
        self.tasks = self.load_tasks()
        self.dynamic_fields = {} 
        self.setup_ui()

    def setup_ui(self):
        header = tk.Frame(self, bg=COLORS["bg_panel"], height=60)
        header.pack(fill="x", side="top")
        tk.Label(header, text="DASHBOARD // DYNAMIC SCRAPER", font=("Segoe UI", 14, "bold"), bg=COLORS["bg_panel"], fg=COLORS["accent"]).pack(pady=15, padx=20, side="left")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # FIX: Define width in Frame, remove from .pack()
        left_panel = ttk.Frame(container, width=400)
        left_panel.pack(side="left", fill="y", expand=False)
        left_panel.pack_propagate(False) # Ensures the frame keeps its 400px width

        config_frame = ttk.LabelFrame(left_panel, text=" 1. CONFIGURATION ", padding=15)
        config_frame.pack(fill="x", pady=(0, 10))

        self.create_input(config_frame, "Task Name:", "e_name", 0)
        self.create_input(config_frame, "Base URL:", "e_url", 1)
        self.create_input(config_frame, "List Item CSS:", "e_s_link", 2)
        self.create_input(config_frame, "URL Prefix:", "e_prefix", 3)

        fields_frame = ttk.LabelFrame(left_panel, text=" 2. SELECTORS ", padding=15)
        fields_frame.pack(fill="x", pady=10)

        field_input_row = ttk.Frame(fields_frame)
        field_input_row.pack(fill="x")
        
        self.f_name = tk.Entry(field_input_row, bg=COLORS["bg_input"], fg="white", insertbackground="white", borderwidth=0, font=("Segoe UI", 10))
        self.f_name.insert(0, "Title")
        self.f_name.pack(side="left", padx=2, ipady=4, expand=True, fill="x")
        
        self.f_selector = tk.Entry(field_input_row, bg=COLORS["bg_input"], fg="white", insertbackground="white", borderwidth=0, font=("Segoe UI", 10))
        self.f_selector.insert(0, "h1.product-title")
        self.f_selector.pack(side="left", padx=2, ipady=4, expand=True, fill="x")

        ttk.Button(field_input_row, text="+", width=3, command=self.add_field_to_list).pack(side="left", padx=5)

        self.fields_display = tk.Text(fields_frame, height=5, bg="#111", fg=COLORS["success"], font=("Consolas", 10), borderwidth=0)
        self.fields_display.pack(fill="x", pady=5)

        gs_frame = ttk.LabelFrame(left_panel, text=" 3. GOOGLE SHEETS ", padding=15)
        gs_frame.pack(fill="x", pady=10)
        self.create_input(gs_frame, "Sheet ID:", "e_sid", 0)
        self.create_input(gs_frame, "Tab Name:", "e_tab", 1)

        ttk.Button(left_panel, text="ADD TO QUEUE", command=self.add_task).pack(fill="x", pady=10)

        # RIGHT PANEL
        right_panel = ttk.Frame(container)
        right_panel.pack(side="right", fill="both", expand=True, padx=(20, 0))

        self.tree = ttk.Treeview(right_panel, columns=("Name", "Fields"), show="headings", height=8)
        self.tree.heading("Name", text="TASK NAME")
        self.tree.heading("Fields", text="FIELD COUNT")
        self.tree.pack(fill="x", pady=(0, 10))
        
        self.tree.tag_configure('odd', background=COLORS["bg_dark"])
        self.tree.tag_configure('even', background=COLORS["bg_panel"])

        btn_row = ttk.Frame(right_panel)
        btn_row.pack(fill="x", pady=5)
        ttk.Button(btn_row, text="▶ START ALL TASKS", command=self.start_thread).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(btn_row, text="CLEAR LOGS", command=lambda: self.log_box.delete("1.0", tk.END)).pack(side="left", padx=2)
        ttk.Button(btn_row, text="❌ REMOVE TASK", command=self.remove_task).pack(side="left", padx=2)

        self.log_box = scrolledtext.ScrolledText(right_panel, bg="#111", fg=COLORS["fg_main"], font=("Consolas", 10), borderwidth=0)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_config("info", foreground=COLORS["fg_main"])
        self.log_box.tag_config("success", foreground=COLORS["success"])
        self.log_box.tag_config("error", foreground=COLORS["error"])
        
        self.refresh_table()

    def remove_task(self):
        selected = self.tree.selection()
        
        if not selected:
            messagebox.showwarning("Warning", "Please select a task to remove.")
            return

        # Get selected index
        index = self.tree.index(selected[0])

        task_name = self.tasks[index]['name']

        confirm = messagebox.askyesno(
            "Confirm",
            f"Are you sure you want to delete task:\n{task_name}?"
        )

        if confirm:
            # Remove from list
            self.tasks.pop(index)

            # Save & refresh UI
            self.save_tasks()
            self.refresh_table()

            self.log(f"🗑 Task removed: {task_name}", "info")
            
    def create_input(self, parent, label, var_name, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        entry = tk.Entry(parent, bg=COLORS["bg_input"], fg="white", insertbackground="white", borderwidth=0, font=("Segoe UI", 10))
        entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0), ipady=4)
        parent.columnconfigure(1, weight=1)
        setattr(self, var_name, entry)

    def add_field_to_list(self):
        name = self.f_name.get().strip()
        sel = self.f_selector.get().strip()
        if name and sel:
            self.dynamic_fields[name] = sel
            self.fields_display.insert(tk.END, f" ✔ {name}: {sel}\n")
            self.f_name.delete(0, tk.END)
            self.f_selector.delete(0, tk.END)

    def add_task(self):
        task = {
            "name": self.e_name.get(), "url": self.e_url.get(), "s_link": self.e_s_link.get(),
            "prefix": self.e_prefix.get(), "fields": self.dynamic_fields.copy(),
            "sheet_id": self.e_sid.get(), "tab": self.e_tab.get(),
        }
        if not task["name"] or not task["fields"]:
            messagebox.showerror("Error", "Task Name and Fields are required.")
            return
        self.tasks.append(task)
        self.save_tasks()
        self.refresh_table()
        self.dynamic_fields = {}
        self.fields_display.delete("1.0", tk.END)

    def log(self, msg, tag="info"):
        self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n", tag)
        self.log_box.see(tk.END)

    def refresh_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for idx, t in enumerate(self.tasks):
            tag = 'even' if idx % 2 == 0 else 'odd'
            self.tree.insert("", "end", values=(t['name'].upper(), len(t['fields'])), tags=(tag,))

    def load_tasks(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        return []

    def save_tasks(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(self.tasks, f, indent=2)

    def start_thread(self):
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
            gc = gspread.authorize(creds)
            scraper = DynamicScraper(self.log)
            for task in self.tasks: scraper.process_task(task, gc)
            messagebox.showinfo("Done", "All tasks finished!")
        except Exception as e: self.log(f"ERROR: {str(e)}", "error")

if __name__ == "__main__":
    app = App()
    app.mainloop()
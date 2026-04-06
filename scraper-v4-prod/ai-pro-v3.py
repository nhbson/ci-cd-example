import os
import json
import random
import time
import threading
import re
import math
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse, urljoin

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

# ================= DYNAMIC CONFIG & UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # All "Hardcoded" values are moved into this dynamic dictionary
        self.config = {
            "auth_file": "service-account.json",
            "tasks_file": "scraper_config.json",
            "theme": {
                "bg": "#f5f6fa",
                "panel": "#ffffff",
                "fg": "#2d3436",
                "accent": "#0984e3",
                "success": "#00b894",
                "error": "#d63031",
                "log_bg": "#1e272e",
                "log_fg": "#d2dae2"
            }
        }

        self.tasks = []
        self.dynamic_fields = {}
        self.selected_task_index = None
        self.running = False
        self.stop_flag = False

        self.title("UNIVERSAL DYNAMIC SCRAPER")
        self.geometry("1250x900")
        self.setup_ui()
        self.load_tasks_from_disk()

    def apply_styles(self):
        t = self.config["theme"]
        self.configure(bg=t["bg"])
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=t["bg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"])
        style.configure("TLabelframe", background=t["bg"])
        style.configure("TLabelframe.Label", background=t["bg"], foreground=t["accent"], font=("Arial", 10, "bold"))

    def setup_ui(self):
        self.apply_styles()
        t = self.config["theme"]

        # Main Container
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        # --- TOP: FILE PATHS ---
        top = ttk.LabelFrame(main, text="Global Configuration")
        top.pack(fill="x", side="top", pady=5)

        ttk.Label(top, text="Service Account:").grid(row=0, column=0, padx=5, pady=5)
        self.ui_auth_path = tk.Entry(top, width=40)
        self.ui_auth_path.grid(row=0, column=1)
        self.ui_auth_path.insert(0, self.config["auth_file"])
        ttk.Button(top, text="Browse", command=self.browse_auth).grid(row=0, column=2, padx=5)

        ttk.Label(top, text="Tasks JSON:").grid(row=0, column=3, padx=5)
        self.ui_conf_path = tk.Entry(top, width=30)
        self.ui_conf_path.grid(row=0, column=4)
        self.ui_conf_path.insert(0, self.config["tasks_file"])
        ttk.Button(top, text="Load", command=self.load_tasks_from_disk).grid(row=0, column=5, padx=5)

        # --- MIDDLE: EDITOR ---
        body = ttk.Frame(main)
        body.pack(fill="both", expand=True, pady=10)

        # LEFT (Task Editor)
        left = ttk.Frame(body, width=450)
        left.pack(side="left", fill="y", padx=5)

        ttk.Label(left, text="Saved Tasks:").pack(anchor="w")
        self.ui_task_list = tk.Listbox(left, height=6)
        self.ui_task_list.pack(fill="x", pady=2)
        self.ui_task_list.bind("<<ListboxSelect>>", self.on_task_click)

        self.ui_name = self.field(left, "Task Name")
        self.ui_url = self.field(left, "Initial URL (Page 1)")
        self.ui_link_sel = self.field(left, "Item Link CSS (e.g. .job-link)")
        
        pg = ttk.LabelFrame(left, text="Dynamic Paging Logic")
        pg.pack(fill="x", pady=5)
        self.ui_stats_sel = self.field(pg, "Stats CSS (e.g. .pager-display)")
        self.ui_page_key = self.field(pg, "URL Page Param (e.g. p)")
        
        self.ui_sid = self.field(left, "Google Sheet ID")
        self.ui_tab = self.field(left, "Tab Name")

        # Selectors
        sel_frame = ttk.LabelFrame(left, text="Data Column : CSS Selector")
        sel_frame.pack(fill="x", pady=5)
        self.ui_f_name = tk.Entry(sel_frame); self.ui_f_name.pack(fill="x", padx=2)
        self.ui_f_sel = tk.Entry(sel_frame); self.ui_f_sel.pack(fill="x", padx=2)
        f_btns = ttk.Frame(sel_frame); f_btns.pack(fill="x")
        ttk.Button(f_btns, text="Add Field", command=self.add_field).pack(side="left", expand=True)
        ttk.Button(f_btns, text="Clear", command=self.clear_fields).pack(side="left", expand=True)
        self.ui_fields_box = tk.Listbox(sel_frame, height=4); self.ui_fields_box.pack(fill="x")

        ttk.Button(left, text="SAVE TASK", command=self.save_task).pack(fill="x", pady=5)
        tk.Button(left, text="DELETE TASK", bg=t["error"], fg="white", command=self.remove_task).pack(fill="x")

        # RIGHT (Logs)
        right = ttk.Frame(body)
        right.pack(side="right", fill="both", expand=True, padx=5)

        btns = ttk.Frame(right); btns.pack(fill="x")
        ttk.Button(btns, text="▶ START", command=self.run).pack(side="left", expand=True, fill="x")
        ttk.Button(btns, text="🛑 STOP", command=self.stop).pack(side="left", expand=True, fill="x")

        self.log_box = scrolledtext.ScrolledText(right, bg=t["log_bg"], fg=t["log_fg"], font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, pady=5)

    # --- UI HELPERS ---
    def field(self, parent, label):
        ttk.Label(parent, text=label).pack(anchor="w")
        e = tk.Entry(parent); e.pack(fill="x", pady=1); return e

    def browse_auth(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p: self.ui_auth_path.delete(0, tk.END); self.ui_auth_path.insert(0, p)

    def add_field(self):
        n, s = self.ui_f_name.get().strip(), self.ui_f_sel.get().strip()
        if n and s: self.dynamic_fields[n] = s; self.refresh_fields_list()

    def clear_fields(self):
        self.dynamic_fields = {}; self.refresh_fields_list()

    def refresh_fields_list(self):
        self.ui_fields_box.delete(0, tk.END)
        for k, v in self.dynamic_fields.items(): self.ui_fields_box.insert(tk.END, f"{k}: {v}")

    def on_task_click(self, event):
        if not self.ui_task_list.curselection(): return
        idx = self.ui_task_list.curselection()[0]
        task = self.tasks[idx]
        self.selected_task_index = idx
        self.ui_name.delete(0, tk.END); self.ui_name.insert(0, task['name'])
        self.ui_url.delete(0, tk.END); self.ui_url.insert(0, task['url'])
        self.ui_link_sel.delete(0, tk.END); self.ui_link_sel.insert(0, task['s_link'])
        self.ui_stats_sel.delete(0, tk.END); self.ui_stats_sel.insert(0, task['stats_sel'])
        self.ui_page_key.delete(0, tk.END); self.ui_page_key.insert(0, task['page_key'])
        self.ui_sid.delete(0, tk.END); self.ui_sid.insert(0, task['sheet_id'])
        self.ui_tab.delete(0, tk.END); self.ui_tab.insert(0, task['tab'])
        self.dynamic_fields = task['fields'].copy(); self.refresh_fields_list()

    def save_task(self):
        task = {
            "name": self.ui_name.get(), "url": self.ui_url.get(), "s_link": self.ui_link_sel.get(),
            "stats_sel": self.ui_stats_sel.get(), "page_key": self.ui_page_key.get(),
            "sheet_id": self.ui_sid.get(), "tab": self.ui_tab.get(), "fields": self.dynamic_fields
        }
        if self.selected_task_index is not None: self.tasks[self.selected_task_index] = task
        else: self.tasks.append(task)
        self.save_tasks_to_disk()

    def remove_task(self):
        if self.selected_task_index is not None: del self.tasks[self.selected_task_index]; self.save_tasks_to_disk()

    def load_tasks_from_disk(self):
        path = self.ui_conf_path.get()
        if os.path.exists(path):
            with open(path, 'r') as f: self.tasks = json.load(f)
            self.refresh_task_list_ui(); self.log(f"Tasks loaded from {path}")

    def save_tasks_to_disk(self):
        path = self.ui_conf_path.get()
        with open(path, 'w') as f: json.dump(self.tasks, f, indent=2)
        self.refresh_task_list_ui(); self.log(f"Tasks saved to {path}", "success")

    def refresh_task_list_ui(self):
        self.ui_task_list.delete(0, tk.END)
        for t in self.tasks: self.ui_task_list.insert(tk.END, t['name'])

    def log(self, msg, status="info"):
        color = self.config["theme"]["success"] if status == "success" else self.config["theme"]["error"] if status == "error" else self.config["theme"]["log_fg"]
        self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def stop(self): self.stop_flag = True

    def run(self):
        if self.running: return
        self.running = True; self.stop_flag = False
        threading.Thread(target=self.engine_start, daemon=True).start()

    # ================= CORE ENGINE =================
    def engine_start(self):
        auth = self.ui_auth_path.get()
        if not os.path.exists(auth): 
            self.log("❌ Auth JSON not found", "error"); self.running = False; return
        
        try:
            scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(auth, scope)
            gc = gspread.authorize(creds)
            
            for task in self.tasks:
                if self.stop_flag: break
                self.process_task(task, gc)
                
            self.log("🏁 ALL DONE", "success")
        except Exception as e: self.log(f"❌ Global Error: {e}", "error")
        finally: self.running = False

    def process_task(self, task, gc):
        self.log(f"🚀 Running: {task['name']}")
        session = requests.Session()
        session.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # 1. Access Google Sheet + Auto-Tab Creation
        try:
            sh = gc.open_by_key(task['sheet_id'])
            try:
                ws = sh.worksheet(task['tab'])
            except gspread.exceptions.WorksheetNotFound:
                self.log(f"Creating missing tab: {task['tab']}")
                ws = sh.add_worksheet(title=task['tab'], rows="1000", cols="20")
        except Exception as e:
            self.log(f"❌ Google Sheet Access Error: {e}", "error"); return

        # 2. Page 1 for Calculation
        try:
            res = session.get(task['url'], timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            self.log(f"❌ Failed to load site: {e}", "error"); return

        # Calculation
        total_pages = 1
        stats_el = soup.select_one(task['stats_sel'])
        if stats_el:
            nums = [int(n) for n in re.findall(r'\d+', stats_el.get_text())]
            if len(nums) >= 3:
                # Based on: "1 to 20 (Total 3187)" -> nums[0]=1, nums[1]=20, nums[2]=3187
                items_per_page = (nums[1] - nums[0]) + 1
                total_pages = math.ceil(nums[2] / items_per_page)
                self.log(f"📊 Detected: {nums[2]} items, {items_per_page}/page -> {total_pages} pages")

        # 3. Main Loop
        for p in range(1, total_pages + 1):
            if self.stop_flag: break
            
            # Construct URL
            u = urlparse(task['url'])
            q = parse_qs(u.query); q[task['page_key']] = [str(p)]
            cur_url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))

            self.log(f"📄 Page {p}/{total_pages}")
            if p > 1:
                p_res = session.get(cur_url)
                soup = BeautifulSoup(p_res.text, "html.parser")

            links = [urljoin(cur_url, a.get("href")) for a in soup.select(task['s_link']) if a.get("href")]
            
            results = []
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(self.fetch_detail, session, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    if self.stop_flag: break
                    r = f.result()
                    if r: results.append(r)

            if results:
                headers = ["URL"] + list(task['fields'].keys())
                rows = [[r.get(h, "") for h in headers] for r in results]
                ws.append_rows(rows)
                self.log(f"✅ Saved {len(results)} rows from page {p}", "success")

    def fetch_detail(self, session, url, fields):
        try:
            time.sleep(random.uniform(0.6, 1.2))
            r = session.get(url, timeout=10)
            if r.status_code != 200: return None
            s = BeautifulSoup(r.text, "html.parser")
            data = {"URL": url}
            for k, v in fields.items():
                el = s.select_one(v)
                data[k] = el.get_text(strip=True) if el else "N/A"
            return data
        except: return None

if __name__ == "__main__":
    App().mainloop()
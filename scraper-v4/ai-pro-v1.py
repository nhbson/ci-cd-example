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
# REPLACED REQUESTS WITH CURL_CFFI FOR BYPASSING BLOCKS
from curl_cffi import requests as crequests 
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

# ================= DYNAMIC CONFIG & UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()

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

        self.title("UNIVERSAL SCRAPER PRO - DASHBOARD")
        self.geometry("1300x950")
        self.apply_styles()
        self.setup_ui()
        self.load_tasks_from_disk()

    def apply_styles(self):
        t = self.config["theme"]
        self.configure(bg=t["bg"])
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=t["bg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"])
        style.configure("TButton", font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=t["accent"])
        style.configure("TLabelframe", background=t["bg"])
        style.configure("TLabelframe.Label", background=t["bg"], foreground=t["accent"], font=("Segoe UI", 10, "bold"))

    def setup_ui(self):
        # Main Navigation
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Task Manager
        self.tab_editor = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_editor, text=" ⚙️ Task Manager ")

        # Tab 2: Raw JSON Editor (TextEdit Mode)
        self.tab_json = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_json, text=" 📝 JSON Expert Mode ")

        # Tab 3: Console
        self.tab_console = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_console, text=" 🖥️ Live Console ")

        self.setup_editor_tab()
        self.setup_json_tab()
        self.setup_console_tab()
        
        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_editor_tab(self):
        main = ttk.Frame(self.tab_editor)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Left Column: List and Global Settings
        left_col = ttk.Frame(main, width=350)
        left_col.pack(side="left", fill="y", padx=5)

        # Global Config
        glob = ttk.LabelFrame(left_col, text="Global Config")
        glob.pack(fill="x", pady=(0, 10))
        self.ui_auth_path = self.create_label_entry(glob, "Auth JSON:", self.config["auth_file"], browse=True)
        self.ui_conf_path = self.create_label_entry(glob, "Tasks JSON:", self.config["tasks_file"])

        # Task List
        list_frame = ttk.LabelFrame(left_col, text="Saved Tasks")
        list_frame.pack(fill="both", expand=True)
        self.ui_task_list = tk.Listbox(list_frame, font=("Segoe UI", 10), bd=0, highlightthickness=0)
        self.ui_task_list.pack(fill="both", expand=True, padx=5, pady=5)
        self.ui_task_list.bind("<<ListboxSelect>>", self.on_task_click)
        
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="✚ New Task", command=self.clear_task_form).pack(side="left", expand=True, fill="x")
        ttk.Button(btn_frame, text="🗑 Delete", command=self.remove_task).pack(side="left", expand=True, fill="x")

        # Right Column: Editor
        right_col = ttk.Frame(main)
        right_col.pack(side="right", fill="both", expand=True, padx=5)

        edit_scroll = tk.Canvas(right_col, highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_col, orient="vertical", command=edit_scroll.yview)
        self.scrollable_frame = ttk.Frame(edit_scroll)

        self.scrollable_frame.bind("<Configure>", lambda e: edit_scroll.configure(scrollregion=edit_scroll.bbox("all")))
        edit_scroll.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        edit_scroll.configure(yscrollcommand=scrollbar.set)
        
        edit_scroll.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Fields
        self.ui_name = self.field(self.scrollable_frame, "Task Display Name")
        self.ui_url = self.field(self.scrollable_frame, "Initial URL (Page 1)")
        self.ui_link_sel = self.field(self.scrollable_frame, "Item Link CSS (e.g. .job-link)")
        
        pg = ttk.LabelFrame(self.scrollable_frame, text="Pagination Logic")
        pg.pack(fill="x", pady=10)
        self.ui_stats_sel = self.field(pg, "Stats CSS (e.g. .pager-display)")
        self.ui_page_key = self.field(pg, "URL Page Parameter (e.g. 'p' or 'page')")
        
        gs = ttk.LabelFrame(self.scrollable_frame, text="Google Sheets Target")
        gs.pack(fill="x", pady=10)
        self.ui_sid = self.field(gs, "Sheet ID")
        self.ui_tab = self.field(gs, "Tab Name")

        # Selectors
        sel_frame = ttk.LabelFrame(self.scrollable_frame, text="Data Extraction (Column Name : CSS Selector)")
        sel_frame.pack(fill="x", pady=10)
        
        f_input = ttk.Frame(sel_frame)
        f_input.pack(fill="x", padx=5, pady=5)
        self.ui_f_name = tk.Entry(f_input, width=20); self.ui_f_name.pack(side="left", padx=2)
        tk.Label(f_input, text=":").pack(side="left")
        self.ui_f_sel = tk.Entry(f_input); self.ui_f_sel.pack(side="left", fill="x", expand=True, padx=2)
        
        f_btns = ttk.Frame(sel_frame)
        f_btns.pack(fill="x", padx=5)
        ttk.Button(f_btns, text="Add/Update Field", command=self.add_field).pack(side="left", expand=True, fill="x")
        ttk.Button(f_btns, text="Clear Fields", command=self.clear_fields).pack(side="left", expand=True, fill="x")
        
        self.ui_fields_box = tk.Listbox(sel_frame, height=5)
        self.ui_fields_box.pack(fill="x", padx=5, pady=5)
        self.ui_fields_box.bind("<<ListboxSelect>>", self.on_field_click)

        ttk.Button(self.scrollable_frame, text="💾 SAVE TASK CONFIGURATION", command=self.save_task, style="Header.TLabel").pack(fill="x", pady=20)

    def setup_json_tab(self):
        label = ttk.Label(self.tab_json, text="Direct JSON Editor (TextEdit Mode)", style="Header.TLabel")
        label.pack(pady=10)
        self.json_editor = scrolledtext.ScrolledText(self.tab_json, font=("Consolas", 11), bg="#2d3436", fg="#ecf0f1")
        self.json_editor.pack(fill="both", expand=True, padx=10, pady=10)
        btn_f = ttk.Frame(self.tab_json); btn_f.pack(fill="x", pady=10)
        ttk.Button(btn_f, text="Pull from UI", command=self.sync_to_json_text).pack(side="left", padx=10)
        ttk.Button(btn_f, text="Push to UI & Save", command=self.sync_from_json_text).pack(side="left", padx=10)

    def setup_console_tab(self):
        t = self.config["theme"]; top = ttk.Frame(self.tab_console); top.pack(fill="x", pady=10, padx=10)
        ttk.Button(top, text="▶ RUN SELECTED TASK", command=lambda: self.run(mode="selected")).pack(side="left", padx=5)
        ttk.Button(top, text="⏩ RUN ALL TASKS", command=lambda: self.run(mode="all")).pack(side="left", padx=5)
        ttk.Button(top, text="🛑 STOP ENGINE", command=self.stop).pack(side="left", padx=5)
        self.log_box = scrolledtext.ScrolledText(self.tab_console, bg=t["log_bg"], fg=t["log_fg"], font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    # --- UI HELPERS ---
    def create_label_entry(self, parent, txt, default, browse=False):
        frame = ttk.Frame(parent); frame.pack(fill="x", padx=5, pady=2); ttk.Label(frame, text=txt, width=15).pack(side="left")
        e = tk.Entry(frame); e.pack(side="left", fill="x", expand=True); e.insert(0, default)
        if browse: ttk.Button(frame, text="...", width=3, command=self.browse_auth).pack(side="right")
        return e
    def field(self, parent, label):
        frame = ttk.Frame(parent); frame.pack(fill="x", pady=5); ttk.Label(frame, text=label, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        e = tk.Entry(frame, font=("Segoe UI", 10)); e.pack(fill="x", pady=2); return e
    def browse_auth(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p: self.ui_auth_path.delete(0, tk.END); self.ui_auth_path.insert(0, p)
    def clear_task_form(self):
        self.selected_task_index = None; self.ui_task_list.selection_clear(0, tk.END)
        for e in [self.ui_name, self.ui_url, self.ui_link_sel, self.ui_stats_sel, self.ui_page_key, self.ui_sid, self.ui_tab, self.ui_f_name, self.ui_f_sel]: e.delete(0, tk.END)
        self.dynamic_fields = {}; self.refresh_fields_list(); self.status_var.set("New Task Mode")
    def add_field(self):
        n, s = self.ui_f_name.get().strip(), self.ui_f_sel.get().strip()
        if n and s: self.dynamic_fields[n] = s; self.refresh_fields_list(); self.ui_f_name.delete(0, tk.END); self.ui_f_sel.delete(0, tk.END)
    def on_field_click(self, event):
        if not self.ui_fields_box.curselection(): return
        idx = self.ui_fields_box.curselection()[0]; key = list(self.dynamic_fields.keys())[idx]
        self.ui_f_name.delete(0, tk.END); self.ui_f_name.insert(0, key); self.ui_f_sel.delete(0, tk.END); self.ui_f_sel.insert(0, self.dynamic_fields[key])
    def clear_fields(self): self.dynamic_fields = {}; self.refresh_fields_list()
    def refresh_fields_list(self):
        self.ui_fields_box.delete(0, tk.END)
        for k, v in self.dynamic_fields.items(): self.ui_fields_box.insert(tk.END, f"{k}: {v}")
    def on_task_click(self, event):
        if not self.ui_task_list.curselection(): return
        idx = self.ui_task_list.curselection()[0]; task = self.tasks[idx]; self.selected_task_index = idx
        self.ui_name.delete(0, tk.END); self.ui_name.insert(0, task['name'])
        self.ui_url.delete(0, tk.END); self.ui_url.insert(0, task['url'])
        self.ui_link_sel.delete(0, tk.END); self.ui_link_sel.insert(0, task['s_link'])
        self.ui_stats_sel.delete(0, tk.END); self.ui_stats_sel.insert(0, task['stats_sel'])
        self.ui_page_key.delete(0, tk.END); self.ui_page_key.insert(0, task['page_key'])
        self.ui_sid.delete(0, tk.END); self.ui_sid.insert(0, task['sheet_id'])
        self.ui_tab.delete(0, tk.END); self.ui_tab.insert(0, task['tab'])
        self.dynamic_fields = task['fields'].copy(); self.refresh_fields_list(); self.status_var.set(f"Editing: {task['name']}")
    def save_task(self):
        task = {"name": self.ui_name.get(), "url": self.ui_url.get(), "s_link": self.ui_link_sel.get(), "stats_sel": self.ui_stats_sel.get(), "page_key": self.ui_page_key.get(), "sheet_id": self.ui_sid.get(), "tab": self.ui_tab.get(), "fields": self.dynamic_fields}
        if self.selected_task_index is not None: self.tasks[self.selected_task_index] = task
        else: self.tasks.append(task)
        self.save_tasks_to_disk(); messagebox.showinfo("Success", "Task saved")
    def remove_task(self):
        if self.selected_task_index is not None and messagebox.askyesno("Confirm", "Delete?"):
            del self.tasks[self.selected_task_index]; self.save_tasks_to_disk(); self.clear_task_form()
    def load_tasks_from_disk(self):
        p = self.ui_conf_path.get()
        if os.path.exists(p):
            try:
                with open(p, 'r') as f: self.tasks = json.load(f)
                self.refresh_task_list_ui(); self.sync_to_json_text()
            except: pass
    def save_tasks_to_disk(self):
        with open(self.ui_conf_path.get(), 'w') as f: json.dump(self.tasks, f, indent=2)
        self.refresh_task_list_ui(); self.sync_to_json_text()
    def refresh_task_list_ui(self):
        self.ui_task_list.delete(0, tk.END)
        for t in self.tasks: self.ui_task_list.insert(tk.END, t['name'])
    def sync_to_json_text(self):
        self.json_editor.delete("1.0", tk.END); self.json_editor.insert("1.0", json.dumps(self.tasks, indent=2))
    def sync_from_json_text(self):
        try: self.tasks = json.loads(self.json_editor.get("1.0", tk.END)); self.save_tasks_to_disk()
        except Exception as e: messagebox.showerror("Error", str(e))
    def log(self, msg, status="info"):
        self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))
    def stop(self): self.stop_flag = True

    def run(self, mode="all"):
        if self.running: return
        tasks = [self.tasks[self.selected_task_index]] if mode == "selected" else self.tasks
        if not tasks: return
        self.running = True; self.stop_flag = False; self.notebook.select(self.tab_console)
        threading.Thread(target=self.engine_start, args=(tasks,), daemon=True).start()

    # ================= CORE ENGINE (UPDATED FOR DODA) =================
    def engine_start(self, task_list):
        auth = self.ui_auth_path.get()
        try:
            gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(auth, ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']))
            for task in task_list:
                if self.stop_flag: break
                self.process_task(task, gc)
            self.log("🏁 SESSION COMPLETE", "success")
        except Exception as e: self.log(f"❌ Error: {e}", "error")
        finally: self.running = False; self.status_var.set("Ready")

    def process_task(self, task, gc):
        self.log(f"🚀 Starting: {task['name']}")
        session = crequests.Session(impersonate="chrome110") 
        session.headers.update({"Referer": "https://google.com"})
        
        try:
            sh = gc.open_by_key(task['sheet_id'])
            ws = sh.worksheet(task['tab'])
        except: self.log("❌ Sheet Error", "error"); return

        try:
            session.get("https://doda.jp/", timeout=20)
            res = session.get(task['url'], timeout=30)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e: self.log(f"❌ Blocked: {e}", "error"); return

        # FIXED MATH FOR COMMAS IN LARGE NUMBERS (2,371)
        total_items = 0
        stats_el = soup.select_one(task['stats_sel'])
        if stats_el:
            total_items = int(re.sub(r'\D', '', stats_el.get_text()))
        
        total_pages = math.ceil(total_items / 50) if total_items > 0 else 1
        self.log(f"📊 Items: {total_items} | Pages: {total_pages}")

        for p in range(1, total_pages + 1):
            if self.stop_flag: break
            u = urlparse(task['url']); q = parse_qs(u.query); q[task['page_key']] = [str(p)]
            cur_url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))
            self.log(f"📄 --- PAGE {p} OF {total_pages} ---")
            
            if p > 1:
                try: soup = BeautifulSoup(session.get(cur_url, timeout=30).text, "html.parser")
                except: continue

            links = [urljoin(cur_url, a.get("href")) for a in soup.select(task['s_link']) if a.get("href")]
            links = list(dict.fromkeys(links))
            if not links: break

            results = []
            with ThreadPoolExecutor(max_workers=2) as ex:
                futures = {ex.submit(self.fetch_detail, session, l, task['fields']): l for l in links}
                count = 0
                for f in as_completed(futures):
                    if self.stop_flag: break
                    r = f.result(); count += 1
                    if r:
                        results.append(r)
                        self.log(f"   ✅ [{count}/{len(links)}] Scraped: {str(r.get('会社名', 'N/A'))[:15]}...")
                    else:
                        self.log(f"   ❌ [{count}/{len(links)}] Failed Link")

            if results:
                headers = ["URL"] + list(task['fields'].keys())
                ws.append_rows([[r.get(h, "") for h in headers] for r in results])
                self.log(f"💾 Page {p} saved.")
            
            time.sleep(random.uniform(5, 8))

    def fetch_detail(self, session, url, fields):
        time.sleep(random.uniform(2, 4))
        try:
            # 1. Force the URL to the "Job Details" tab directly to save one request
            # We transform /j_jid__3014640205/ into /j_jid__3014640205/-tab__jd/
            if "-tab__jd" not in url:
                url = url.rstrip('/') + '/-tab__jd/'
            
            # 2. Fetch the page
            r = session.get(url, timeout=25)
            if r.status_code != 200:
                # Fallback: if the direct tab link fails, try the original URL
                r = session.get(url.replace('/-tab__jd/', '/'), timeout=25)
            
            if r.status_code != 200: return None
            
            s = BeautifulSoup(r.text, "html.parser")
            data = {"URL": url}
            
            # 3. Extract Data
            for k, v in fields.items():
                # Handle Fallback Selectors
                found = False
                for sel in v.split(','):
                    el = s.select_one(sel.strip())
                    if el:
                        # get_text(separator=" ") ensures we get text from inside sub-tags
                        data[k] = el.get_text(separator=" ", strip=True)
                        found = True
                        break
                if not found:
                    data[k] = "N/A"
            
            return data
        except Exception as e:
            self.log(f"   ❌ Error: {str(e)[:50]}")
            return None

if __name__ == "__main__":
    App().mainloop()
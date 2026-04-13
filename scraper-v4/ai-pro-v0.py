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

# ================= MODERN UI CONFIG =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.config = {
            "auth_file": "service-account.json",
            "tasks_file": "scraper_config.json",
            "theme": {
                "bg": "#F1F5F9",           # Soft Light Gray
                "sidebar": "#1E293B",      # Deep Navy
                "panel": "#FFFFFF",        # Pure White
                "accent": "#2563EB",       # Royal Blue
                "text_main": "#0F172A",    # Near Black
                "success": "#16A34A",      # Emerald Green
                "error": "#DC2626",        # Vivid Red
                "warning": "#EA580C",      # Burnt Orange
            }
        }

        self.tasks = []
        self.dynamic_fields = []
        self.selected_task_index = None
        self.selected_field_index = None 
        self.running = False
        self.stop_flag = False
        
        # Stats
        self.stat_rows = tk.IntVar(value=0)
        self.stat_pages = tk.StringVar(value="0 / 0")
        self.stat_task = tk.StringVar(value="IDLE")
        self.stat_total = tk.StringVar(value="0")

        self.title("UNIVERSAL SCRAPER PRO v5.2")
        self.geometry("1350x900")
        self.apply_styles()
        self.setup_ui()
        
        # Initial Load
        if os.path.exists(self.config["auth_file"]):
            self.ui_auth_path.insert(0, self.config["auth_file"])
        self.load_tasks_from_disk()

    def apply_styles(self):
        t = self.config["theme"]
        self.configure(bg=t["bg"])
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("TFrame", background=t["bg"])
        style.configure("TNotebook", background=t["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=[20, 10], font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=t["bg"], foreground=t["text_main"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=t["sidebar"])

    def btn(self, parent, text, color_key, command, width=None):
        """Creates high-visibility buttons with White text"""
        bg = self.config["theme"][color_key]
        return tk.Button(
            parent, text=text, bg=bg, fg="white", 
            activebackground=bg, activeforeground="white",
            relief="flat", font=("Segoe UI", 10, "bold"), 
            command=command, cursor="hand2", padx=15, pady=8, width=width
        )

    def setup_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_editor = ttk.Frame(self.notebook)
        self.tab_json = ttk.Frame(self.notebook)
        self.tab_console = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_editor, text=" ⚙️ CONFIGURATOR ")
        self.notebook.add(self.tab_json, text=" 📝 JSON STUDIO ")
        self.notebook.add(self.tab_console, text=" 📊 DASHBOARD ")

        self.setup_editor_tab()
        self.setup_json_tab()
        self.setup_console_tab()

    def setup_editor_tab(self):
        t = self.config["theme"]
        main = ttk.Frame(self.tab_editor, padding=15)
        main.pack(fill="both", expand=True)
        pane = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        pane.pack(fill="both", expand=True)

        # LEFT SIDE: Task List
        left = ttk.Frame(pane)
        pane.add(left, weight=1)
        ttk.Label(left, text="TASK REPOSITORY", style="Header.TLabel").pack(pady=(0, 10), anchor="w")
        
        self.ui_task_list = tk.Listbox(left, font=("Segoe UI", 10), bd=1, relief="solid", highlightthickness=0)
        self.ui_task_list.pack(fill="both", expand=True, padx=(0, 10))
        self.ui_task_list.bind("<<ListboxSelect>>", self.on_task_click)

        btn_f = tk.Frame(left, bg=t["bg"])
        btn_f.pack(fill="x", pady=10, padx=(0, 10))
        self.btn(btn_f, "✚ NEW", "accent", self.clear_task_form).pack(side="left", expand=True, fill="x", padx=2)
        self.btn(btn_f, "🗑 DELETE", "error", self.remove_task).pack(side="left", expand=True, fill="x", padx=2)

        # RIGHT SIDE: Form
        right_container = ttk.Frame(pane)
        pane.add(right_container, weight=3)
        
        canvas = tk.Canvas(right_container, bg=t["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=t["bg"])
        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Configuration Sections
        sec_glob = self.create_card(self.scroll_frame, "GOOGLE AUTHENTICATION")
        self.ui_auth_path = self.entry_row(sec_glob, "JSON Key Path")
        self.btn(sec_glob, "📁 BROWSE...", "sidebar", self.browse_auth).pack(pady=5, padx=15, anchor="e")

        sec_task = self.create_card(self.scroll_frame, "TARGET SETTINGS")
        self.ui_name = self.entry_row(sec_task, "Task Name")
        self.ui_url = self.entry_row(sec_task, "Primary URL")
        self.ui_sid = self.entry_row(sec_task, "G-Sheet ID")
        self.ui_tab = self.entry_row(sec_task, "Tab Name")
        self.ui_cookie = self.entry_row(sec_task, "Cookie")
        self.ui_max_pages = self.entry_row(sec_task, "Page Limit")
        
        sec_engine = self.create_card(self.scroll_frame, "SELECTORS")
        self.ui_link_sel = self.entry_row(sec_engine, "Detail Link CSS")
        self.ui_stats_sel = self.entry_row(sec_engine, "Total Count CSS")
        self.ui_page_key = self.entry_row(sec_engine, "Page Param")

        sec_fields = self.create_card(self.scroll_frame, "DATA FIELDS")
        f_in = tk.Frame(sec_fields, bg="white"); f_in.pack(fill="x", padx=10, pady=5)
        
        tk.Label(f_in, text="Col Name:", bg="white").grid(row=0, column=0, sticky="w")
        self.ui_f_name = tk.Entry(f_in, font=("Segoe UI", 10), bg="#F8FAFC")
        self.ui_f_name.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(f_in, text="CSS Selector:", bg="white").grid(row=1, column=0, sticky="w")
        self.ui_f_sel = tk.Entry(f_in, font=("Segoe UI", 10), bg="#F8FAFC")
        self.ui_f_sel.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        f_in.columnconfigure(1, weight=1)

        f_bt = tk.Frame(sec_fields, bg="white"); f_bt.pack(fill="x", padx=10, pady=5)
        self.btn_field_add = self.btn(f_bt, "✅ SAVE FIELD", "success", self.add_field)
        self.btn_field_add.pack(side="left", expand=True, fill="x", padx=2)
        self.btn(f_bt, "🗑 REMOVE", "error", self.remove_field).pack(side="left", expand=True, fill="x", padx=2)
        
        self.ui_fields_box = tk.Listbox(sec_fields, height=5, font=("Consolas", 10))
        self.ui_fields_box.pack(fill="x", padx=15, pady=10)
        self.ui_fields_box.bind("<<ListboxSelect>>", self.on_field_click)

        self.btn(self.scroll_frame, "💾 SAVE ENTIRE TASK CONFIG", "accent", self.save_task).pack(fill="x", pady=20, padx=10)

    def setup_json_tab(self):
        main = ttk.Frame(self.tab_json, padding=20)
        main.pack(fill="both", expand=True)
        self.json_editor = scrolledtext.ScrolledText(main, font=("Consolas", 11), bg="#1E293B", fg="#38BDF8", insertbackground="white")
        self.json_editor.pack(fill="both", expand=True, pady=(0, 10))
        
        btn_f = tk.Frame(main, bg=self.config["theme"]["bg"])
        btn_f.pack(fill="x")
        self.btn(btn_f, "🔄 REFRESH FROM UI", "sidebar", self.sync_to_json).pack(side="left", padx=5)
        self.btn(btn_f, "📥 APPLY TO UI", "warning", self.sync_from_json).pack(side="left", padx=5)

    def setup_console_tab(self):
        main = ttk.Frame(self.tab_console, padding=20)
        main.pack(fill="both", expand=True)
        
        stats = tk.Frame(main, bg=self.config["theme"]["bg"]); stats.pack(fill="x", pady=(0, 20))
        for t, v in [("TASK", self.stat_task), ("PAGE", self.stat_pages), ("ROWS", self.stat_rows), ("TOTAL", self.stat_total)]:
            f = tk.Frame(stats, bg="white", highlightbackground="#E2E8F0", highlightthickness=1)
            f.pack(side="left", fill="both", expand=True, padx=5)
            tk.Label(f, text=t, bg="white", font=("Segoe UI", 9, "bold"), fg="#64748B").pack(pady=(10,0))
            tk.Label(f, textvariable=v, bg="white", font=("Segoe UI", 16, "bold"), fg=self.config["theme"]["accent"]).pack(pady=(0,10))

        body = ttk.Frame(main); body.pack(fill="both", expand=True)
        ctrl = tk.Frame(body, width=200, bg=self.config["theme"]["bg"]); ctrl.pack(side="left", fill="y", padx=(0, 20))
        
        self.btn(ctrl, "▶ START ALL", "success", lambda: self.run("all")).pack(fill="x", pady=5)
        self.btn(ctrl, "🎯 START SELECTED", "accent", lambda: self.run("selected")).pack(fill="x", pady=5)
        self.btn(ctrl, "🛑 STOP ENGINE", "error", self.stop).pack(fill="x", pady=5)
        
        self.log_box = scrolledtext.ScrolledText(body, bg="#0F172A", fg="#F8FAFC", font=("Consolas", 10), borderwidth=0)
        self.log_box.pack(side="right", fill="both", expand=True)

    # --- UI HELPERS ---
    def create_card(self, parent, title):
        f = tk.Frame(parent, bg="white", highlightbackground="#E2E8F0", highlightthickness=1)
        f.pack(fill="x", padx=10, pady=10)
        tk.Label(f, text=title, bg="white", font=("Segoe UI", 10, "bold"), fg=self.config["theme"]["accent"]).pack(anchor="w", padx=15, pady=(10, 5))
        return f

    def entry_row(self, parent, label):
        f = tk.Frame(parent, bg="white", pady=5); f.pack(fill="x", padx=15)
        tk.Label(f, text=label, bg="white", width=20, anchor="w").pack(side="left")
        e = tk.Entry(f, font=("Segoe UI", 10), bg="#F8FAFC", relief="flat", highlightbackground="#CBD5E1", highlightthickness=1)
        e.pack(side="left", fill="x", expand=True, ipady=3); return e

    def browse_auth(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path: self.ui_auth_path.delete(0, tk.END); self.ui_auth_path.insert(0, path)

    # --- TASK & FIELD LOGIC ---
    def on_task_click(self, e):
        selection = self.ui_task_list.curselection()
        if not selection: return
        self.selected_task_index = selection[0]
        t = self.tasks[self.selected_task_index]
        self.set_entry(self.ui_name, t.get('name', ''))
        self.set_entry(self.ui_url, t.get('url', ''))
        self.set_entry(self.ui_sid, t.get('sheet_id', ''))
        self.set_entry(self.ui_tab, t.get('tab', ''))
        self.set_entry(self.ui_cookie, t.get('cookie', ''))
        self.set_entry(self.ui_max_pages, t.get('max_pages', '0'))
        self.set_entry(self.ui_link_sel, t.get('s_link', 'a'))
        self.set_entry(self.ui_stats_sel, t.get('stats_sel', '.pager-display'))
        self.set_entry(self.ui_page_key, t.get('page_key', 'p'))
        self.dynamic_fields = t.get('fields', []).copy()
        self.refresh_fields_list()

    def set_entry(self, widget, val):
        widget.delete(0, tk.END); widget.insert(0, str(val))

    def clear_task_form(self):
        self.selected_task_index = None
        for w in [self.ui_name, self.ui_url, self.ui_sid, self.ui_tab, self.ui_cookie, self.ui_max_pages]: w.delete(0, tk.END)
        self.dynamic_fields = []; self.refresh_fields_list()

    def save_task(self):
        task = {
            "name": self.ui_name.get(), "url": self.ui_url.get(), "sheet_id": self.ui_sid.get(),
            "tab": self.ui_tab.get(), "fields": self.dynamic_fields, "cookie": self.ui_cookie.get(),
            "max_pages": self.ui_max_pages.get(), "s_link": self.ui_link_sel.get(),
            "stats_sel": self.ui_stats_sel.get(), "page_key": self.ui_page_key.get()
        }
        if self.selected_task_index is not None: self.tasks[self.selected_task_index] = task
        else: self.tasks.append(task)
        self.save_tasks_to_disk(); messagebox.showinfo("Saved", "Task library updated.")

    def remove_task(self):
        if self.selected_task_index is not None:
            if messagebox.askyesno("Confirm", "Delete this task?"):
                del self.tasks[self.selected_task_index]
                self.save_tasks_to_disk()
                self.clear_task_form()

    def add_field(self):
        n, s = self.ui_f_name.get().strip(), self.ui_f_sel.get().strip()
        if not n or not s: return
        if self.selected_field_index is not None: self.dynamic_fields[self.selected_field_index] = {"name": n, "selector": s}
        else: self.dynamic_fields.append({"name": n, "selector": s})
        self.ui_f_name.delete(0, tk.END); self.ui_f_sel.delete(0, tk.END)
        self.selected_field_index = None; self.btn_field_add.config(text="✅ SAVE FIELD"); self.refresh_fields_list()

    def remove_field(self):
        if self.selected_field_index is not None:
            del self.dynamic_fields[self.selected_field_index]
            self.selected_field_index = None; self.refresh_fields_list()

    def on_field_click(self, e):
        sel = self.ui_fields_box.curselection()
        if not sel: return
        self.selected_field_index = sel[0]
        f = self.dynamic_fields[self.selected_field_index]
        self.set_entry(self.ui_f_name, f['name']); self.set_entry(self.ui_f_sel, f['selector'])
        self.btn_field_add.config(text="🔄 UPDATE FIELD")

    def refresh_fields_list(self):
        self.ui_fields_box.delete(0, tk.END)
        for f in self.dynamic_fields: self.ui_fields_box.insert(tk.END, f" {f['name']}  ->  {f['selector']}")

    # --- PERSISTENCE ---
    def load_tasks_from_disk(self):
        if os.path.exists(self.config["tasks_file"]):
            with open(self.config["tasks_file"], 'r', encoding='utf-8') as f: self.tasks = json.load(f)
            self.refresh_task_list_ui(); self.sync_to_json()

    def save_tasks_to_disk(self):
        with open(self.config["tasks_file"], 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        self.refresh_task_list_ui(); self.sync_to_json()

    def refresh_task_list_ui(self):
        self.ui_task_list.delete(0, tk.END)
        for t in self.tasks: self.ui_task_list.insert(tk.END, f" {t['name']}")

    def sync_to_json(self):
        self.json_editor.delete("1.0", tk.END)
        self.json_editor.insert("1.0", json.dumps(self.tasks, indent=2, ensure_ascii=False))

    def sync_from_json(self):
        try:
            self.tasks = json.loads(self.json_editor.get("1.0", tk.END))
            self.save_tasks_to_disk(); messagebox.showinfo("Success", "Config updated.")
        except Exception as e: messagebox.showerror("Error", str(e))

    # --- SCRAPING ENGINE ---
    def log(self, msg):
        self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def stop(self): self.stop_flag = True

    def run(self, mode="all"):
        if self.running: return
        auth_path = self.ui_auth_path.get().strip()
        if not auth_path or not os.path.exists(auth_path):
            messagebox.showerror("Error", "Valid Service Account JSON required.")
            return
        t_list = [self.tasks[self.selected_task_index]] if mode == "selected" and self.selected_task_index is not None else self.tasks
        if not t_list: return
        self.running = True; self.stop_flag = False; self.stat_rows.set(0)
        self.notebook.select(self.tab_console)
        threading.Thread(target=self.engine_start, args=(t_list, auth_path), daemon=True).start()

    def engine_start(self, task_list, auth_path):
        try:
            gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(auth_path, ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']))
            for task in task_list:
                if self.stop_flag: break
                self.process_task(task, gc)
        except Exception as e: self.log(f"CRITICAL: {e}")
        finally: self.running = False; self.stat_task.set("IDLE")

    def process_task(self, task, gc):
        self.stat_task.set(task['name'].upper())
        sess = requests.Session()
        sess.headers = {"User-Agent": "Mozilla/5.0"}
        if task.get('cookie'): sess.headers["Cookie"] = task['cookie']

        try:
            sh = gc.open_by_key(task['sheet_id'])
            try: ws = sh.worksheet(task['tab'])
            except: ws = sh.add_worksheet(title=task['tab'], rows="5000", cols="20")
        except Exception as e: self.log(f"SHEET ERROR: {e}"); return

        try:
            r = sess.get(task['url'], timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            total_pages = 1
            stats = soup.select_one(task.get('stats_sel', '.pager-display'))
            if stats:
                nums = [int(n) for n in re.findall(r'\d+', stats.get_text().replace(',', ''))]
                if len(nums) >= 3:
                    ipp = (nums[1] - nums[0]) + 1
                    total_pages = math.ceil(nums[2] / ipp)
                    self.stat_total.set(str(nums[2]))
            mx = int(task.get('max_pages', 0))
            if mx > 0: total_pages = min(total_pages, mx)
        except: total_pages = 1

        for p in range(1, total_pages + 1):
            if self.stop_flag: break
            self.stat_pages.set(f"{p} / {total_pages}")
            u = urlparse(task['url'])
            q = parse_qs(u.query); q[task.get('page_key', 'p')] = [str(p)]
            cur_url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))
            
            p_res = sess.get(cur_url)
            p_soup = BeautifulSoup(p_res.text, "html.parser")
            
            # Grab all unique links matched by the Detail Link CSS selector
            links = [urljoin(cur_url, a.get("href")) for a in p_soup.select(task.get('s_link', 'a')) if a.get("href")]
            links = list(set(links)) 

            results = []
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(self.fetch_detail, sess, l, task['fields']) for l in links]
                for f in as_completed(futures):
                    res = f.result()
                    if res: results.append(res)

            if results:
                headers = ["URL"] + [f['name'] for f in task['fields']]
                rows = [[r.get(h, "") for h in headers] for r in results]
                ws.append_rows(rows)
                self.stat_rows.set(self.stat_rows.get() + len(results))
                self.log(f"✅ Saved {len(results)} rows from page {p}")

    def fetch_detail(self, sess, url, fields):
        try:
            time.sleep(random.uniform(0.5, 1.0))
            r = sess.get(url, timeout=10)
            s = BeautifulSoup(r.text, "html.parser")
            data = {"URL": url}
            for f in fields:
                target = s.select_one(f['selector'])
                data[f['name']] = target.get_text(strip=True) if target else "N/A"
            return data
        except: return None

if __name__ == "__main__":
    App().mainloop()
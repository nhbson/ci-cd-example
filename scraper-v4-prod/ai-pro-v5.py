import os, json, random, time, threading, re, math
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse, urljoin
import gspread
from curl_cffi import requests as crequests 
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = {
            "auth_file": "service-account.json",
            "tasks_file": "scraper_config.json",
            "theme": {"bg": "#f5f6fa", "fg": "#2d3436", "accent": "#0984e3", "log_bg": "#1e272e", "log_fg": "#d2dae2"}
        }
        self.tasks = []; self.dynamic_fields = {}; self.selected_task_index = None; self.running = False; self.stop_flag = False
        self.title("DODA REAL-TIME SCRAPER")
        self.geometry("1100x850")
        self.apply_styles(); self.setup_ui(); self.load_tasks_from_disk()

    def apply_styles(self):
        self.configure(bg=self.config["theme"]["bg"])
        s = ttk.Style(); s.theme_use('clam')
        s.configure("TFrame", background=self.config["theme"]["bg"])
        s.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=self.config["theme"]["accent"])

    def setup_ui(self):
        self.notebook = ttk.Notebook(self); self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_editor = ttk.Frame(self.notebook); self.notebook.add(self.tab_editor, text=" ⚙️ Task Manager ")
        self.tab_console = ttk.Frame(self.notebook); self.notebook.add(self.tab_console, text=" 🖥️ Console ")
        
        # Simple Editor
        main = ttk.Frame(self.tab_editor); main.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(main, width=250); left.pack(side="left", fill="y")
        self.ui_task_list = tk.Listbox(left); self.ui_task_list.pack(fill="both", expand=True); self.ui_task_list.bind("<<ListboxSelect>>", self.on_task_click)
        ttk.Button(left, text="💾 Save", command=self.save_task).pack(fill="x")
        
        right = ttk.Frame(main); right.pack(side="right", fill="both", expand=True, padx=10)
        self.ui_name = self.field(right, "Name"); self.ui_url = self.field(right, "URL")
        self.ui_sid = self.field(right, "Sheet ID"); self.ui_tab = self.field(right, "Tab Name")
        
        # Console
        top = ttk.Frame(self.tab_console); top.pack(fill="x", pady=5)
        ttk.Button(top, text="▶ START SCRAPING", command=self.run).pack(side="left", padx=10)
        ttk.Button(top, text="🛑 STOP", command=self.stop).pack(side="left")
        self.log_box = scrolledtext.ScrolledText(self.tab_console, bg="#1e272e", fg="#d2dae2", font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    def field(self, p, l):
        f = ttk.Frame(p); f.pack(fill="x", pady=2); ttk.Label(f, text=l, width=10).pack(side="left")
        e = tk.Entry(f); e.pack(side="left", fill="x", expand=True); return e

    def on_task_click(self, e):
        if not self.ui_task_list.curselection(): return
        idx = self.ui_task_list.curselection()[0]; task = self.tasks[idx]; self.selected_task_index = idx
        self.ui_name.delete(0, tk.END); self.ui_name.insert(0, task['name'])
        self.ui_url.delete(0, tk.END); self.ui_url.insert(0, task['url'])
        self.ui_sid.delete(0, tk.END); self.ui_sid.insert(0, task['sheet_id'])
        self.ui_tab.delete(0, tk.END); self.ui_tab.insert(0, task['tab'])

    def save_task(self):
        # Default selectors for Doda
        t = {
            "name": self.ui_name.get(), "url": self.ui_url.get(), "sheet_id": self.ui_sid.get(), "tab": self.ui_tab.get(),
            "s_link": "a[href*='/JobSearchDetail/j_jid__']", "stats_sel": ".displayJobCount__totalNum", "page_key": "page",
            "fields": {
                "会社名": "h2.SectionTitle-module_title__DvvU6",
                "タイトル": "p.Text-module_text--size14--articlePC__yHzvA",
                "給与": ".jobSearchDetail-salary__detail",
                "住所": "div.DescriptionList-module_descriptionList__columnItem__GtLF0:nth-of-type(2) dd",
                "従業員数": "div.DescriptionList-module_descriptionList__columnItem__GtLF0:nth-of-type(5) dd"
            }
        }
        if self.selected_task_index is not None: self.tasks[self.selected_task_index] = t
        else: self.tasks.append(t)
        with open("scraper_config.json", 'w') as f: json.dump(self.tasks, f, indent=2)
        self.load_tasks_from_disk()

    def load_tasks_from_disk(self):
        if os.path.exists("scraper_config.json"):
            with open("scraper_config.json", 'r') as f: self.tasks = json.load(f)
            self.ui_task_list.delete(0, tk.END)
            for t in self.tasks: self.ui_task_list.insert(tk.END, t['name'])

    def log(self, msg):
        self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def stop(self): self.stop_flag = True

    def run(self):
        if self.running or self.selected_task_index is None: return
        self.running = True; self.stop_flag = False
        threading.Thread(target=self.engine_start, args=(self.tasks[self.selected_task_index],), daemon=True).start()

    # ================= ENGINE =================
    def engine_start(self, task):
        try:
            self.log(f"🚀 Initializing Google Sheets...")
            gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name("service-account.json", ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']))
            sh = gc.open_by_key(task['sheet_id'])
            ws = sh.worksheet(task['tab'])
            
            session = crequests.Session(impersonate="chrome110")
            session.headers.update({"Referer": "https://google.com"})
            
            self.log(f"🔗 Accessing Doda...")
            session.get("https://doda.jp/", timeout=20) # Get Cookies
            res = session.get(task['url'], timeout=30)
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Pagination Math Fix
            total_items = 0
            stats_el = soup.select_one(task['stats_sel'])
            if stats_el:
                total_items = int(re.sub(r'\D', '', stats_el.get_text()))
            
            total_pages = math.ceil(total_items / 50) if total_items > 0 else 1
            self.log(f"📊 Total Jobs: {total_items} | Total Pages: {total_pages}")

            for p in range(1, total_pages + 1):
                if self.stop_flag: break
                
                u = urlparse(task['url']); q = parse_qs(u.query); q[task['page_key']] = [str(p)]
                cur_url = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))
                
                self.log(f"📄 --- PAGE {p} OF {total_pages} ---")
                if p > 1:
                    soup = BeautifulSoup(session.get(cur_url, timeout=30).text, "html.parser")

                links = [urljoin(cur_url, a.get("href")) for a in soup.select(task['s_link']) if a.get("href")]
                links = list(dict.fromkeys(links))
                
                if not links:
                    self.log("⚠️ No links found. Ending session."); break

                results = []
                # Use max_workers=3 for better speed without getting banned
                with ThreadPoolExecutor(max_workers=3) as ex:
                    futures = {ex.submit(self.fetch_detail, session, l, task['fields']): l for l in links}
                    count = 0
                    for f in as_completed(futures):
                        if self.stop_flag: break
                        r = f.result()
                        count += 1
                        if r:
                            results.append(r)
                            self.log(f"   ✅ [{count}/{len(links)}] Extracted: {r['会社名'][:20]}...")
                        else:
                            self.log(f"   ❌ [{count}/{len(links)}] Failed/Blocked: {futures[f][:40]}...")

                if results:
                    headers = ["URL"] + list(task['fields'].keys())
                    ws.append_rows([[r.get(h, "") for h in headers] for r in results])
                    self.log(f"💾 Page {p} saved to Google Sheets.")
                
                time.sleep(random.uniform(5, 8)) # Page transition delay

            self.log("🏁 FINISHED")
        except Exception as e: self.log(f"❌ Critical Error: {e}")
        finally: self.running = False

    def fetch_detail(self, session, url, fields):
        # Adding a smaller random jitter for detail pages
        time.sleep(random.uniform(2, 5))
        try:
            r = session.get(url, timeout=20)
            if r.status_code != 200: return None
            s = BeautifulSoup(r.text, "html.parser")
            data = {"URL": url}
            for k, v in fields.items():
                el = s.select_one(v)
                data[k] = el.get_text(strip=True) if el else "N/A"
            return data
        except: return None

if __name__ == "__main__": App().mainloop()
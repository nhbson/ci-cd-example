import os
import json
import random
import time
import threading
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse, urljoin

import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

SERVICE_ACCOUNT_FILE = "service-account.json"
CONFIG_FILE = "scraper_config.json"

AI_DEBUG = True  # 🔥 ENABLE AI MODE

COLORS = {
    "bg": "#f5f6fa",
    "panel": "#ffffff",
    "fg": "#2d3436",
    "accent": "#0984e3",
    "success": "#00b894",
    "error": "#d63031",
    "warning": "#f1c40f"
}

# ================= SCRAPER =================
class DynamicScraper: 
    def __init__(self, log, check_status, cookie):
        self.log = log
        self.check_status = check_status
        self.session = requests.Session()
        self.seen = set()

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ja,en-US;q=0.9"
        }

        if not cookie:
            return ""
        # remove newline, tabs, carriage return
        cleaned_cookie = cookie.replace("\n", "").replace("\r", "").replace("\t", "")
        # remove extra spaces
        cleaned_cookie = re.sub(r"\s+", " ", cookie)

        if cleaned_cookie:
            headers["Cookie"] = cleaned_cookie
            
        self.session.headers.update(headers)

    def safe_get(self, url):
        if not self.check_status(): return None
        try:
            time.sleep(random.uniform(2, 4))
            r = self.session.get(url, timeout=15)
            return r if r.status_code == 200 else None
        except Exception as e:
            self.log(f"Request error: {e}", "ERROR")
            return None

    # 🤖 AI FALLBACK
    def ai_find_element(self, soup, field_name):
        keywords_map = {
            "企業名": ["会社", "company", "corp"],
            "住所": ["住所", "所在地", "address"],
            "電話番号": ["電話", "tel", "phone"],
            "ジャンル": ["ジャンル", "category"],
        }

        keywords = keywords_map.get(field_name, [field_name.lower()])

        for tag in soup.select("tr, li, div"):
            text = tag.get_text(" ", strip=True)
            for k in keywords:
                if k.lower() in text.lower():
                    return text[:100]

        for tag in ["h1", "title"]:
            el = soup.select_one(tag)
            if el:
                return el.get_text(strip=True)

        return None

    def ai_analyze(self, soup):
        titles = [t.get_text(strip=True) for t in soup.select("h1, h2")[:3]]
        self.log(f"🧠 AI Titles: {titles}", "DEBUG")

    def fetch_detail(self, url, fields):
        if url in self.seen: return None
        res = self.safe_get(url)
        if not res: return None

        soup = BeautifulSoup(res.text, "html.parser")
        data = {"URL": url}

        if AI_DEBUG:
            self.ai_analyze(soup)

        for f in fields:
            try:
                el = soup.select_one(f["selector"])
                if el:
                    val = el.get_text(strip=True)
                    data[f["name"]] = val
                    self.log(f"{f['name']} = {val[:40]}", "SUCCESS")
                else:
                    self.log(f"{f['name']} FAILED ({f['selector']})", "WARNING")

                    if AI_DEBUG:
                        ai_val = self.ai_find_element(soup, f["name"])
                        if ai_val:
                            data[f["name"]] = ai_val
                            self.log(f"🤖 AI FIXED {f['name']} → {ai_val[:40]}", "SUCCESS")
                        else:
                            data[f["name"]] = "N/A"
                            self.log(f"❌ AI FAILED {f['name']}", "ERROR")
                    else:
                        data[f["name"]] = "N/A"

            except Exception as e:
                data[f["name"]] = "ERROR"
                self.log(f"{f['name']} ERROR: {e}", "ERROR")

        self.seen.add(url)
        return data

    def process(self, task, gc):
        self.log(f"🚀 Start {task['name']}", "INFO")

        res = self.safe_get(task["url"])
        if not res: return

        soup = BeautifulSoup(res.text, "html.parser")

        max_pages = int(task.get("max_pages", 10))

        for p in range(1, max_pages + 1):
            if not self.check_status(): break

            self.log(f"📄 Page {p}", "INFO")

            u = urlparse(task["url"])
            q = parse_qs(u.query)
            q[task.get("page_param", "p")] = [str(p)]
            page_url = urlunparse(u._replace(query=urlencode(q, doseq=True)))

            if p > 1:
                res = self.safe_get(page_url)
                if not res: break
                soup = BeautifulSoup(res.text, "html.parser")

            links = []
            for a in soup.select(task.get("s_link", "a")):
                href = a.get("href")
                if not href: continue
                full = urljoin(task["url"], href)

                if any(x in full for x in ["/job/", "/view/", "/restaurant/", "/shop/"]):
                    links.append(full.split("?")[0])

            links = list(set(links))
            self.log(f"🔗 Found {len(links)} links", "INFO")

            results = []
            with ThreadPoolExecutor(max_workers=3) as ex:
                futures = [ex.submit(self.fetch_detail, l, task["fields"]) for l in links]
                for f in as_completed(futures):
                    if not self.check_status(): break
                    r = f.result()
                    if r: results.append(r)

            if results:
                try:
                    sh = gc.open_by_key(task["sheet_id"])
                    ws = sh.worksheet(task["tab"])
                    headers = ["URL"] + [f["name"] for f in task["fields"]]
                    rows = [[r.get(h, "N/A") for h in headers] for r in results]
                    ws.append_rows(rows)
                    self.log(f"💾 Saved {len(results)}", "SUCCESS")
                except Exception as e:
                    self.log(f"Sheet error: {e}", "ERROR")

        self.log("🏁 DONE", "SUCCESS")

# ================= UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SCRAPER AI PRO")
        self.geometry("1200x900")
        self.configure(bg=COLORS["bg"])

        self.tasks = self.load_tasks()
        self.fields = []
        self.selected_index = None

        self.running = False
        self.paused = False
        self.stop_flag = False
        self.cond = threading.Condition()

        self.setup_ui()
        self.refresh_list()

    def log(self, msg, level="INFO"):
        now = time.strftime("%H:%M:%S")
        line = f"[{now}] [{level}] {msg}"
        self.after(0, lambda: (self.log_box.insert(tk.END, line+"\n"), self.log_box.see(tk.END)))

    def run(self):
        if self.running: return
        self.running = True
        self.stop_flag = False
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                SERVICE_ACCOUNT_FILE,
                ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
            )
            gc = gspread.authorize(creds)

            scraper = DynamicScraper(self.log, self.check_status, self.e_cookie.get("1.0", tk.END))

            for t in self.tasks:
                if self.stop_flag: break
                scraper.process(t, gc)

        except Exception as e:
            self.log(str(e), "ERROR")

        self.running = False

    def check_status(self):
        with self.cond:
            while self.paused and not self.stop_flag:
                self.cond.wait()
            return not self.stop_flag

    def pause(self):
        self.paused = True
        self.log("⏸ paused", "WARNING")

    def resume(self):
        self.paused = False
        with self.cond:
            self.cond.notify_all()
        self.log("▶ resumed", "SUCCESS")

    def stop(self):
        self.stop_flag = True
        with self.cond:
            self.cond.notify_all()
        self.log("🛑 stop", "ERROR")

    # ===== TASK CRUD =====
    def save_task(self):
        task = {
            "name": self.e_name.get(),
            "url": self.e_url.get(),
            "s_link": self.e_link.get(),
            "cookie": self.e_cookie.get("1.0", tk.END).strip(),
            "page_param": "p",
            "max_pages": self.e_pages.get(),
            "fields": self.fields,
            "sheet_id": self.e_sid.get(),
            "tab": self.e_tab.get()
        }

        if self.selected_index is not None:
            self.tasks[self.selected_index] = task
        else:
            self.tasks.append(task)

        self.save_tasks()
        self.refresh_list()
        self.log("💾 Task saved", "SUCCESS")

    def load_tasks(self):
        if not os.path.exists(CONFIG_FILE):
            return []
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_tasks(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=2, ensure_ascii=False)

    def refresh_list(self):
        self.lb.delete(0, tk.END)
        for t in self.tasks:
            self.lb.insert(tk.END, t["name"])

    # ===== UI BUILD (UNCHANGED LAYOUT) =====
    def setup_ui(self):
        main = tk.Frame(self); main.pack(fill="both", expand=True)

        left = tk.Frame(main); left.pack(side="left", fill="y")
        self.lb = tk.Listbox(left); self.lb.pack(fill="x")
        self.lb.bind("<<ListboxSelect>>", self.load_task)

        self.e_name = tk.Entry(left); self.e_name.pack(fill="x")
        self.e_url = tk.Entry(left); self.e_url.pack(fill="x")
        self.e_link = tk.Entry(left); self.e_link.pack(fill="x")

        self.e_cookie = tk.Text(left, height=3); self.e_cookie.pack(fill="x")
        self.e_pages = tk.Entry(left); self.e_pages.pack(fill="x")
        self.e_sid = tk.Entry(left); self.e_sid.pack(fill="x")
        self.e_tab = tk.Entry(left); self.e_tab.pack(fill="x")

        self.f_name = tk.Entry(left); self.f_name.pack(fill="x")
        self.f_sel = tk.Entry(left); self.f_sel.pack(fill="x")

        tk.Button(left, text="Add", command=self.add_field).pack(fill="x")
        tk.Button(left, text="Update", command=self.update_field).pack(fill="x")
        tk.Button(left, text="Remove", command=self.remove_field).pack(fill="x")

        self.field_lb = tk.Listbox(left); self.field_lb.pack(fill="x")
        self.field_lb.bind("<<ListboxSelect>>", self.load_field)

        tk.Button(left, text="SAVE", command=self.save_task).pack(fill="x")

        right = tk.Frame(main); right.pack(side="right", fill="both", expand=True)

        tk.Button(right, text="START", command=self.run).pack()
        tk.Button(right, text="PAUSE", command=self.pause).pack()
        tk.Button(right, text="RESUME", command=self.resume).pack()
        tk.Button(right, text="STOP", command=self.stop).pack()

        self.log_box = scrolledtext.ScrolledText(right)
        self.log_box.pack(fill="both", expand=True)

    # ===== FIELD CRUD =====
    def add_field(self):
        self.fields.append({"name": self.f_name.get(), "selector": self.f_sel.get()})
        self.refresh_fields()

    def update_field(self):
        if not self.field_lb.curselection(): return
        i = self.field_lb.curselection()[0]
        self.fields[i] = {"name": self.f_name.get(), "selector": self.f_sel.get()}
        self.refresh_fields()

    def remove_field(self):
        if not self.field_lb.curselection(): return
        i = self.field_lb.curselection()[0]
        self.fields.pop(i)
        self.refresh_fields()

    def load_field(self, e):
        if not self.field_lb.curselection(): return
        i = self.field_lb.curselection()[0]
        f = self.fields[i]
        self.f_name.delete(0, tk.END); self.f_name.insert(0, f["name"])
        self.f_sel.delete(0, tk.END); self.f_sel.insert(0, f["selector"])

    def refresh_fields(self):
        self.field_lb.delete(0, tk.END)
        for f in self.fields:
            self.field_lb.insert(tk.END, f"{f['name']} : {f['selector']}")

    def load_task(self, e):
        if not self.lb.curselection(): return
        i = self.lb.curselection()[0]
        self.selected_index = i
        t = self.tasks[i]

        self.e_name.delete(0, tk.END); self.e_name.insert(0, t["name"])
        self.e_url.delete(0, tk.END); self.e_url.insert(0, t["url"])
        self.e_link.delete(0, tk.END); self.e_link.insert(0, t.get("s_link",""))
        self.e_sid.delete(0, tk.END); self.e_sid.insert(0, t.get("sheet_id",""))
        self.e_tab.delete(0, tk.END); self.e_tab.insert(0, t.get("tab",""))
        self.e_pages.delete(0, tk.END); self.e_pages.insert(0, t.get("max_pages","10"))

        self.fields = t.get("fields", [])
        self.refresh_fields()

if __name__ == "__main__":
    App().mainloop()
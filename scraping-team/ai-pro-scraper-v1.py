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

SERVICE_ACCOUNT_FILE = "service-account.json"
CACHE_FILE = "cache.json"


# ================= DEVTOOLS =================
class DevToolsWindow(tk.Toplevel):
    def __init__(self, master, log_func):
        super().__init__(master)
        self.title("🧠 DevTools PRO (Level 4)")
        self.geometry("1400x900")

        self.log = log_func
        self.driver = None
        self.running = False

        self.setup_ui()

    def setup_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x")

        self.url_entry = ttk.Entry(top)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=5)

        ttk.Button(top, text="🚀 Open", command=self.open_browser).pack(side="left")
        ttk.Button(top, text="🧠 Inspect", command=self.enable_inspect_mode).pack(side="left")
        ttk.Button(top, text="📡 Network", command=self.enable_network).pack(side="left")
        ttk.Button(top, text="🔗 Get Links", command=self.extract_links).pack(side="left")

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill="both", expand=True)

        # LEFT PANEL
        left = ttk.Frame(main)
        main.add(left, weight=1)

        ttk.Label(left, text="Element Info").pack(anchor="w")

        self.info_box = scrolledtext.ScrolledText(left)
        self.info_box.pack(fill="both", expand=True)

        # RIGHT PANEL
        right = ttk.Frame(main)
        main.add(right, weight=1)

        ttk.Label(right, text="Selector / Results").pack(anchor="w")

        self.selector_box = tk.Text(right, height=3)
        self.selector_box.pack(fill="x")

        ttk.Button(right, text="Test Selector", command=self.test_selector).pack()

        self.result_box = scrolledtext.ScrolledText(right)
        self.result_box.pack(fill="both", expand=True)

    # ================= BROWSER =================
    def open_browser(self):
        url = self.url_entry.get()

        if self.driver:
            self.driver.quit()

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")

        self.driver = uc.Chrome(options=options, version_main=146)
        self.driver.get(url)

        # Enable mouse tracking JS
        self.driver.execute_script("""
            document.addEventListener('mousemove', function(e){
                window._mx = e.clientX;
                window._my = e.clientY;
            });
        """)

        self.log(f"[OPEN] {url}")

    # ================= INSPECT =================
    def enable_inspect_mode(self):
        self.running = True
        self.log("[INSPECT] ON")

        def loop():
            while self.running:
                try:
                    el = self.driver.execute_script("""
                        return document.elementFromPoint(window._mx, window._my);
                    """)

                    if el:
                        self.highlight(el)
                        self.show_element_info(el)

                    time.sleep(0.2)
                except:
                    break

        threading.Thread(target=loop, daemon=True).start()

    def highlight(self, el):
        try:
            self.driver.execute_script("""
                arguments[0].style.outline='2px solid red';
            """, el)
        except:
            pass

    def show_element_info(self, el):
        try:
            tag = el.tag_name

            attrs = self.driver.execute_script("""
                let o = {};
                for (let a of arguments[0].attributes) {
                    o[a.name] = a.value;
                }
                return o;
            """, el)

            text = el.text[:200]

            selector = self.smart_selector(tag, attrs)

            self.info_box.delete("1.0", tk.END)
            self.info_box.insert(tk.END, f"{tag}\n{text}\n\n{json.dumps(attrs, indent=2)}")

            self.selector_box.delete("1.0", tk.END)
            self.selector_box.insert(tk.END, selector)

        except Exception as e:
            self.log(f"[ERROR] {e}")

    # ================= SMART SELECTOR (LEVEL 4 AI STYLE) =================
    def smart_selector(self, tag, attrs):
        if "id" in attrs and attrs["id"]:
            return f"#{attrs['id']}"

        if "class" in attrs:
            classes = attrs["class"].split()
            if len(classes) > 0:
                return tag + "." + ".".join(classes[:2])

        if "data-testid" in attrs:
            return f"[data-testid='{attrs['data-testid']}']"

        return tag

    # ================= TEST =================
    def test_selector(self):
        sel = self.selector_box.get("1.0", tk.END).strip()
        els = self.driver.find_elements(By.CSS_SELECTOR, sel)

        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, f"{len(els)} elements\n\n")

        for e in els[:10]:
            self.result_box.insert(tk.END, e.text + "\n\n")

    # ================= NETWORK =================
    def enable_network(self):
        self.log("[NETWORK] ON")

        def monitor():
            try:
                self.driver.execute_cdp_cmd("Network.enable", {})
                while True:
                    logs = self.driver.get_log("performance")

                    for l in logs:
                        msg = json.loads(l["message"])["message"]

                        if msg["method"] == "Network.requestWillBeSent":
                            url = msg["params"]["request"]["url"]
                            if "api" in url:
                                self.log(f"[API] {url}")

                    time.sleep(1)
            except Exception as e:
                self.log(f"[NET ERROR] {e}")

        threading.Thread(target=monitor, daemon=True).start()

    # ================= EXTRACT LINKS =================
    def extract_links(self):
        els = self.driver.find_elements(By.CSS_SELECTOR, "a")

        links = []
        for e in els:
            href = e.get_attribute("href")
            if href:
                links.append(href)

        links = list(set(links))

        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, "\n".join(links[:50]))

        self.log(f"[LINKS] {len(links)} found")
            
# ================= SCRAPER =================
class DynamicScraper:
    def __init__(self, log_func):
        self.log = log_func
        self.session = requests.Session()
        self.seen_urls = set()
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                self.seen_urls = set(json.load(f))

    def save_cache(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(self.seen_urls), f)

    def safe_get(self, url, retries=3):
        for i in range(retries):
            try:
                res = self.session.get(url, timeout=15)
                if res.status_code == 200:
                    return res
            except:
                time.sleep(1.5 * (i + 1))
        return None

    def smart_select(self, soup, css_list):
        for css in css_list:
            if css:
                el = soup.select_one(css)
                if el:
                    return el.get_text(" ", strip=True)
        return "N/A"

    def fetch_detail(self, url, task):
        if url in self.seen_urls:
            return None

        time.sleep(random.uniform(0.5, 1.5))

        res = self.safe_get(url)
        if not res:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        title = self.smart_select(soup, [task['s_title'], "h1"])
        company = self.smart_select(soup, [task['s_company'], ".company"])
        address = self.smart_select(soup, [task['s_address'], ".address"])

        self.seen_urls.add(url)
        self.log(f"[DETAIL] {company[:20]}")

        return [company, address, url, title]

    def get_next_page(self, soup, base_url):
        btn = soup.select_one("a[rel=next], .next")
        if btn:
            href = btn.get("href")
            if href.startswith("/"):
                return base_url.rstrip("/") + href
            return href
        return None

    def save_csv(self, rows):
        with open("output.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def process_task(self, task, gc, progress_callback=None):
        self.log(f"[TASK] {task['name']}")

        try:
            sh = gc.open_by_key(task['sheet_id'])
            try:
                ws = sh.worksheet(task['tab'])
            except:
                ws = sh.add_worksheet(title=task['tab'], rows="1000", cols="5")
                ws.append_row(["会社名", "住所", "URL", "タイトル"])
        except Exception as e:
            self.log(f"[ERROR] {e}")
            return

        url = task['url']
        page = 1

        while url and page <= 50:
            self.log(f"[PAGE] {page}")

            res = self.safe_get(url)
            if not res:
                break

            soup = BeautifulSoup(res.text, "html.parser")

            links = []
            for a in soup.select(task['s_link']):
                href = a.get("href")
                if not href:
                    continue
                if href.startswith("/") and task['prefix']:
                    href = task['prefix'].rstrip("/") + href
                links.append(href.split("?")[0])

            links = list(set(links))

            self.log(f"[LINKS] {len(links)}")

            results = []
            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = [ex.submit(self.fetch_detail, l, task) for l in links]
                for f in as_completed(futures):
                    r = f.result()
                    if r:
                        results.append(r)

            if results:
                ws.append_rows(results)
                self.save_csv(results)

            if progress_callback:
                progress_callback(page)

            url = self.get_next_page(soup, task['prefix'] or task['url'])
            page += 1

        self.save_cache()


# ================= UI =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🔥 AI Scraper + DevTools")
        self.geometry("1100x850")
        self.tasks = self.load_tasks()
        self.setup_ui()

    def setup_ui(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        frame = ttk.LabelFrame(main, text="Config")
        frame.pack(fill="x")

        self.e_name = ttk.Entry(frame)
        self.e_name.grid(row=0, column=1)

        self.e_url = ttk.Entry(frame, width=50)
        self.e_url.grid(row=0, column=3)

        ttk.Label(frame, text="Name").grid(row=0, column=0)
        ttk.Label(frame, text="URL").grid(row=0, column=2)

        self.e_s_link = ttk.Entry(frame)
        self.e_s_link.grid(row=1, column=1)

        self.e_prefix = ttk.Entry(frame)
        self.e_prefix.grid(row=1, column=3)

        ttk.Label(frame, text="Link CSS").grid(row=1, column=0)
        ttk.Label(frame, text="Prefix").grid(row=1, column=2)

        self.e_s_title = ttk.Entry(frame)
        self.e_s_title.grid(row=2, column=1)

        self.e_s_comp = ttk.Entry(frame)
        self.e_s_comp.grid(row=2, column=3)

        self.e_s_addr = ttk.Entry(frame)
        self.e_s_addr.grid(row=2, column=5)

        ttk.Label(frame, text="Title").grid(row=2, column=0)
        ttk.Label(frame, text="Company").grid(row=2, column=2)
        ttk.Label(frame, text="Address").grid(row=2, column=4)

        self.e_sid = ttk.Entry(frame, width=50)
        self.e_sid.grid(row=3, column=1, columnspan=3)

        self.e_tab = ttk.Entry(frame)
        self.e_tab.grid(row=3, column=5)

        ttk.Label(frame, text="Sheet ID").grid(row=3, column=0)
        ttk.Label(frame, text="Tab").grid(row=3, column=4)

        ttk.Button(frame, text="Add Task", command=self.add_task).grid(row=4, column=0, columnspan=6)

        self.tree = ttk.Treeview(main, columns=("Name", "Sheet", "Tab"), show="headings")
        for c in ("Name", "Sheet", "Tab"):
            self.tree.heading(c, text=c)
        self.tree.pack(fill="x")

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="RUN", command=self.start_thread).pack(side="left")
        ttk.Button(btn_frame, text="🧠 DevTools", command=self.open_devtools).pack(side="left", padx=10)

        self.progress = ttk.Progressbar(main, length=300)
        self.progress.pack()

        self.log_box = scrolledtext.ScrolledText(main, height=20, bg="#111", fg="#0f0")
        self.log_box.pack(fill="both", expand=True)

        self.refresh_table()

    def log(self, msg):
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)

    def open_devtools(self):
        DevToolsWindow(self, self.log)

    def add_task(self):
        task = {
            "name": self.e_name.get(),
            "url": self.e_url.get(),
            "s_link": self.e_s_link.get(),
            "prefix": self.e_prefix.get(),
            "s_title": self.e_s_title.get(),
            "s_company": self.e_s_comp.get(),
            "s_address": self.e_s_addr.get(),
            "sheet_id": self.e_sid.get(),
            "tab": self.e_tab.get(),
        }
        self.tasks.append(task)
        self.save_tasks()
        self.refresh_table()

    def load_tasks(self):
        if os.path.exists("training_config.json"):
            with open("training_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_tasks(self):
        with open("training_config.json", "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=2, ensure_ascii=False)

    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for t in self.tasks:
            self.tree.insert("", "end", values=(t['name'], t['sheet_id'], t['tab']))

    def start_thread(self):
        threading.Thread(target=self.run_engine, daemon=True).start()

    def update_progress(self, page):
        self.progress["value"] = (page / 50) * 100
        self.update_idletasks()

    def run_engine(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
            gc = gspread.authorize(creds)

            scraper = DynamicScraper(self.log)

            for task in self.tasks:
                scraper.process_task(task, gc, self.update_progress)

            messagebox.showinfo("Done", "Completed!")
        except Exception as e:
            self.log(f"[ERROR] {e}")


if __name__ == "__main__":
    App().mainloop()
import os, json, random, time, threading, re, math
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from urllib.parse import urljoin
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
            "theme": {"bg": "#f5f6fa", "log_bg": "#1e272e", "log_fg": "#d2dae2"}
        }
        self.tasks = []; self.selected_task_index = None; self.running = False; self.stop_flag = False
        self.title("HELLOWORK ENGINE - PRO")
        self.geometry("1200x900") # FIXED GEOMETRY
        self.setup_ui()
        self.load_tasks_from_disk()

    def setup_ui(self):
        self.configure(bg=self.config["theme"]["bg"])
        self.notebook = ttk.Notebook(self); self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_editor = ttk.Frame(self.notebook); self.notebook.add(self.tab_editor, text=" ⚙️ Task Manager ")
        self.tab_console = ttk.Frame(self.notebook); self.notebook.add(self.tab_console, text=" 🖥️ Live Console ")
        
        editor_main = ttk.Frame(self.tab_editor); editor_main.pack(fill="both", expand=True, padx=10, pady=10)
        self.ui_task_list = tk.Listbox(editor_main, height=6); self.ui_task_list.pack(fill="x", pady=5)
        self.ui_task_list.bind("<<ListboxSelect>>", self.on_task_click)
        self.json_editor = scrolledtext.ScrolledText(editor_main, height=20, font=("Consolas", 10)); self.json_editor.pack(fill="both", expand=True, pady=5)
        ttk.Button(editor_main, text="💾 SAVE", command=self.sync_from_json_text).pack(fill="x")

        top = ttk.Frame(self.tab_console); top.pack(fill="x", pady=10, padx=10)
        ttk.Button(top, text="▶ START", command=self.run).pack(side="left", padx=5)
        ttk.Button(top, text="🛑 STOP", command=self.stop).pack(side="left", padx=5)
        self.log_box = scrolledtext.ScrolledText(self.tab_console, bg=self.config["theme"]["log_bg"], fg=self.config["theme"]["log_fg"], font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    def load_tasks_from_disk(self):
        if os.path.exists(self.config["tasks_file"]):
            with open(self.config["tasks_file"], 'r', encoding='utf-8') as f: self.tasks = json.load(f)
            self.refresh_list()
    def refresh_list(self):
        self.ui_task_list.delete(0, tk.END)
        for t in self.tasks: self.ui_task_list.insert(tk.END, t['name'])
    def on_task_click(self, e):
        if not self.ui_task_list.curselection(): return
        idx = self.ui_task_list.curselection()[0]; self.selected_task_index = idx
        self.json_editor.delete("1.0", tk.END); self.json_editor.insert("1.0", json.dumps(self.tasks[idx], indent=2, ensure_ascii=False))
    def sync_from_json_text(self):
        try:
            data = json.loads(self.json_editor.get("1.0", tk.END))
            if self.selected_task_index is not None: self.tasks[self.selected_task_index] = data
            else: self.tasks.append(data)
            with open(self.config["tasks_file"], 'w', encoding='utf-8') as f: json.dump(self.tasks, f, indent=2, ensure_ascii=False)
            self.refresh_list(); messagebox.showinfo("Success", "Saved")
        except Exception as e: messagebox.showerror("Error", str(e))
    def log(self, msg): self.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))
    def stop(self): self.stop_flag = True
    def run(self):
        if self.running or self.selected_task_index is None: return
        self.running = True; self.stop_flag = False; self.notebook.select(self.tab_console)
        threading.Thread(target=self.engine_start, args=(self.tasks[self.selected_task_index],), daemon=True).start()

    # ================= THE COMPLETE PRODUCTION ENGINE =================
    def engine_start(self, task):
        try:
            # 1. Sheets Setup
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.config["auth_file"], scope)
            gc = gspread.authorize(creds)
            ws = gc.open_by_key(task['sheet_id']).worksheet(task['tab'])

            # 2. Initialize Session
            session = crequests.Session(impersonate="chrome120")
            session.headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "ja-JP,ja;q=0.9",
                "Connection": "keep-alive",
                "Host": "jinzai.hellowork.mhlw.go.jp",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })

            # --- STEP 1: PORTAL ENTRY ---
            self.log("📡 Step 1: Loading Portal...")
            entry_url = "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do?action=initDisp&screenId=GICB101010"
            session.headers.update({"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1"})
            res_portal = session.get(entry_url, timeout=30)
            
            soup_portal = BeautifulSoup(res_portal.text, "html.parser")
            form = soup_portal.find("form", {"id": "ID_multiForm1"})
            payload = {el.get("name"): el.get("value", "") for el in form.find_all("input", {"type": "hidden"}) if el.get("name")}
            
            payload.update({
                "params": "0",
                "action": "transition",
                "hfTransitionIdx": "0",
                "screenId": "GICB101010",
                "codeAssistType": "", "codeAssistKind": "", "codeAssistCode": "",
                "codeAssistItemCode": "", "codeAssistItemName": "", "codeAssistDivide": "",
                "maba_vrbs": ""
            })

            time.sleep(random.uniform(2, 4))

            # --- STEP 2: TRANSITION ---
            self.log("🔘 Step 2: Submitting Transition...")
            session.headers.update({"Origin": "https://jinzai.hellowork.mhlw.go.jp", "Referer": entry_url, "Content-Type": "application/x-www-form-urlencoded", "Sec-Fetch-Site": "same-origin"})
            post_url = "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do"
            res_trans = session.post(post_url, data=payload, timeout=30)
            
            if "GICB102010" not in res_trans.text:
                self.log("🚨 BLOCK at Step 2.")
                return

            time.sleep(random.uniform(3, 5))

            # --- STEP 3: SEARCH EXECUTION ---
            self.log("🔍 Step 3: Executing Search Query...")
            soup_search = BeautifulSoup(res_trans.text, "html.parser")
            search_form = soup_search.find("form", {"id": "ID_multiForm1"})
            search_payload = {el.get("name"): el.get("value", "") for el in search_form.find_all("input", {"type": "hidden"}) if el.get("name")}
            
            # Use task URL but target GICB102010
            search_payload.update({
                "action": "search",
                "cbKanto": "1", "cbIbaragi": "1", "cbTochigi": "1", "cbGunma": "1",
                "cbSaitama": "1", "cbChiba": "1", "cbTokyo": "1", "cbKanagawa": "1",
                "cbJigyonushiName": "1", "cbJigyoshoName": "1",
                "nm_btnSearch.x": "100", "nm_btnSearch.y": "20",
                "hfScrollTop": "1764",
                "screenId": "GICB102010"
            })

            search_do_url = "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB102010.do"
            session.headers.update({"Referer": search_do_url})
            res_final = session.post(search_do_url, data=search_payload, timeout=30)

            # --- STEP 4: RESULT VALIDATION & SCRAPE LOOP ---
            soup_final = BeautifulSoup(res_final.text, "html.parser")
            stats = soup_final.select_one(task['stats_sel'])
            
            if not stats:
                self.log("⚠️ Results not found.")
                return

            total_items = int(re.sub(r'\D', '', stats.get_text()))
            total_pages = math.ceil(total_items / 20)
            self.log(f"📊 SUCCESS: Found {total_items} items. Starting loop...")

            for p in range(1, total_pages + 1):
                if self.stop_flag: break
                self.log(f"📄 Page {p}/{total_pages}")
                
                if p > 1:
                    search_payload["curPage"] = str(p)
                    res_final = session.post(search_do_url, data=search_payload)
                    soup_final = BeautifulSoup(res_final.text, "html.parser")

                # Extract links on current page
                links = [urljoin(search_do_url, a.get("href")) for a in soup_final.select(task['s_link']) if a.get("href")]
                links = list(dict.fromkeys(links)) 
                
                results_batch = []
                for link in links:
                    if self.stop_flag: break
                    data = self.fetch_detail(session, link, task['fields'], referer=search_do_url)
                    if data:
                        results_batch.append(data)
                        self.log(f"   ✅ {data.get('会社名', '...')[:15]}")
                    time.sleep(random.uniform(5, 8)) # CRITICAL: Do not lower this for 20k items

                if results_batch:
                    headers = ["URL"] + list(task['fields'].keys())
                    ws.append_rows([[r.get(h, "") for h in headers] for r in results_batch])
                    self.log(f"💾 Page {p} saved to Google Sheets.")

        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
        finally:
            self.running = False; self.log("🏁 Engine Stopped.")

    def fetch_detail(self, session, url, fields, referer):
        try:
            session.headers.update({"Referer": referer})
            r = session.get(url, timeout=25)
            if "セキュリティー" in r.text or "サーバーでエラー" in r.text:
                return None
            s = BeautifulSoup(r.text, "html.parser")
            data = {"URL": url}
            for k, v in fields.items():
                el = s.select_one(v)
                data[k] = el.get_text(strip=True) if el else "N/A"
            return data
        except:
            return None

if __name__ == "__main__": App().mainloop()
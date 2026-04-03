import wx
import wx.adv
import threading
import requests
import json
import shutil
import re
import time
import random
import zipfile
import os
import logging
from os import path
from typing import List, Dict, Any

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# Google Sheets
from gspread import service_account

# ==============================================================================
# CONFIG
# ==============================================================================

FILE_PATH = path.abspath(__file__)
DIR_PATH = path.dirname(FILE_PATH)
SERVICE_ACCOUNT_FILE = path.join(DIR_PATH, "service-account.json")

LOG_FILE = path.join(DIR_PATH, "debug.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

GSHEET_ID = "19cpI7FRotk1YvePyrFWIOwsFmCOxSbwfp85goXZbgE4"
WORKSHEET_TITLE = "AI-Search"
MIN_DELAY_SECONDS = 8

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/118 Safari/537.36",
]

# ==============================================================================
# DRIVER
# ==============================================================================

def init_driver(proxy=None):
    logger.debug(f"Init driver with proxy: {proxy}")

    options = Options()
    ua = random.choice(USER_AGENTS)

    options.add_argument(f"--user-agent={ua}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    })

    logger.debug("Driver initialized successfully")
    return driver

# ==============================================================================
# SCRAPER
# ==============================================================================

def scrape_google(query, driver, retry=2):
    logger.debug(f"Query: {query}")

    url = "https://www.google.com/search?q=" + requests.utils.quote(query)

    for attempt in range(retry):
        try:
            driver.get(url)
            time.sleep(random.uniform(2, 4))

            html = driver.page_source.lower()

            # Detect block
            if "captcha" in html or "unusual traffic" in html:
                logger.warning(f"Blocked on attempt {attempt+1}")
                time.sleep(5 + attempt * 5)
                continue

            soup = BeautifulSoup(driver.page_source, "html.parser")

            result = {
                "postal_code": "N/A",
                "address": "N/A",
                "phone": "N/A",
                "website": "#"
            }

            for g in soup.select("div.g")[:5]:
                txt = g.get_text(" ", strip=True)

                if result["postal_code"] == "N/A":
                    m = re.search(r"\d{3}-\d{4}", txt)
                    if m:
                        result["postal_code"] = m.group()

                if result["phone"] == "N/A":
                    m = re.search(r"(0\d{1,4}-\d{1,4}-\d{3,4})", txt)
                    if m:
                        result["phone"] = m.group()

                if result["website"] == "#":
                    a = g.select_one("a")
                    if a:
                        result["website"] = a.get("href")

            logger.debug(f"Parsed result: {result}")
            return result

        except Exception:
            logger.exception("Scrape failed, retrying...")
            time.sleep(3)

    return None

# ==============================================================================
# UI
# ==============================================================================

class App(wx.Frame):
    def __init__(self):
        super().__init__(None, title="AI Scraper DEBUG", size=(700, 750))
        self.driver = None
        self.running = False
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.sheet = wx.TextCtrl(panel, value=GSHEET_ID)
        self.start_btn = wx.Button(panel, label="START")
        self.start_btn.Bind(wx.EVT_BUTTON, self.start)

        self.log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)

        vbox.Add(self.sheet, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.start_btn, 0, wx.ALL, 5)
        vbox.Add(self.log, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(vbox)
        self.Show()

    def ui_log(self, msg):
        wx.CallAfter(self.log.AppendText, msg + "\n")
        logger.info(msg)

    def start(self, e):
        if not self.running:
            self.running = True
            threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            self.ui_log("Starting...")

            self.driver = init_driver()

            gc = service_account(filename=SERVICE_ACCOUNT_FILE)
            sheet = gc.open_by_key(self.sheet.GetValue()).worksheet(WORKSHEET_TITLE)

            rows = sheet.get_all_values()
            logger.debug(f"Total rows: {len(rows)}")

            # ===============================
            # AUTO-FILL DEMO DATA
            # ===============================
            if len(rows) <= 1:
                self.ui_log("⚠️ Sheet empty → auto inserting demo data...")

                demo_data = [
                    ["DYMVietnam", "Ho Chi Minh"],
                    ["FPT Software", "Vietnam"],
                    ["VNG Corporation", "Vietnam"],
                    ["Viettel Group", "Vietnam"],
                    ["VinGroup", "Vietnam"],
                ]

                # Ensure header exists
                if len(rows) == 0:
                    sheet.append_row(["Name", "Location", "Postal", "Address", "Phone", "Website"])

                for row in demo_data:
                    sheet.append_row(row)

                time.sleep(2)  # wait for sheet update
                rows = sheet.get_all_values()

                self.ui_log(f"✅ Inserted {len(demo_data)} demo rows")

            # ===============================
            # BUILD TASKS
            # ===============================
            tasks = []

            for i, r in enumerate(rows[1:], start=2):
                if len(r) < 2:
                    continue

                name = r[0].strip()
                location = r[1].strip()

                if not name:
                    continue

                # Skip processed
                if len(r) >= 3 and r[2].strip():
                    continue

                query = f"{name} {location}"
                tasks.append((i, query))

            self.ui_log(f"Tasks: {len(tasks)}")

            if not tasks:
                self.ui_log("No tasks found after filtering.")
                return

            # ===============================
            # RUN SCRAPER
            # ===============================
            for i, query in tasks:
                start = time.time()

                self.ui_log(f"Searching: {query}")

                res = scrape_google(query, self.driver)

                if res:
                    try:
                        sheet.update(f"C{i}:F{i}", [[
                            res["postal_code"],
                            res["address"],
                            res["phone"],
                            res["website"]
                        ]])
                        logger.debug(f"Updated row {i}")
                    except Exception:
                        logger.exception("Sheet update failed")

                duration = time.time() - start
                logger.debug(f"Time: {duration:.2f}s")

                wait = random.uniform(MIN_DELAY_SECONDS, MIN_DELAY_SECONDS + 5)
                logger.debug(f"Sleep: {wait:.2f}s")

                time.sleep(wait)

            self.ui_log("DONE")

        except Exception:
            logger.exception("Worker crashed")

        finally:
            if self.driver:
                self.driver.quit()
            self.running = False
            
# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    app = wx.App()
    App()
    app.MainLoop()
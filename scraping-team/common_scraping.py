#coding: UTF-8
from google.oauth2.service_account import Credentials
import gspread
import logging
import os
import random
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import socket
import time

from chatwork import Chatwork


class CommonScraping():
    def __init__(self, file_name: str) -> None:
        # Beautifulsoup
        self.session = requests.Session()
        # Chatwork
        self.chatwork = Chatwork(
            os.environ['CHATWORK_RID'],
            file_name,
            os.environ['CHATWORK_TOKEN']
        )
        #Chrome
        self.set_driver()
        # Log
        self.set_log(file_name)
        # Spread
        self.sheet_id = os.environ['SPREAD_ID']
        self.sheet_name = os.environ['SHEET_NAME']
        self.set_spread()

    def set_driver(self) -> None:
        try:
            hostname = socket.gethostname()
            if "ap-northeast-1" in hostname:
                from selenium.webdriver.chrome.options import Options
                chrome_options = Options()
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--disable-infobars")
                chrome_options.add_argument("--disable-notifications")
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--remote-debugging-port=9222")
                self.driver = webdriver.Chrome(options=chrome_options)
            else:
                self.driver = webdriver.Chrome()
            self.driver.implicitly_wait(3)
            self.driver.set_window_size(1920, 1024)
        except Exception as e:
            self.logger.error(f"An error occurred: {e}", exc_info=True)
            raise

    def set_log(self, file_name) -> None:
        log_dir = "log"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, file_name)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)

    def set_spread(self) -> None:
        scopes = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_file(
            'service-account.json',
            scopes=scopes
        )
        gc = gspread.authorize(credentials)
        sheet_id = self.sheet_id
        sheet_name = self.sheet_name
        self.spread = gc.open_by_key(sheet_id).worksheet(sheet_name)

    def print_and_log_info(self, info: str) -> None:
        print(info)
        self.logger.info(info)

    def error_catch(self, error: Exception, alert_message: str) -> None:
        print(error)
        self.logger.error(f"An error occurred: {error}", exc_info=True)
        self.chatwork.send_alert(True, alert_message )

    def fetch_page(self, url, headers=None):
        if headers is None:
            headers = {}
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        return response.content

    def fetch_with_backoff(self, url, headers, max_retry=5):
        for attempt in range(max_retry):
            res = self.session.get(url, headers=headers)
            if res.status_code == 200:
                return res.content
            elif res.status_code == 403:
                wait = random.randint(5, 10)
                print(f"403出た… {wait}秒まつわ…🥺")
                time.sleep(wait)
                self.session = requests.Session()
            else:
                print(f"status: {res.status_code}, retry中…")
                time.sleep(5)
        return None

    def wait_for_page_load(self, second) -> None:
        WebDriverWait(self.driver, second).until(
            lambda driver: driver.execute_script("return document.readyState")
            == "complete"
        )

    def wait_for_selector_catch(self, second: int, selector: str) -> WebElement:
        element = WebDriverWait(self.driver, second).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element

    def clean_company_name(self, company_name: str) -> str:
        SPECIAL_CHARACTERS = "[『』「」【】《》（）()〔〕]"
        company_name = re.sub(SPECIAL_CHARACTERS, "", company_name)
        company_name = re.sub(r'[^\w\s]', '', company_name, flags=re.UNICODE)
        company_name = re.sub(r'\s+', ' ', company_name).strip()
        return company_name
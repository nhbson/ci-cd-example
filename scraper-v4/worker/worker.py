import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import redis
import json
import time
from core.scraper import scrape_google
from core.driver import init_driver
from core.proxy import get_proxy

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
MAX_TASKS_PER_DRIVER = 5
QUEUE = "scraper:tasks"

def worker_loop():
    driver = init_driver()
    task_count = 0

    while True:
        try:
            task_data = r.brpop(QUEUE, timeout=5)
            if not task_data:
                continue

            _, task_json = task_data
            task = json.loads(task_json)

            result = scrape_google(task["query"], driver)

            print("[DONE]", task["query"], "->", result)

            task_count += 1

            # 🔥 ROTATE DRIVER
            if task_count >= MAX_TASKS_PER_DRIVER:
                print("[INFO] Restarting driver...")
                driver.quit()
                driver = init_driver()
                task_count = 0

        except Exception as e:
            print("[ERROR]", e)

            # 🔥 FORCE RESET DRIVER
            try:
                driver.quit()
            except:
                pass

            driver = init_driver()
            task_count = 0

if __name__ == "__main__":
    worker_loop()
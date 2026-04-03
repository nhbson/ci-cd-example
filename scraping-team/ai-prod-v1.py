import time
import random
import json
from playwright.sync_api import sync_playwright

# =========================
# STEALTH IMPORT (SAFE)
# =========================
try:
    from playwright_stealth import stealth
except:
    try:
        from playwright_stealth.stealth import stealth_sync as stealth
    except:
        stealth = None


# =========================
# CONFIG
# =========================
TARGET_URL = "https://gigabaito.com/"
SEARCH_KEYWORD = "ギガバイト バイト"

PROXY_POOL = [
    "http://172.23.229.61:3128",  # local proxy
    # "http://user:pass@residential-proxy:port",  # add real proxy here
]

MAX_RETRIES = 3


# =========================
# UTIL
# =========================
def human_delay(a=2, b=5):
    time.sleep(random.uniform(a, b))


def get_proxy(target=None):
    """
    Smart routing:
    - gigabaito → prefer residential
    - fallback → local proxy
    """
    for p in PROXY_POOL:
        if "127.0.0.1" not in p:
            return p
    return PROXY_POOL[0] if PROXY_POOL else None


def is_blocked(page):
    html = page.content()
    keywords = ["CloudFront", "Request blocked", "Access Denied", "403 ERROR"]
    return any(k in html for k in keywords)


def debug_block(page, tag="blocked"):
    print("[DEBUG] Saving debug info...")
    page.screenshot(path=f"{tag}.png")
    with open(f"{tag}.html", "w", encoding="utf-8") as f:
        f.write(page.content())


# =========================
# BROWSER FACTORY
# =========================
def create_browser(p, proxy=None):
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )

    context_args = {
        "locale": "ja-JP",
        "timezone_id": "Asia/Tokyo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "viewport": {"width": 1280, "height": 800},
    }

    if proxy:
        context_args["proxy"] = {"server": proxy}
        print(f"[PROXY] Using {proxy}")

    context = browser.new_context(**context_args)

    return browser, context


# =========================
# SESSION
# =========================
def save_session(context):
    try:
        cookies = context.cookies()
        with open("session.json", "w") as f:
            json.dump(cookies, f)
    except:
        pass


def load_session(context):
    try:
        with open("session.json", "r") as f:
            cookies = json.load(f)
            context.add_cookies(cookies)
            print("[SESSION] Loaded cookies")
    except:
        pass


# =========================
# HUMAN ENTRY (OPTIONAL)
# =========================
def open_via_google(page):
    if stealth:
        try:
            stealth(page)
        except:
            pass

    print("[STEP] Google entry")
    page.goto("https://www.google.com/")
    page.wait_for_load_state("networkidle")
    human_delay()

    page.fill("input[name='q']", SEARCH_KEYWORD)
    human_delay(1, 2)
    page.keyboard.press("Enter")

    page.wait_for_load_state("networkidle")
    human_delay(3, 5)

    links = page.query_selector_all("a")

    for a in links:
        try:
            href = a.get_attribute("href")
            if href and "gigabaito.com" in href:
                print("[CLICK] Google result")
                a.click()
                break
        except:
            continue

    page.wait_for_load_state("networkidle")
    human_delay(4, 6)


# =========================
# SAFE NAVIGATION (WITH PROXY ROTATION)
# =========================
def safe_open_with_retry(p, url):
    for attempt in range(MAX_RETRIES):
        proxy = get_proxy(url)

        browser, context = create_browser(p, proxy)
        load_session(context)

        page = context.new_page()

        if stealth:
            try:
                stealth(page)
            except:
                pass

        try:
            print(f"[NAVIGATE] Attempt {attempt+1} → {url}")
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle")
            human_delay()

            if is_blocked(page):
                raise Exception("Blocked")

            print("[SUCCESS] Page loaded")
            return browser, context, page

        except Exception as e:
            print(f"[RETRY] {attempt+1} - {e}")
            debug_block(page, f"blocked_{attempt}")
            browser.close()
            human_delay(3, 6)

    return None, None, None


# =========================
# LINK EXTRACTOR
# =========================
def extract_links(page):
    print("[STEP] Extract links")

    links = page.eval_on_selector_all(
        "a",
        "els => els.map(e => e.href)"
    )

    results = [
        l for l in links
        if l and ("outline" in l or "corp" in l or "job" in l)
    ]

    results = list(set(results))

    print(f"[INFO] Found {len(results)} links")

    for l in results[:10]:
        print("[LINK]", l)

    return results[:20]


# =========================
# MAIN ENGINE
# =========================
def run_engine():
    with sync_playwright() as p:

        browser, context, page = safe_open_with_retry(p, TARGET_URL)

        if not page:
            print("[FAIL] Cannot bypass block")
            return []

        links = extract_links(page)

        save_session(context)
        browser.close()

        return links


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    data = run_engine()

    print("\n=== RESULT ===")
    for d in data:
        print(d)
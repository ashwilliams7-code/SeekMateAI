"""
LongFormBot — Standalone bot for external job applications on SEEK.

Searches SEEK for jobs, identifies those requiring external applications
(company portals like Workday, Greenhouse, etc.), and uses the LongFormEngine
to complete multi-page application forms automatically.

Usage:
    python longform_bot.py

Controlled via longform_control.json (pause/stop signals from longform_gui.py).
Logs to longform_log.txt for live dashboard tailing.
"""

import builtins
import os
import json
import time
import sys
import re
import random
import tempfile
import urllib.request
import urllib.parse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from openai import OpenAI
from datetime import datetime, timedelta


# ============================================
# RESOURCE PATH
# ============================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_dir():
    if sys.platform == "darwin":
        data_dir = os.path.expanduser("~/Library/Application Support/SeekMateAI")
    elif sys.platform == "win32":
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SeekMateAI")
    else:
        data_dir = os.path.expanduser("~/.seekmateai")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# ============================================
# LOGGING
# ============================================
LOG_FILE = os.path.join(get_data_dir(), "longform_log.txt")
_orig_print = builtins.print

def print(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except:
        pass
    _orig_print(*args, **kwargs)


# ============================================
# CONFIG
# ============================================
CONFIG_FILE = resource_path("config.json")

if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}. Run config_gui.exe first.")

CONFIG = {}

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def reload_config():
    global CONFIG, SCAN_SPEED, APPLY_SPEED, COOLDOWN_DELAY, STEALTH_MODE
    global MAX_JOBS, JOB_TITLE, LOCATION, BLOCKED_COMPANIES, BLOCKED_TITLES
    CONFIG = load_config()
    SCAN_SPEED = CONFIG.get("SCAN_SPEED", 50) * 10  # normalize 1-10 → 10-100
    APPLY_SPEED = CONFIG.get("APPLY_SPEED", 50) * 10
    COOLDOWN_DELAY = CONFIG.get("COOLDOWN_DELAY", 5)
    STEALTH_MODE = CONFIG.get("STEALTH_MODE", False)
    MAX_JOBS = CONFIG.get("MAX_JOBS", 100)
    JOB_TITLE = CONFIG.get("JOB_TITLE", "director")
    LOCATION = CONFIG.get("LOCATION", "Gold Coast, Australia")
    BLOCKED_COMPANIES = [c.lower().strip() for c in CONFIG.get("BLOCKED_COMPANIES", [])]
    BLOCKED_TITLES = [t.lower().strip() for t in CONFIG.get("BLOCKED_TITLES", [])]

reload_config()


# ============================================
# CONTROL SIGNALS (longform_control.json)
# ============================================
CONTROL_FILE = resource_path("longform_control.json")

def check_control():
    try:
        if os.path.exists(CONTROL_FILE):
            with open(CONTROL_FILE, "r") as f:
                data = json.load(f)
                if data.get("stop", False):
                    return "stop"
                if data.get("pause", False):
                    return "pause"
    except:
        pass
    return "run"

def write_control(pause=None, stop=None):
    data = {"pause": False, "stop": False}
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r") as f:
                data.update(json.load(f))
        except:
            pass
    if pause is not None:
        data["pause"] = pause
    if stop is not None:
        data["stop"] = stop
    with open(CONTROL_FILE, "w") as f:
        json.dump(data, f)

def wait_while_paused():
    while True:
        status = check_control()
        if status == "stop":
            print("[!] Stop signal received.")
            return False
        elif status == "pause":
            time.sleep(0.5)
            continue
        else:
            return True


# ============================================
# SPEED & TIMING
# ============================================
def get_scan_multiplier():
    if SCAN_SPEED >= 95: return 0.02
    elif SCAN_SPEED >= 75: return 0.15
    elif SCAN_SPEED >= 50: return 0.4
    elif SCAN_SPEED >= 25: return 0.8
    else: return 1.5

def get_apply_multiplier():
    if APPLY_SPEED >= 95: return 0.02
    elif APPLY_SPEED >= 75: return 0.15
    elif APPLY_SPEED >= 50: return 0.4
    elif APPLY_SPEED >= 25: return 0.8
    else: return 1.5

def throttle():
    if SCAN_SPEED >= 90: return
    if SCAN_SPEED >= 75: time.sleep(0.1)
    elif SCAN_SPEED >= 50: time.sleep(0.3)
    else: time.sleep(0.6)

def speed_sleep(base, mode="scan"):
    multiplier = get_scan_multiplier() if mode == "scan" else get_apply_multiplier()
    actual_delay = base * multiplier
    if mode == "scan":
        actual_delay = max(actual_delay, 0.05 if SCAN_SPEED >= 95 else 0.1)
    else:
        actual_delay = max(actual_delay, 0.02 if APPLY_SPEED >= 95 else 0.05)
    time.sleep(actual_delay)

def job_cooldown():
    if COOLDOWN_DELAY > 0:
        print(f"    [*] Cooldown: waiting {COOLDOWN_DELAY}s before next job...")
        time.sleep(COOLDOWN_DELAY)


# ============================================
# STEALTH MODE
# ============================================
def stealth_random_scroll(driver):
    if not STEALTH_MODE: return
    try:
        actions = [
            ("down", random.randint(100, 400)),
            ("up", random.randint(50, 200)),
            ("down", random.randint(200, 500)),
        ]
        for direction, amount in random.sample(actions, random.randint(1, 2)):
            sign = "" if direction == "down" else "-"
            driver.execute_script(f"window.scrollBy(0, {sign}{amount});")
            time.sleep(random.uniform(0.3, 0.8))
    except: pass

def stealth_random_pause():
    if not STEALTH_MODE: return
    time.sleep(random.uniform(0.5, 2.5))

def stealth_reading_delay():
    if not STEALTH_MODE: return
    time.sleep(random.uniform(2, 6))

def stealth_before_click():
    if not STEALTH_MODE: return
    time.sleep(random.uniform(0.2, 0.6))

def stealth_page_behavior(driver):
    if not STEALTH_MODE: return
    try:
        if random.random() > 0.5: stealth_random_scroll(driver)
        stealth_reading_delay()
    except: pass


# ============================================
# TITLE MATCHING & FILTERS
# ============================================
def detect_category(titles):
    titles_norm = [t.lower().strip() for t in titles]
    gov_kw = ["el1", "el 1", "el2", "el 2", "ses", "ses1", "ses 1", "ses2", "ses 2",
              "policy", "governance", "compliance", "public sector", "principal", "advisor"]
    if any(k in t for t in titles_norm for k in gov_kw): return "gov"
    if any(t in titles_norm for t in ["director", "program director", "operations director",
        "project director", "head of", "general manager", "executive", "principal",
        "portfolio manager", "gm"]): return "leadership"
    if any(t in titles_norm for t in ["project manager", "program manager", "agile",
        "scrum master", "project lead", "delivery manager"]): return "project"
    if any(t in titles_norm for t in ["bdm", "business development", "sales", "account manager",
        "relationship manager", "client", "growth", "partnership"]): return "sales"
    if any(t in titles_norm for t in ["research", "policy", "community", "anthropology",
        "program officer", "stakeholder engagement"]): return "social"
    if any(t in titles_norm for t in ["admin", "coordinator", "ea", "executive assistant"]): return "admin"
    if any(t in titles_norm for t in ["it", "developer", "engineer", "software", "cyber",
        "cloud", "data"]): return "it"
    return "generic"

def title_matches(title):
    allowed = [t.lower().strip() for t in CONFIG.get("JOB_TITLES", [])]
    title_clean = title.lower().strip()
    if any(a in title_clean for a in allowed): return True
    title_words = [w for w in title_clean.replace('-', ' ').split() if len(w) > 3]
    for word in title_words:
        if any(word in a for a in allowed): return True
    cat = detect_category(allowed)
    category_map = {
        "social": ["research", "policy", "community", "program", "stakeholder",
                    "case manager", "social", "analyst", "coordinator", "officer",
                    "engagement", "advisor", "consultant", "specialist"],
        "gov": ["el1", "el 1", "el2", "el 2", "ses", "director", "policy",
                "principal", "executive", "governance", "advisor", "analyst",
                "coordinator", "officer", "manager", "public sector"],
        "project": ["project", "program", "delivery", "scrum", "agile", "lead",
                     "coordinator", "manager", "officer", "analyst"],
        "sales": ["bdm", "business development", "sales", "account", "partnership",
                   "growth", "client", "relationship", "solutions", "commercial"],
        "leadership": ["director", "head", "general manager", "gm", "executive",
                        "principal", "lead", "chief", "senior", "manager"],
        "admin": ["admin", "coordinator", "ea", "executive assistant",
                   "office", "project coordinator", "officer", "support"],
        "it": ["developer", "engineer", "software", "it", "cloud", "cyber",
               "product", "technical", "devops", "data", "analyst"],
    }
    related = category_map.get(cat, [])
    if any(r in title_clean for r in related): return True
    return False

def is_company_blocked(company):
    if not BLOCKED_COMPANIES: return False
    return any(b in company.lower().strip() for b in BLOCKED_COMPANIES)

def is_title_blocked(title):
    if not BLOCKED_TITLES: return False
    return any(b in title.lower().strip() for b in BLOCKED_TITLES)


# ============================================
# SEEK URL BUILDER
# ============================================
def build_search_url(job_title, location):
    safe_location = location.replace(", Australia", "").strip()
    job_query = job_title.replace(" ", "%20")
    loc_query = safe_location.replace(" ", "%20")
    return f"https://www.seek.com.au/jobs?keywords={job_query}&where={loc_query}&sortmode=ListedDate"


# ============================================
# BROWSER INIT
# ============================================
def init_browser():
    chrome_options = Options()
    run_headless = os.getenv("RUN_HEADLESS", "false").lower() == "true"

    if run_headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        print("[INFO] Running in HEADLESS mode")
    else:
        chrome_options.add_argument("--start-maximized")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")

    # Use separate Chrome profile for long-form bot
    profile_dir = os.path.join(tempfile.gettempdir(), "seekmate_longform_chrome")
    os.makedirs(profile_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    if SCAN_SPEED >= 90: driver.implicitly_wait(0.1)
    elif SCAN_SPEED >= 50: driver.implicitly_wait(1)
    else: driver.implicitly_wait(3)

    return driver


# ============================================
# OPENAI GPT
# ============================================
OPENAI_API_KEY = CONFIG.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
OPENAI_MODEL = "gpt-4.1-mini"


# ============================================
# LONG-FORM BOT
# ============================================
class LongFormBot:
    def __init__(self, driver):
        self.driver = driver
        self.successful_submits = 0
        self.applied_job_titles = []
        self.skipped_quick_apply = 0

        # OpenAI client
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

        # WebDriverWait timeout
        self.wait = WebDriverWait(driver, 10 if SCAN_SPEED < 50 else 5)

    def gpt(self, system_prompt, user_prompt):
        if not self.client:
            print("    [!] No OpenAI API key configured")
            return ""
        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=800,
                temperature=0.4,
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            print(f"    [!] GPT ERROR: {e}")
            return ""

    def ensure_logged_in(self):
        self.driver.get("https://www.seek.com.au/")
        speed_sleep(5, "scan")
        throttle()
        sign_in = self.driver.find_elements(By.XPATH, "//a[contains(., 'Sign in')]")
        if sign_in:
            print("[!] Not logged in. Log in manually...")
            input("Press ENTER after logging in...")
        else:
            print("[*] Already logged in to SEEK.")

    def get_job_cards(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "article[data-automation='normalJob']")
        if not cards:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "article")
        print(f"[*] Found {len(cards)} jobs on this page.")
        return cards

    def get_total_job_count(self):
        try:
            for selector in [
                "span[data-automation='totalJobs']",
                "span[data-automation='jobsCount']",
                "h1[data-automation='searchResults']",
                "div[data-automation='searchResults'] span",
            ]:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, selector):
                        match = re.search(r'([\d,]+)\s*jobs?', el.text.strip(), re.IGNORECASE)
                        if match:
                            return int(match.group(1).replace(',', ''))
                except: continue
            try:
                for el in self.driver.find_elements(By.XPATH, "//span[contains(text(), 'jobs')]"):
                    match = re.search(r'([\d,]+)\s*jobs?', el.text.strip(), re.IGNORECASE)
                    if match:
                        return int(match.group(1).replace(',', ''))
            except: pass
            cards = self.get_job_cards()
            return len(cards) * 2 if cards else 0
        except Exception as e:
            print(f"    [!] Could not get job count: {e}")
            return 0

    def open_job(self, card):
        throttle()
        stealth_before_click()
        try:
            link = card.find_element(By.CSS_SELECTOR, "a[data-automation='jobTitle']")
            href = link.get_attribute("href")
            self.driver.execute_script("window.open(arguments[0], '_blank');", href)
            speed_sleep(2, "scan")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            stealth_page_behavior(self.driver)
            print(f"    [+] Opened: {href}")
            return href
        except Exception:
            print("    [-] Failed to open job tab.")
            return ""

    def get_description(self):
        for sel in ["[data-automation='jobDescription']",
                     "div[data-automation*='jobAdDetails']",
                     "div[data-automation*='job']"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                txt = el.text.strip()
                if len(txt) > 50: return txt
            except: continue
        return ""

    def go_to_next_page(self):
        try:
            for sel in ["//a[@aria-label='Next']", "//a[contains(text(), 'Next')]",
                         "//button[@aria-label='Next']", "//button[contains(text(), 'Next')]"]:
                try:
                    btn = self.driver.find_element(By.XPATH, sel)
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    speed_sleep(0.5, "scan")
                    throttle()
                    self.driver.execute_script("arguments[0].click();", btn)
                    print("[*] Next page clicked.")
                    speed_sleep(3, "scan")
                    throttle()
                    return True
                except: continue
            print("[!] Next page button not found.")
            return False
        except Exception as e:
            print(f"Next page error: {e}")
            return False

    def check_external_apply(self):
        """Check if current job page has an external apply button. Returns the button or None."""
        try:
            external = self.driver.find_elements(
                By.XPATH,
                "//button[contains(., 'company site') or contains(., 'Apply on company')]"
            )
            if external:
                return external[0]
        except: pass
        return None

    def check_quick_apply(self):
        """Check if current job page has a Quick Apply button."""
        try:
            for xpath in [
                "//button[contains(., 'Quick apply')]",
                "//button[contains(., 'Quick Apply')]",
                "//button[.//span[contains(text(), 'Quick apply')]]",
            ]:
                btns = self.driver.find_elements(By.XPATH, xpath)
                if btns:
                    return True
        except: pass
        return False

    def apply_external(self, external_button, job_title, company, job_url, description):
        """Run the LongFormEngine on this external application."""
        try:
            from longform import LongFormEngine
            lf = LongFormEngine(self.driver, CONFIG, self.gpt)
            result = lf.run(external_button, job_title, company, job_url, description)

            if result.get("success"):
                self.successful_submits += 1
                self.applied_job_titles.append(job_title)
                print(f"    [+] Long-form application SUBMITTED for {job_title} @ {company}")
                print(f"    [+] Successful submissions: {self.successful_submits}")
            else:
                print(f"    [-] Long-form FAILED: {result.get('reason', 'Unknown')}")

            return result
        except Exception as e:
            print(f"    [-] Long-form engine error: {e}")
            return {"success": False, "reason": str(e)}

    def run(self):
        """Main bot loop — scan SEEK, find external jobs, apply via LongFormEngine."""
        reload_config()
        write_control(pause=False, stop=False)
        run_start_time = time.time()

        print("\n" + "=" * 60)
        print("  SEEKMATE LONG-FORM BOT")
        print("  External Application Engine")
        print("=" * 60)
        print(f"  Target: {MAX_JOBS} applications")
        print(f"  Location: {LOCATION}")
        print(f"  Job Titles: {len(CONFIG.get('JOB_TITLES', []))} configured")
        print("=" * 60 + "\n")

        # Ensure logged in
        self.ensure_logged_in()

        job_titles = CONFIG.get("JOB_TITLES", [])
        if not job_titles:
            print("[!] No job titles configured.")
            return

        # Location strategy: primary + alternatives
        primary_location = LOCATION
        alternative_locations = [
            "Brisbane, Australia", "Gold Coast, Australia",
            "Sydney, Australia", "Melbourne, Australia",
            "Perth, Australia", "Adelaide, Australia",
            "Canberra, Australia", "Newcastle, Australia",
        ]
        # Remove primary from alternatives
        alt_locations = [loc for loc in alternative_locations if loc != primary_location]

        for title_idx, search_title in enumerate(job_titles):
            if check_control() == "stop":
                print("[!] Stop signal received. Shutting down...")
                break
            if self.successful_submits >= MAX_JOBS:
                print(f"\n[+] Reached {MAX_JOBS} applications! Stopping.")
                break

            print(f"\n{'=' * 50}")
            print(f"  SEARCHING: {search_title} ({title_idx + 1}/{len(job_titles)})")
            print(f"  Progress: {self.successful_submits}/{MAX_JOBS} long-form applications")
            print(f"{'=' * 50}\n")

            locations_to_try = [primary_location] + alt_locations

            for loc_idx, location in enumerate(locations_to_try):
                if check_control() == "stop": break
                if self.successful_submits >= MAX_JOBS: break

                print(f"\n[*] Searching in: {location}")
                search_url = build_search_url(search_title, location)
                print(f"    URL: {search_url}")

                self.driver.get(search_url)
                speed_sleep(3, "scan")
                throttle()

                total_jobs = self.get_total_job_count()
                print(f"[*] Found {total_jobs} jobs in {location}")

                if total_jobs == 0:
                    print(f"[*] No jobs found in {location}, moving on...")
                    continue

                # Process pages
                page = 1
                location_done = False

                while self.successful_submits < MAX_JOBS and not location_done:
                    if check_control() == "stop":
                        print("[!] Stop signal received.")
                        break

                    print(f"\n===== PAGE {page} =====")
                    cards = self.get_job_cards()

                    if not cards:
                        print("[!] No job cards found.")
                        break

                    for idx, card in enumerate(cards):
                        status = check_control()
                        if status == "stop": break
                        elif status == "pause":
                            print("[*] Bot paused. Waiting to resume...")
                            if not wait_while_paused(): break
                            print("[*] Bot resumed.")

                        if self.successful_submits >= MAX_JOBS: break

                        # Parse job title
                        try:
                            title = card.find_element(By.CSS_SELECTOR, "[data-automation='jobTitle']").text
                        except:
                            title = "Unknown"

                        if not title_matches(title):
                            continue

                        if is_title_blocked(title):
                            print(f"    [x] BLOCKED (title): {title}")
                            continue

                        try:
                            company = card.find_element(By.CSS_SELECTOR, "[data-automation='jobCompany']").text
                        except:
                            company = "Unknown"

                        if is_company_blocked(company):
                            print(f"    [x] BLOCKED (company): {company}")
                            continue

                        print(f"\n[*] Job {idx + 1}: {title} | {company}")
                        stealth_random_pause()

                        job_url = self.open_job(card)
                        if not job_url:
                            continue

                        speed_sleep(2, "scan")

                        # KEY DIFFERENCE: Only process EXTERNAL applications
                        external_btn = self.check_external_apply()
                        if external_btn:
                            print(f"    [*] EXTERNAL APPLICATION found — processing...")
                            description = self.get_description()
                            self.apply_external(external_btn, title, company, job_url, description)
                        elif self.check_quick_apply():
                            self.skipped_quick_apply += 1
                            print(f"    [-] Quick Apply job — SKIPPING (use short-form bot)")
                        else:
                            print(f"    [-] No apply button found — skipping")

                        # Close job tab and return to search
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                            stealth_random_scroll(self.driver)

                        job_cooldown()

                    if self.successful_submits >= MAX_JOBS: break

                    moved = self.go_to_next_page()
                    if not moved:
                        print(f"[*] Exhausted all pages in {location}.")
                        location_done = True
                        break
                    page += 1

        # Final summary
        duration_minutes = int((time.time() - run_start_time) / 60)
        print(f"\n{'=' * 60}")
        print(f"  LONG-FORM BOT COMPLETE")
        print(f"  Successfully submitted: {self.successful_submits} external applications")
        print(f"  Skipped Quick Apply: {self.skipped_quick_apply}")
        print(f"  Duration: {duration_minutes} minutes")
        print(f"{'=' * 60}")

        # WhatsApp summary
        try:
            from main import send_whatsapp_summary
            full_name = CONFIG.get("FULL_NAME", "User")
            send_whatsapp_summary(full_name, self.successful_submits,
                                  duration_minutes, self.applied_job_titles)
        except Exception:
            pass  # WhatsApp is optional


def main():
    reload_config()
    write_control(pause=False, stop=False)
    driver = init_browser()
    bot = LongFormBot(driver)
    try:
        bot.run()
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    main()

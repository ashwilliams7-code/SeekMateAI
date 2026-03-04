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
    import shutil

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
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Force correct Chrome binary path
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        chrome_options.binary_location = chrome_path

    # Use a PERSISTENT Chrome profile so SEEK login cookies survive between sessions.
    # Stored in AppData (not temp) so Windows doesn't clean it up.
    # The longform bot gets its own profile to avoid conflicts with the main bot.
    profile_dir = os.path.join(get_data_dir(), "chrome_profile_longform")

    # Only remove lock files (not the whole profile!) so cookies/login persist
    if os.path.exists(profile_dir):
        for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"]:
            lock_path = os.path.join(profile_dir, lock_file)
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
                    print(f"[*] Removed stale lock: {lock_file}")
            except:
                pass

    os.makedirs(profile_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    print(f"[INFO] Chrome profile: {profile_dir}")

    service = Service(ChromeDriverManager().install())
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        # Fallback: clear lock files more aggressively and retry (keep cookies!)
        print(f"[!] Chrome failed ({e}), clearing locks and retrying...")
        if os.path.exists(profile_dir):
            # Remove ALL lock-like files, but preserve cookies/login data
            for root, dirs, files in os.walk(profile_dir):
                for f in files:
                    if f.startswith("Singleton") or f == "lockfile":
                        try: os.remove(os.path.join(root, f))
                        except: pass
                break  # only top-level
        os.makedirs(profile_dir, exist_ok=True)
        chrome_options2 = Options()
        chrome_options2.add_argument("--start-maximized")
        chrome_options2.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options2.add_argument("--disable-extensions")
        chrome_options2.add_argument("--disable-notifications")
        chrome_options2.add_argument("--no-sandbox")
        chrome_options2.add_argument("--disable-dev-shm-usage")
        if os.path.exists(chrome_path):
            chrome_options2.binary_location = chrome_path
        chrome_options2.add_argument(f"--user-data-dir={profile_dir}")
        service2 = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service2, options=chrome_options2)

    if SCAN_SPEED >= 90: driver.implicitly_wait(0.1)
    elif SCAN_SPEED >= 50: driver.implicitly_wait(1)
    else: driver.implicitly_wait(3)

    return driver


# ============================================
# AI ENGINE — Claude Code (free), Claude API, or OpenAI GPT
# ============================================
ANTHROPIC_API_KEY = CONFIG.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
OPENAI_API_KEY = CONFIG.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
USE_CLAUDE_CODE = CONFIG.get("USE_CLAUDE_CODE", True)  # Default: use Claude Code (free)
CLAUDE_MODEL = "claude-sonnet-4-20250514"
OPENAI_MODEL = "gpt-4.1-mini"

# Determine which AI engine to use — Claude Code is preferred (zero cost)
if USE_CLAUDE_CODE:
    AI_ENGINE = "claude_code"
    print("[AI] Using Claude Code (zero API cost — file-based bridge)")
elif ANTHROPIC_API_KEY:
    AI_ENGINE = "claude_api"
    print(f"[AI] Using Claude API ({CLAUDE_MODEL})")
elif OPENAI_API_KEY:
    AI_ENGINE = "openai"
    print(f"[AI] Using OpenAI ({OPENAI_MODEL})")
else:
    AI_ENGINE = "claude_code"  # Default fallback to Claude Code
    print("[AI] No API keys — using Claude Code bridge")


# ============================================
# LONG-FORM BOT
# ============================================
class LongFormBot:
    def __init__(self, driver):
        self.driver = driver
        self.successful_submits = 0
        self.applied_job_titles = []
        self.skipped_quick_apply = 0

        # AI clients
        self.claude_client = None
        self.openai_client = None

        if AI_ENGINE == "claude_api":
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
            except Exception as e:
                print(f"[!] Failed to init Claude client: {e}")
        elif AI_ENGINE == "openai":
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

        # WebDriverWait timeout
        self.wait = WebDriverWait(driver, 10 if SCAN_SPEED < 50 else 5)

    def gpt(self, system_prompt, user_prompt):
        """Unified AI call — routes to Claude Code, Claude API, or OpenAI."""
        # Claude Code bridge (zero cost — Claude Code answers via file)
        if AI_ENGINE == "claude_code":
            try:
                from cc_ai_bridge import ask_claude_code
                answer = ask_claude_code(system_prompt, user_prompt, timeout=300)
                if answer:
                    return answer
                print("    [!] Claude Code did not respond — check if monitoring loop is running")
                return ""
            except ImportError:
                print("    [!] cc_ai_bridge.py not found — falling back to API")
            except Exception as e:
                print(f"    [!] Claude Code bridge error: {e}")

        # Claude API
        if self.claude_client:
            try:
                res = self.claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=800,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return res.content[0].text.strip()
            except Exception as e:
                print(f"    [!] CLAUDE API ERROR: {e}")
                if self.openai_client:
                    print("    [*] Falling back to OpenAI...")

        # OpenAI fallback
        if self.openai_client:
            try:
                res = self.openai_client.chat.completions.create(
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

        print("    [!] No AI engine available")
        return ""

    def ensure_logged_in(self):
        self.driver.get("https://www.seek.com.au/")
        time.sleep(5)
        sign_in = self.driver.find_elements(By.XPATH, "//a[contains(., 'Sign in')]")
        if sign_in:
            print("[!] Not logged in to SEEK. Please log in via the browser window...")
            print("[*] Waiting for login (checking every 10 seconds)...")
            # Poll until user logs in (no input() needed — works in subprocess mode)
            for attempt in range(60):  # Wait up to 10 minutes
                if check_control() == "stop":
                    print("[!] Stop signal received during login wait.")
                    return
                time.sleep(10)
                try:
                    self.driver.get("https://www.seek.com.au/")
                    time.sleep(3)
                    still_signed_out = self.driver.find_elements(By.XPATH, "//a[contains(., 'Sign in')]")
                    if not still_signed_out:
                        print("[*] Login detected! Continuing...")
                        return
                    print(f"    [*] Still waiting for login... (attempt {attempt + 1}/60)")
                except:
                    pass
            print("[!] Login timeout — proceeding anyway (may fail).")
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

    def wait_for_apply_button(self):
        """Wait for the Apply button to render on the job detail page.
        Uses explicit WebDriverWait (not speed-dependent) so the page has time to load."""
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-automation='job-detail-apply']"))
            )
            return True
        except:
            # Fallback: also try alternative selector
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Apply')]"))
                )
                return True
            except:
                return False

    def find_apply_link(self):
        """Find the Apply link/button on the job detail page.
        Returns (element, href, text) — text is used to distinguish Quick Apply vs External."""
        # SEEK uses <a data-automation="job-detail-apply"> for all apply buttons
        selectors = [
            "a[data-automation='job-detail-apply']",
            "a[data-automation='jobDetailApply']",
        ]
        for sel in selectors:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    href = els[0].get_attribute("href") or ""
                    text = els[0].text.strip()
                    return els[0], href, text
            except:
                continue

        # Fallback: look for links/buttons with Apply text
        for xpath in [
            "//a[contains(., 'Apply')]",
            "//button[contains(., 'Apply')]",
        ]:
            try:
                els = self.driver.find_elements(By.XPATH, xpath)
                if els:
                    href = els[0].get_attribute("href") or ""
                    text = els[0].text.strip()
                    return els[0], href, text
            except:
                continue

        return None, None, None

    def detect_apply_type_from_text(self, button_text):
        """Detect if the Apply button is Quick Apply or External based on its text.
        SEEK uses 'Quick apply' for internal forms and 'Apply' for external portals."""
        text = button_text.lower().replace('\u2060', '').strip()  # strip zero-width chars
        if "quick" in text:
            return "quick_apply"
        elif text in ("apply", "apply now", "apply on company site"):
            return "external"
        return "unknown"

    def click_apply_and_go_external(self, apply_element, job_url):
        """Click the external Apply link and wait for the external portal to load.
        Returns True if we landed on an external page, False otherwise."""
        original_handles = set(self.driver.window_handles)

        try:
            self.driver.execute_script("arguments[0].click();", apply_element)
            time.sleep(5)  # Fixed 5s wait for redirect — not speed-dependent

            # Check if new tab opened
            new_handles = set(self.driver.window_handles)
            if new_handles - original_handles:
                new_tab = list(new_handles - original_handles)[0]
                self.driver.switch_to.window(new_tab)
                time.sleep(3)  # Wait for external page to load

            current_url = self.driver.current_url
            print(f"    [*] After clicking Apply, landed on: {current_url[:100]}")

            if "seek.com.au" not in current_url:
                print(f"    [*] EXTERNAL PORTAL detected!")
                return True

            # Might be SEEK redirect page — wait a bit more
            if "/apply" in current_url:
                time.sleep(4)
                current_url = self.driver.current_url
                if "seek.com.au" not in current_url:
                    print(f"    [*] EXTERNAL PORTAL detected after redirect!")
                    return True

            print(f"    [-] Did not land on external portal")
            return False

        except Exception as e:
            print(f"    [!] Error navigating to external portal: {e}")
            return False

    def apply_external(self, job_title, company, job_url, description):
        """Run the LongFormEngine on the current external page."""
        try:
            from longform import LongFormEngine
            lf = LongFormEngine(self.driver, CONFIG, self.gpt)

            # The browser is already on the external ATS portal — engine handles from here
            result = lf.run(None, job_title, company, job_url, description)

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

                        # Explicit wait for Apply button to render (not speed-dependent)
                        self.wait_for_apply_button()

                        # Get job description before checking Apply type
                        description = self.get_description()

                        # Find the Apply link on the job page
                        apply_el, apply_href, apply_text = self.find_apply_link()
                        if not apply_el:
                            print(f"    [-] No apply button found — skipping")
                            if len(self.driver.window_handles) > 1:
                                self.driver.close()
                                self.driver.switch_to.window(self.driver.window_handles[0])
                            job_cooldown()
                            continue

                        print(f"    [*] Apply button text: '{apply_text}' | href: {apply_href[:80] if apply_href else 'none'}")

                        # Detect Quick Apply vs External from button text (no click needed)
                        apply_type = self.detect_apply_type_from_text(apply_text)

                        if apply_type == "quick_apply":
                            self.skipped_quick_apply += 1
                            print(f"    [-] Quick Apply job — SKIPPING (use short-form bot)")
                        elif apply_type == "external":
                            print(f"    [*] EXTERNAL APPLICATION — clicking through to portal...")
                            if self.click_apply_and_go_external(apply_el, job_url):
                                self.apply_external(title, company, job_url, description)
                            else:
                                print(f"    [-] Failed to reach external portal — skipping")
                        else:
                            # Unknown text — try clicking to detect
                            print(f"    [*] Unknown apply type '{apply_text}' — clicking to detect...")
                            if self.click_apply_and_go_external(apply_el, job_url):
                                self.apply_external(title, company, job_url, description)
                            else:
                                self.skipped_quick_apply += 1
                                print(f"    [-] Landed on SEEK form — SKIPPING")

                        # Close all extra tabs and return to search results
                        while len(self.driver.window_handles) > 1:
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

import builtins
import os
import json
import time
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from openai import OpenAI
import openpyxl
from openpyxl import Workbook
from datetime import datetime

# ============================================
# SMART CATEGORY + STRICT TITLE MATCHING
# ============================================

def detect_category(titles):
    """Detects which preset category user is targeting."""
    titles_norm = [t.lower().strip() for t in titles]

    # GOVERNMENT / EXEC / EL / SES (APS REMOVED)
    gov_keywords = [
        "el1", "el 1", "el2", "el 2",
        "ses", "ses1", "ses 1", "ses2", "ses 2",
        "policy", "governance", "compliance", "public sector",
        "principal", "advisor"
    ]
    if any(k in t for t in titles_norm for k in gov_keywords):
        return "gov"

    # DIRECTOR / LEADERSHIP
    if any(t in titles_norm for t in [
        "director", "program director", "operations director",
        "project director", "head of", "general manager",
        "executive", "principal", "portfolio manager", "gm"
    ]):
        return "leadership"

    # PROJECT / PROGRAM
    if any(t in titles_norm for t in [
        "project manager", "program manager", "agile",
        "scrum master", "project lead", "delivery manager"
    ]):
        return "project"

    # SALES / BDM
    if any(t in titles_norm for t in [
        "bdm", "business development", "sales", "account manager",
        "relationship manager", "client", "growth", "partnership"
    ]):
        return "sales"

    # SOCIAL / RESEARCH
    if any(t in titles_norm for t in [
        "research", "policy", "community", "anthropology",
        "program officer", "stakeholder engagement"
    ]):
        return "social"

    # ADMIN
    if any(t in titles_norm for t in [
        "admin", "coordinator", "ea", "executive assistant"
    ]):
        return "admin"

    # IT
    if any(t in titles_norm for t in [
        "it", "developer", "engineer", "software", "cyber",
        "cloud", "data"
    ]):
        return "it"

    return "generic"


def title_matches(job_title):
    """Strict matching engine using category rules."""
    job = job_title.lower().strip()
    titles = CONFIG.get("JOB_TITLES", [])
    category = detect_category(titles)

    # ------------------------------
    # RULESETS PER CATEGORY
    # ------------------------------

    # GOV — APS REMOVED, EL/SES/Director only
    if category == "gov":
        allowed = [
            "el1", "el 1",
            "el2", "el 2",
            "ses", "ses1", "ses 1", "ses2", "ses 2",
            "director",
            "policy",
            "principal",
            "executive",
            "governance",
            "advisor",
            "project manager",
            "program manager",
            "public sector",
            "engagement",
            "analyst",
            "coordinator"
        ]
        return any(a in job for a in allowed)

    if category == "leadership":
        allowed = [
            "director", "head", "general manager", "gm",
            "executive", "principal", "lead",
            "program director", "project director"
        ]
        return any(a in job for a in allowed)

    if category == "project":
        allowed = [
            "project manager", "program manager", "delivery manager",
            "scrum master", "agile", "project lead"
        ]
        return any(a in job for a in allowed)

    if category == "sales":
        allowed = [
            "bdm", "business development", "sales",
            "account manager", "partnership",
            "growth", "client", "relationship manager",
            "sales manager", "solutions"
        ]
        return any(a in job for a in allowed)

    if category == "social":
        allowed = [
            "research", "policy", "community",
            "program officer", "stakeholder",
            "case manager", "social"
        ]
        return any(a in job for a in allowed)

    if category == "admin":
        allowed = [
            "admin", "coordinator", "ea", "executive assistant",
            "office manager", "project coordinator"
        ]
        return any(a in job for a in allowed)

    if category == "it":
        allowed = [
            "developer", "engineer", "software",
            "it", "cloud", "cyber", "product manager"
        ]
        return any(a in job for a in allowed)

    return True


# ============================================
# RESOURCE PATH FIX FOR PYINSTALLER EXE
# ============================================
def resource_path(relative_path):
    """ Return absolute path for dev mode or PyInstaller EXE """
    try:
        base_path = sys._MEIPASS  # folder where EXE extracts files
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_dir():
    """Get a consistent, user-writable data directory for logs and data files"""
    if sys.platform == "darwin":  # macOS
        data_dir = os.path.expanduser("~/Library/Application Support/SeekMateAI")
    elif sys.platform == "win32":  # Windows
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SeekMateAI")
    else:  # Linux
        data_dir = os.path.expanduser("~/.seekmateai")
    
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# ============================================
# LOGGING (WORKS IN EXE)
# ============================================
LOG_FILE = os.path.join(get_data_dir(), "log.txt")
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
# CONFIG LOAD (FIXED FOR EXE)
# ============================================
CONFIG_FILE = resource_path("config.json")
CONTROL_FILE = resource_path("control.json")

if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(
        "config.json not found. Run config_gui.exe first to create it."
    )

def check_control():
    """Check control.json for pause/stop signals. Returns: 'run', 'pause', or 'stop'"""
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

def wait_while_paused():
    """Block execution while paused, return False if stopped"""
    while True:
        status = check_control()
        if status == "stop":
            print("[!] Stop signal received.")
            return False
        elif status == "pause":
            time.sleep(0.5)  # Check every 500ms while paused
            continue
        else:
            return True  # Continue running

with open(CONFIG_FILE, "r") as f:
    CONFIG = json.load(f)


# Basic fields
SEEK_EMAIL = CONFIG.get("SEEK_EMAIL", "")
JOB_TITLE = CONFIG.get("JOB_TITLE", "")
CV_PATH = CONFIG.get("CV_PATH", "")
MAX_JOBS = 100
EXPECTED_SALARY = CONFIG.get("EXPECTED_SALARY", "100000")

# Read LOCATION from config
LOCATION = CONFIG.get("LOCATION", "Brisbane, Australia")

# ============================================
# SPEED SLIDER SYSTEM (1-100 scale)
# ============================================
SCAN_SPEED = CONFIG.get("SCAN_SPEED", 50)
APPLY_SPEED = CONFIG.get("APPLY_SPEED", 50)
COOLDOWN_DELAY = CONFIG.get("COOLDOWN_DELAY", 5)
STEALTH_MODE = CONFIG.get("STEALTH_MODE", False)

# Print speed settings on startup
stealth_status = "🥷 ENABLED" if STEALTH_MODE else "OFF"
print(f"[SPEED] Scan: {SCAN_SPEED}% | Apply: {APPLY_SPEED}% | Cooldown: {COOLDOWN_DELAY}s | Stealth: {stealth_status}")

def get_scan_multiplier():
    """Convert 1-100 slider to delay multiplier (100=fastest, 1=slowest)"""
    if SCAN_SPEED >= 95:
        return 0.02  # Near instant
    elif SCAN_SPEED >= 75:
        return 0.15  # Fast
    elif SCAN_SPEED >= 50:
        return 0.4   # Normal
    elif SCAN_SPEED >= 25:
        return 0.8   # Slow
    else:
        return 1.5   # Very slow

def get_apply_multiplier():
    """Convert 1-100 slider to delay multiplier for form filling"""
    if APPLY_SPEED >= 95:
        return 0.02
    elif APPLY_SPEED >= 75:
        return 0.15
    elif APPLY_SPEED >= 50:
        return 0.4
    elif APPLY_SPEED >= 25:
        return 0.8
    else:
        return 1.5

def throttle():
    """Extra delay layer for page scanning operations."""
    if SCAN_SPEED >= 90:
        return  # Skip entirely for fast modes
    if SCAN_SPEED >= 75:
        time.sleep(0.1)
    elif SCAN_SPEED >= 50:
        time.sleep(0.3)
    else:
        time.sleep(0.6)

def speed_sleep(base, mode="scan"):
    """
    Scaled dynamic sleep based on slider settings.
    mode: 'scan' for page loading, 'apply' for form filling
    """
    if mode == "scan":
        multiplier = get_scan_multiplier()
    else:
        multiplier = get_apply_multiplier()
    
    actual_delay = base * multiplier
    
    # Enforce minimum delays for stability (but much lower for insane mode)
    if mode == "scan":
        if SCAN_SPEED >= 95:
            actual_delay = max(actual_delay, 0.05)  # 50ms minimum
        else:
            actual_delay = max(actual_delay, 0.1)   # 100ms minimum
    else:
        if APPLY_SPEED >= 95:
            actual_delay = max(actual_delay, 0.02)  # 20ms minimum for form filling
        else:
            actual_delay = max(actual_delay, 0.05)
    
    time.sleep(actual_delay)

def job_cooldown():
    """Wait between job applications (from slider)."""
    if COOLDOWN_DELAY > 0:
        print(f"    [*] Cooldown: waiting {COOLDOWN_DELAY}s before next job...")
        time.sleep(COOLDOWN_DELAY)


# ============================================
# STEALTH MODE - HUMAN-LIKE BEHAVIOR
# ============================================
import random

def stealth_random_scroll(driver):
    """Perform random scrolling like a human would"""
    if not STEALTH_MODE:
        return
    
    try:
        # Random scroll direction and amount
        scroll_actions = [
            ("down", random.randint(100, 400)),
            ("up", random.randint(50, 200)),
            ("down", random.randint(200, 500)),
        ]
        
        for direction, amount in random.sample(scroll_actions, random.randint(1, 2)):
            if direction == "down":
                driver.execute_script(f"window.scrollBy(0, {amount});")
            else:
                driver.execute_script(f"window.scrollBy(0, -{amount});")
            time.sleep(random.uniform(0.3, 0.8))
    except:
        pass

def stealth_random_pause():
    """Add random pauses like a human reading"""
    if not STEALTH_MODE:
        return
    
    # Random pause between 0.5 and 2.5 seconds
    pause = random.uniform(0.5, 2.5)
    time.sleep(pause)

def stealth_mouse_wiggle(driver):
    """Simulate mouse movement by moving to random elements"""
    if not STEALTH_MODE:
        return
    
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        
        # Find some random elements on the page
        elements = driver.find_elements(By.TAG_NAME, "div")[:20]
        if elements:
            # Move to a random element
            random_element = random.choice(elements)
            actions = ActionChains(driver)
            actions.move_to_element(random_element).perform()
            time.sleep(random.uniform(0.1, 0.3))
    except:
        pass

def stealth_reading_delay():
    """Simulate reading time on job description"""
    if not STEALTH_MODE:
        return
    
    # Simulate reading: 2-6 seconds
    read_time = random.uniform(2, 6)
    time.sleep(read_time)

def stealth_typing_delay():
    """Add small delays between typing actions"""
    if not STEALTH_MODE:
        return
    
    time.sleep(random.uniform(0.05, 0.15))

def stealth_before_click():
    """Pause briefly before clicking (like a human would)"""
    if not STEALTH_MODE:
        return
    
    time.sleep(random.uniform(0.2, 0.6))

def stealth_page_behavior(driver):
    """Combined human-like behavior when viewing a page"""
    if not STEALTH_MODE:
        return
    
    try:
        # Random chance to do each action
        if random.random() > 0.5:
            stealth_random_scroll(driver)
        
        if random.random() > 0.6:
            stealth_mouse_wiggle(driver)
        
        stealth_reading_delay()
    except:
        pass


# ---------- STRICT TITLE FILTER ----------
def title_matches(title: str) -> bool:
    allowed = [t.lower().strip() for t in CONFIG.get("JOB_TITLES", [])]
    title_clean = title.lower().strip()

    # strict contains matching
    return any(a in title_clean for a in allowed)


# ---------- BLOCKLIST FILTERS ----------
BLOCKED_COMPANIES = [c.lower().strip() for c in CONFIG.get("BLOCKED_COMPANIES", [])]
BLOCKED_TITLES = [t.lower().strip() for t in CONFIG.get("BLOCKED_TITLES", [])]

def is_company_blocked(company: str) -> bool:
    """Check if a company is in the blocklist"""
    if not BLOCKED_COMPANIES:
        return False
    company_clean = company.lower().strip()
    return any(blocked in company_clean for blocked in BLOCKED_COMPANIES)

def is_title_blocked(title: str) -> bool:
    """Check if a job title contains blocked keywords"""
    if not BLOCKED_TITLES:
        return False
    title_clean = title.lower().strip()
    return any(blocked in title_clean for blocked in BLOCKED_TITLES)

# Print blocklist info on startup
if BLOCKED_COMPANIES:
    print(f"[BLOCKLIST] Companies: {', '.join(BLOCKED_COMPANIES)}")
if BLOCKED_TITLES:
    print(f"[BLOCKLIST] Titles: {', '.join(BLOCKED_TITLES)}")


# OpenAI
OPENAI_API_KEY = CONFIG.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
OPENAI_MODEL = "gpt-4.1-mini"


# ============================================
# BUILD SEEK URL (NOW USES LOCATION)
# ============================================
def build_search_url(job_title, location):
    # Strip ", Australia" because SEEK doesn't use it in URL searches
    safe_location = location.replace(", Australia", "").strip()

    job_query = job_title.replace(" ", "%20")
    loc_query = safe_location.replace(" ", "%20")

    return f"https://www.seek.com.au/jobs?keywords={job_query}&where={loc_query}&sortmode=ListedDate"



SEARCH_URL = build_search_url(JOB_TITLE, LOCATION)



# ------------------ FIXED BROWSER LAUNCHER ------------------
def init_browser():
    import tempfile
    
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")

    # Use temp directory for Chrome profile (works on macOS bundled apps)
    # This avoids permission issues on macOS sandboxed environments
    profile_dir = os.path.join(tempfile.gettempdir(), "seekmate_chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Set implicit wait based on SCAN_SPEED slider
    if SCAN_SPEED >= 90:
        driver.implicitly_wait(0.1)  # Near instant for insane/fast
    elif SCAN_SPEED >= 50:
        driver.implicitly_wait(1)    # Quick for normal
    else:
        driver.implicitly_wait(3)    # Patient for slow
    
    return driver



class SeekBot:
    def __init__(self, driver):
        self.successful_submits = 0
        self.driver = driver
        
        # WebDriverWait timeout based on speed
        if SCAN_SPEED >= 90:
            wait_timeout = 3   # Fast timeout for insane mode
        elif SCAN_SPEED >= 50:
            wait_timeout = 8   # Normal timeout
        else:
            wait_timeout = 15  # Patient timeout for slow mode
        
        self.wait = WebDriverWait(driver, wait_timeout)
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    # ---------- GPT ----------
    def log_job(self, title, company, url):
        file_path = "job_log.xlsx"

        if not os.path.exists(file_path):
            wb = Workbook()
            ws = wb.active
            ws.append(["Timestamp", "Job Title", "Company", "URL"])
            wb.save(file_path)

        wb = openpyxl.load_workbook(file_path)
        ws = wb.active

        ws.append([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            title,
            company,
            url
        ])

        wb.save(file_path)
        print(f"    [+] Logged to Excel → {title} @ {company}")
    def gpt(self, system_prompt: str, user_prompt: str) -> str:
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
            print("GPT ERROR:", e)
            return ""

    # ---------- LOGIN ----------
    def ensure_logged_in(self):
        self.driver.get("https://www.seek.com.au/")
        speed_sleep(5, "scan")
        throttle()

        sign_in = self.driver.find_elements(By.XPATH, "//a[contains(., 'Sign in')]")
        if sign_in:
            print("[!] Not logged in. Log in manually...")
            input("Press ENTER after logging in...")
        else:
            print("[*] Already logged in.")

    # ---------- SEARCH ----------
    def open_search(self):
        print(f"[*] Opening search for: {JOB_TITLE}")
        print(f"    URL: {SEARCH_URL}")
        self.driver.get(SEARCH_URL)   # <- This is now auto-generated above
        speed_sleep(3, "scan")
        throttle()

    def get_job_cards(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "article[data-automation='normalJob']")
        if not cards:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "article")
        print(f"[*] Found {len(cards)} jobs on this page.")
        return cards

    # ---------- OPEN JOB ----------
    def open_job(self, card) -> str:
        """Opens job in new tab. Returns URL if successful, empty string if failed."""
        throttle()
        stealth_before_click()  # Human-like pause before clicking
        try:
            link = card.find_element(By.CSS_SELECTOR, "a[data-automation='jobTitle']")
            href = link.get_attribute("href")
            self.driver.execute_script("window.open(arguments[0], '_blank');", href)
            speed_sleep(2, "scan")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # Stealth: Behave like human viewing the job page
            stealth_page_behavior(self.driver)
            
            print(f"    [+] Opened: {href}")
            return href
        except Exception:
            print("    [-] Failed to open job tab.")
            return ""

    # ---------- DESCRIPTION ----------
    def get_description(self) -> str:
        selectors = [
            "[data-automation='jobDescription']",
            "div[data-automation*='jobAdDetails']",
            "div[data-automation*='job']",
        ]
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                txt = el.text.strip()
                if len(txt) > 50:
                    return txt
            except:
                continue
        return ""

    # ---------- COVER LETTER (NEW LONG VERSION + OVERWRITE PROTECTION) ----------
    def fill_cover_letter(self, job_title, company, desc):
        full_name = CONFIG.get("FULL_NAME", "Applicant")
        location = CONFIG.get("LOCATION", "Australia")
        background_bio = CONFIG.get("BACKGROUND_BIO", "")

        letter = self.gpt(
            "You are a professional cover letter writer who creates highly tailored, job-specific cover letters. You carefully analyze job descriptions and match candidate experience to specific role requirements.",
            f"""
        Write a highly targeted cover letter for **{full_name}** applying for:

        ROLE: {job_title}
        COMPANY: {company}

        CANDIDATE:
        - Name: {full_name}
        - Location: {location}
        - Background: {background_bio}

        ═══════════════════════════════════════════════════════
        CRITICAL: JOB-SPECIFIC REQUIREMENTS
        ═══════════════════════════════════════════════════════
        
        STEP 1 - ANALYZE THE JOB DESCRIPTION BELOW AND IDENTIFY:
        • The TOP 3-4 key responsibilities mentioned
        • The specific skills or qualifications required
        • Any industry-specific terminology used
        • The company's apparent culture or values
        
        STEP 2 - WRITE THE COVER LETTER THAT:
        • Directly addresses EACH key responsibility from the job posting
        • Uses the SAME terminology and keywords from the job description
        • Provides specific examples of how {full_name} has done similar work
        • References the actual duties listed (e.g., "Your requirement for X aligns with my experience in...")
        • Shows understanding of what THIS specific role involves
        
        ═══════════════════════════════════════════════════════
        
        STRUCTURE:
        Paragraph 1: Hook + why THIS specific role at THIS company
        Paragraph 2: Address the FIRST major responsibility from job description with concrete example
        Paragraph 3: Address the SECOND major responsibility with evidence
        Paragraph 4: Address additional key requirements (skills, qualifications, soft skills)
        Paragraph 5: Strong closing with call to action

        FORMAT RULES:
        • First line MUST be: "Dear {company} Hiring Team,"
        • DO NOT include: email, phone, LinkedIn, dates, addresses, or any placeholders
        • End with signature: {full_name}
        • Length: 400-550 words
        
        STYLE:
        • Confident and professional, not generic
        • Use action verbs and quantifiable achievements where possible
        • Mirror the tone of the job posting
        • NO clichés like "I am excited to apply" or "I believe I would be a great fit"

        ═══════════════════════════════════════════════════════
        JOB DESCRIPTION TO ANALYZE:
        ═══════════════════════════════════════════════════════
        {desc}
        """
        )

        if not letter:
            print("    [-] GPT failed.")
            return

        textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
        for ta in textareas:
            try:
                name_attr = (ta.get_attribute("name") or "").lower()
                id_attr = (ta.get_attribute("id") or "").lower()
                if "cover" not in name_attr and "cover" not in id_attr:
                    continue

                self.driver.execute_script("arguments[0].scrollIntoView(true);", ta)
                speed_sleep(0.5, "apply")

                # 1) Double clear
                ta.clear()
                speed_sleep(0.2, "apply")
                ta.clear()
                speed_sleep(0.2, "apply")

                # 2) Inject via JS
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];", ta, letter
                )

                # 3) Fire typing events
                self.driver.execute_script("""
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, ta)

                speed_sleep(0.4, "apply")

                # 4) Force SEEK to commit
                ta.send_keys(" ")
                ta.send_keys("\b")

                print("    [+] Cover letter added (overwrite protection).")
                return
            except:
                pass

    # ---------- SCREENING TEXT QUESTIONS (MULTI-USER VERSION) ----------
    def answer_questions(self, job_title, company, desc):
        full_name = CONFIG.get("FULL_NAME", "the candidate")
        location = CONFIG.get("LOCATION", "Australia")
        background_bio = CONFIG.get("BACKGROUND_BIO", "")

        textareas = self.driver.find_elements(By.TAG_NAME, "textarea")

        for ta in textareas:
            try:
                # ----- SKIP ANYTHING THAT LOOKS LIKE A COVER LETTER -----
                placeholder = (ta.get_attribute("placeholder") or "").lower()
                aria = (ta.get_attribute("aria-label") or "").lower()
                name_attr = (ta.get_attribute("name") or "").lower()
                id_attr = (ta.get_attribute("id") or "").lower()

                if "cover" in placeholder or "cover" in aria or "cover" in name_attr or "cover" in id_attr:
                    continue

                # Skip large text fields
                height = ta.size.get("height", 0)
                if height > 200:
                    continue

                # Get the question label
                label_text = ""
                try:
                    label = ta.find_element(By.XPATH, "./preceding::label[1]")
                    label_text = label.text.strip()
                except:
                    continue

                if len(label_text) < 5:
                    continue

                print("    [*] Screening Q:", label_text)

                # ---------- GPT ANSWER ----------
                answer = self.gpt(
                    "You write concise, senior-level answers for job screening questions.",
                    f"""
You are answering as **{full_name}**, a senior professional based in {location}.

BACKGROUND BIO:
{background_bio}

JOB APPLYING FOR:
- {job_title} at {company}

RULES:
• 4–7 sentences
• Direct, confident, senior tone
• If the question is about commute, onsite work, availability, local work rights, or proximity → mention being based in {location}
• Otherwise DO NOT mention the location
• No dates, emails, phone numbers, or irrelevant details
• No clichés

QUESTION:
"{label_text}"
                    """
                )

                if not answer:
                    continue

                # Fill the textarea safely
                self.driver.execute_script("arguments[0].scrollIntoView(true);", ta)
                speed_sleep(0.5, "apply")
                ta.clear()
                ta.send_keys(answer)
                speed_sleep(0.3, "apply")

            except Exception as e:
                print("    [!] Error answering question:", e)
                continue

    # ---------- RADIO BUTTONS (YES-FIRST) ----------
    def answer_radio_buttons(self):
        try:
            radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")

            # Group radios by 'name'
            groups = {}
            for r in radios:
                name = r.get_attribute("name")
                if name:
                    groups.setdefault(name, []).append(r)

            for name, group in groups.items():
                try:
                    # Try to get the question text above the radio buttons
                    question_text = ""
                    try:
                        q = group[0].find_element(By.XPATH, "./ancestor::fieldset//legend")
                        question_text = q.text.strip().lower()
                    except:
                        try:
                            q = group[0].find_element(By.XPATH, "./preceding::*[self::label or self::h3][1]")
                            question_text = q.text.strip().lower()
                        except:
                            question_text = ""

                    # Extract option labels
                    options = []
                    for r in group:
                        try:
                            lbl = r.find_element(By.XPATH, "./following::label[1]").text.strip().lower()
                        except:
                            lbl = ""
                        options.append((r, lbl))

                    # --- RULE 1: YES/NO QUESTIONS (do you / have you / were you / worked / responsible) ---
                    if any(phrase in question_text for phrase in [
                        "do you",
                        "have you",
                        "were you",
                        "worked",
                        "responsible",
                        "can you",
                        "did you",
                        "have",
                    ]):
                        for r, lbl in options:
                            if "yes" in lbl:
                                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                                self.driver.execute_script("arguments[0].click();", r)
                                speed_sleep(0.2, "apply")
                                break
                        continue

                    # --- RULE 2: EXPERIENCE QUESTIONS ---
                    if "experience" in question_text:
                        r, lbl = options[-1]  # choose highest experience
                        self.driver.execute_script("arguments[0].click();", r)
                        speed_sleep(0.2, "apply")
                        continue

                    # --- RULE 3: FAMILIARITY / KNOWLEDGE ---
                    if any(x in question_text for x in ["familiar", "knowledge", "domain", "government"]):
                        r, lbl = options[-1]
                        self.driver.execute_script("arguments[0].click();", r)
                        speed_sleep(0.2, "apply")
                        continue

                    # --- RULE 4: POLICE CHECK ---
                    if "police" in question_text or "check" in question_text:
                        for r, lbl in options:
                            if "yes" in lbl:
                                self.driver.execute_script("arguments[0].click();", r)
                                speed_sleep(0.2, "apply")
                                break
                        continue

                    # --- RULE 5: RELOCATION ---
                    if "relocat" in question_text or "move" in question_text:
                        for r, lbl in options:
                            if "already" in lbl or "yes" in lbl:
                                self.driver.execute_script("arguments[0].click();", r)
                                speed_sleep(0.2, "apply")
                                break
                        continue

                    # --- RULE 6: WORK ELIGIBILITY / CITIZENSHIP ---
                    if any(phrase in question_text for phrase in [
                        "work eligibility", "eligibility", "right to work", 
                        "work rights", "visa", "citizen", "residency",
                        "legally", "authorised", "authorized"
                    ]):
                        selected = False
                        # Prioritize citizen/permanent resident options
                        for r, lbl in options:
                            if any(keyword in lbl for keyword in [
                                "australian", "citizen", "permanent resident", 
                                "nz citizen", "pr", "unlimited"
                            ]):
                                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                                self.driver.execute_script("arguments[0].click();", r)
                                print(f"    [+] Work eligibility: {lbl}")
                                speed_sleep(0.2, "apply")
                                selected = True
                                break
                        if selected:
                            continue
                        # If no citizen option found, pick first non-visa option
                        for r, lbl in options:
                            if "visa" not in lbl and "sponsor" not in lbl:
                                self.driver.execute_script("arguments[0].click();", r)
                                speed_sleep(0.2, "apply")
                                selected = True
                                break
                        if selected:
                            continue

                    # --- RULE 7: DRIVER'S LICENSE ---
                    if "driver" in question_text or "licence" in question_text or "license" in question_text:
                        for r, lbl in options:
                            if "yes" in lbl:
                                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                                self.driver.execute_script("arguments[0].click();", r)
                                print("    [+] Driver's license: Yes")
                                speed_sleep(0.2, "apply")
                                break
                        continue

                    # --- RULE 8: LOCATION/BASED QUESTIONS ---
                    if "based" in question_text or "located" in question_text or "travel" in question_text:
                        for r, lbl in options:
                            if "yes" in lbl:
                                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                                self.driver.execute_script("arguments[0].click();", r)
                                speed_sleep(0.2, "apply")
                                break
                        continue

                    # --- DEFAULT RULE (avoid 'no', 'none', 'no experience', 'visa', 'sponsor') ---
                    for r, lbl in options:
                        # Skip negative and visa-related options
                        if any(skip in lbl for skip in ["no", "none", "visa", "sponsor", "require"]):
                            continue
                        self.driver.execute_script("arguments[0].click();", r)
                        speed_sleep(0.2, "apply")
                        break

                except Exception as e:
                    print("    [!] Radio group error:", e)
                    continue

        except Exception as e:
            print("Radio handler error:", e)

    # ---------- CHECKBOXES (Tick ALL except "None of these") ----------
    def answer_checkboxes(self):
        try:
            labels = self.driver.find_elements(By.XPATH, "//label")
            none_labels = [lbl for lbl in labels if "none of these" in lbl.text.strip().lower()]

            for lbl in none_labels:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", lbl)
                    self.driver.execute_script("arguments[0].click();", lbl)
                    speed_sleep(0.2, "apply")
                except:
                    pass

            boxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            for c in boxes:
                try:
                    label = c.get_attribute("aria-label") or ""
                    if "none of these" in label.lower():
                        continue

                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", c)
                    self.driver.execute_script("arguments[0].click();", c)
                    speed_sleep(0.2, "apply")
                except:
                    continue

        except Exception as e:
            print("Checkbox handler error:", e)

    # ---------- DROPDOWNS (Choose MOST senior option + Citizenship + Salary) ----------
    def answer_dropdowns(self):
        try:
            selects = self.driver.find_elements(By.TAG_NAME, "select")

            for s in selects:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", s)
                    speed_sleep(0.3, "apply")

                    options = s.find_elements(By.TAG_NAME, "option")
                    if len(options) < 2:
                        continue

                    # Get the label for this dropdown
                    label_text = ""
                    try:
                        label = s.find_element(By.XPATH, "./preceding::label[1]")
                        label_text = label.text.strip().lower()
                    except:
                        pass

                    # ---------- CITIZENSHIP PATCH ----------
                    if "right to work" in label_text or "best describes your right" in label_text:
                        for opt in options:
                            if "australian citizen" in opt.text.lower():
                                opt.click()
                                print("    [+] Selected: Australian citizen")
                                break
                        continue

                    # ---------- SALARY EXPECTATIONS ----------
                    if any(word in label_text for word in ["salary", "pay", "remuneration", "expectation", "compensation"]):
                        # Find the option closest to our expected salary
                        target_salary = EXPECTED_SALARY
                        if isinstance(target_salary, str):
                            target_salary = int(target_salary.replace(",", "").replace("$", "").replace("k", "000"))
                        
                        best_option = None
                        best_diff = float('inf')
                        
                        for opt in options:
                            opt_text = opt.text.strip().lower()
                            # Skip placeholder options
                            if "select" in opt_text or "please" in opt_text or opt_text == "":
                                continue
                            
                            # Try to extract numbers from the option
                            import re
                            numbers = re.findall(r'\d+', opt_text.replace(",", ""))
                            if numbers:
                                # Handle "k" suffix (e.g., "100k" = 100000)
                                if "k" in opt_text:
                                    opt_salary = int(numbers[0]) * 1000
                                else:
                                    opt_salary = int(numbers[0])
                                    # If number is small, assume it's in thousands
                                    if opt_salary < 1000:
                                        opt_salary *= 1000
                                
                                diff = abs(opt_salary - target_salary)
                                if diff < best_diff:
                                    best_diff = diff
                                    best_option = opt
                        
                        if best_option:
                            best_option.click()
                            print(f"    [+] Salary selected: {best_option.text.strip()}")
                            continue
                        else:
                            # If no numeric option found, pick the highest one
                            options[-1].click()
                            print(f"    [+] Salary (fallback): {options[-1].text.strip()}")
                            continue

                    # ---------- EXISTING SENIOR SELECTION LOGIC ----------
                    selected = False
                    keywords = ["more", "5", "5+", "senior"]

                    for opt in options:
                        opt_label = opt.text.strip().lower()
                        if any(k in opt_label for k in keywords):
                            opt.click()
                            selected = True
                            break

                    if not selected:
                        options[-1].click()

                    speed_sleep(0.2, "apply")

                except:
                    continue

        except Exception as e:
            print("Dropdown handler error:", e)

    # ---------- SALARY INPUT FIELDS ----------
    def answer_salary_fields(self):
        """Fill in salary expectation input fields"""
        try:
            # Find all number and text inputs
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='number'], input[type='text']")
            
            for inp in inputs:
                try:
                    # Check if this is a salary field
                    label_text = ""
                    placeholder = (inp.get_attribute("placeholder") or "").lower()
                    name_attr = (inp.get_attribute("name") or "").lower()
                    aria_label = (inp.get_attribute("aria-label") or "").lower()
                    
                    # Try to get the label
                    try:
                        label = inp.find_element(By.XPATH, "./preceding::label[1]")
                        label_text = label.text.strip().lower()
                    except:
                        pass
                    
                    # Check if any identifier suggests this is a salary field
                    all_text = f"{label_text} {placeholder} {name_attr} {aria_label}"
                    
                    if any(word in all_text for word in ["salary", "pay", "remuneration", "expectation", "compensation", "rate"]):
                        # Skip if already filled
                        current_value = inp.get_attribute("value")
                        if current_value and len(current_value) > 0:
                            continue
                        
                        # Get our expected salary
                        target_salary = EXPECTED_SALARY
                        if isinstance(target_salary, str):
                            target_salary = target_salary.replace(",", "").replace("$", "").replace("k", "000")
                        
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
                        speed_sleep(0.2, "apply")
                        
                        inp.clear()
                        inp.send_keys(str(target_salary))
                        speed_sleep(0.2, "apply")
                        
                        print(f"    [+] Salary entered: ${target_salary}")
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Salary field handler error: {e}")

    # ---------- GPT SMART FALLBACK FOR VALIDATION ERRORS ----------
    def detect_and_fix_errors(self, job_title, company, desc):
        """
        Detect validation errors on the page and use GPT to answer unanswered questions.
        Returns True if errors were found and fixed, False otherwise.
        """
        try:
            # Look for error indicators
            error_elements = self.driver.find_elements(By.XPATH, 
                "//*[contains(text(), 'Required field') or contains(text(), 'Please make a selection') or contains(text(), 'Please select') or contains(@class, 'error')]"
            )
            
            if not error_elements:
                return False
            
            print("    [!] Validation errors detected. Using GPT to answer...")
            
            # Collect all unanswered questions
            unanswered = []
            
            # Find empty textareas with labels
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas:
                try:
                    if ta.get_attribute("value") or ta.text:
                        continue  # Already has content
                    
                    # Get the question label
                    label_text = ""
                    try:
                        label = ta.find_element(By.XPATH, "./preceding::*[self::label or self::span or self::div[contains(@class,'label')]][1]")
                        label_text = label.text.strip()
                    except:
                        try:
                            parent = ta.find_element(By.XPATH, "./ancestor::div[1]//label")
                            label_text = parent.text.strip()
                        except:
                            pass
                    
                    if label_text and len(label_text) > 5:
                        unanswered.append({"type": "text", "question": label_text, "element": ta})
                except:
                    continue
            
            # Find unselected radio button groups
            radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            groups = {}
            for r in radios:
                name = r.get_attribute("name")
                if name:
                    groups.setdefault(name, []).append(r)
            
            for name, group in groups.items():
                try:
                    # Check if any in the group is selected
                    any_selected = any(r.get_attribute("checked") for r in group)
                    if any_selected:
                        continue
                    
                    # Get the question
                    question_text = ""
                    try:
                        q = group[0].find_element(By.XPATH, "./ancestor::fieldset//legend")
                        question_text = q.text.strip()
                    except:
                        try:
                            q = group[0].find_element(By.XPATH, "./preceding::*[self::label or self::div or self::span][1]")
                            question_text = q.text.strip()
                        except:
                            pass
                    
                    # Get options
                    options = []
                    for r in group:
                        try:
                            lbl = r.find_element(By.XPATH, "./following::label[1]").text.strip()
                            options.append(lbl)
                        except:
                            pass
                    
                    if question_text and options:
                        unanswered.append({
                            "type": "radio",
                            "question": question_text,
                            "options": options,
                            "elements": group
                        })
                except:
                    continue
            
            # Find unselected checkbox groups
            checkbox_questions = self.driver.find_elements(By.XPATH, 
                "//div[contains(@class,'error') or .//span[contains(text(),'Please')]]/preceding::*[self::label or self::legend][1]"
            )
            
            if not unanswered:
                print("    [!] Could not identify unanswered questions.")
                return False
            
            print(f"    [*] Found {len(unanswered)} unanswered questions. Asking GPT...")
            
            # Ask GPT to answer each question
            for item in unanswered:
                try:
                    if item["type"] == "text":
                        # Text question - ask GPT for a written answer
                        answer = self.gpt(
                            f"You are {CONFIG.get('FULL_NAME', 'a professional')} applying for {job_title} at {company}. Answer concisely and professionally.",
                            f"""Answer this job application question in 2-4 sentences. Be specific and enthusiastic.

Question: {item['question']}

Context about the role:
{desc[:500] if desc else 'No description available'}

Your background: {CONFIG.get('BACKGROUND_BIO', 'Experienced professional')}
Location: {CONFIG.get('LOCATION', 'Australia')}"""
                        )
                        
                        if answer:
                            ta = item["element"]
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ta)
                            speed_sleep(0.2, "apply")
                            ta.clear()
                            ta.send_keys(answer)
                            print(f"    [+] GPT answered: {item['question'][:50]}...")
                            speed_sleep(0.2, "apply")
                    
                    elif item["type"] == "radio":
                        # Multiple choice - ask GPT which option to pick
                        options_text = "\n".join([f"- {opt}" for opt in item["options"]])
                        
                        answer = self.gpt(
                            "You are answering job application questions. Reply with ONLY the exact option text to select. Nothing else.",
                            f"""Question: {item['question']}

Options:
{options_text}

Important context:
- You are an Australian citizen with full work rights
- You have a driver's license
- You are based in {CONFIG.get('LOCATION', 'Australia')}
- You can travel if needed
- Answer YES to capability questions
- For experience questions, pick the highest/best option

Reply with ONLY the exact option text to select:"""
                        )
                        
                        if answer:
                            answer_clean = answer.strip().lower()
                            # Find and click the matching option
                            for i, opt in enumerate(item["options"]):
                                if opt.lower() in answer_clean or answer_clean in opt.lower():
                                    r = item["elements"][i]
                                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                                    self.driver.execute_script("arguments[0].click();", r)
                                    print(f"    [+] GPT selected: {opt}")
                                    speed_sleep(0.2, "apply")
                                    break
                
                except Exception as e:
                    print(f"    [!] GPT answer error: {e}")
                    continue
            
            return True
            
        except Exception as e:
            print(f"    [!] Error detection failed: {e}")
            return False

    # ---------- APPLY FLOW ----------
    def apply(self, job_title, company, job_url=""):
        speed_sleep(2, "scan")
        throttle()
        
        # Stealth: Random scroll and pause like reading the job
        stealth_random_scroll(self.driver)
        stealth_random_pause()

        # Skip external sites
        try:
            external = self.driver.find_elements(
                By.XPATH,
                "//button[contains(., 'company site') or contains(., 'Apply on company')]"
            )
            if external:
                print("    [-] External site. Skipping.")
                return
        except:
            pass

        self.driver.execute_script("window.scrollTo(0, 300);")
        speed_sleep(1, "scan")
        throttle()
        
        # Stealth: Simulate reading before applying
        stealth_reading_delay()

        candidates = [
            (By.XPATH, "//button[contains(., 'Quick apply')]"),
            (By.XPATH, "//button[contains(., 'Quick Apply')]"),
            (By.XPATH, "//button[.//span[contains(text(), 'Quick apply')]]"),
            (By.XPATH, "//button[.//span[contains(text(), 'Quick Apply')]]"),
            (By.CSS_SELECTOR, "button[data-automation='quickApplyButton']"),
            (By.CSS_SELECTOR, "button[data-automation*='quickApply']"),
            (By.CSS_SELECTOR, "a[data-automation*='quickApply']"),
            (By.XPATH, "//button[contains(@aria-label, 'Quick apply')]"),
            (By.XPATH, "//button[contains(@aria-label, 'Quick Apply')]"),
            (By.XPATH, "//*[self::button or self::a][.//*[contains(text(),'Quick apply')]]"),
            (By.XPATH, "//button[contains(., 'Apply now')]"),
            (By.XPATH, "//button[contains(., 'Apply')]"),
        ]

        clicked = False

        for by, sel in candidates:
            try:
                btn = self.driver.find_element(by, sel)
                if btn.is_displayed() and btn.is_enabled():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    speed_sleep(1, "scan")
                    throttle()
                    stealth_before_click()  # Human-like pause before clicking
                    self.driver.execute_script("arguments[0].click();", btn)
                    print("    [+] Clicked apply button:", sel)
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            print("    [-] No apply button found.")
            return

        speed_sleep(3, "apply")
        throttle()
        stealth_random_pause()  # Pause after form loads

        desc = self.get_description()

        # --------------------------
        # PAGE 1 — only text + cover letter
        # --------------------------
        self.fill_cover_letter(job_title, company, desc)
        self.answer_questions(job_title, company, desc)

        try:
            cont = self.driver.find_element(
                By.XPATH,
                "//button[contains(., 'Continue') or contains(., 'Next')]"
            )
            self.driver.execute_script("arguments[0].click();", cont)
            print("    [+] Continue → Page 2")
            speed_sleep(3, "apply")
        except:
            print("    [-] Cannot continue from page 1.")
            return

        # --------------------------
        # PAGE 2+ — full automation with GPT fallback
        # --------------------------
        for page_attempt in range(6):
            # First pass - use rule-based handlers
            self.answer_questions(job_title, company, desc)
            self.answer_radio_buttons()
            self.answer_checkboxes()
            self.answer_dropdowns()
            self.answer_salary_fields()

            # Try to continue
            try:
                cont = self.driver.find_element(
                    By.XPATH,
                    "//button[contains(., 'Continue') or contains(., 'Next')]"
                )
                self.driver.execute_script("arguments[0].click();", cont)
                print("    [+] Continue")
                speed_sleep(2, "apply")
                
                # Check if there are validation errors after clicking continue
                error_box = self.driver.find_elements(By.XPATH,
                    "//*[contains(text(), 'Before you can continue') or contains(text(), 'address the following') or contains(@class, 'error') and contains(text(), 'Required')]"
                )
                
                if error_box:
                    print("    [!] Form validation errors detected!")
                    # Use GPT to fix the errors
                    if self.detect_and_fix_errors(job_title, company, desc):
                        # Try clicking continue again after GPT fixes
                        speed_sleep(1, "apply")
                        try:
                            cont = self.driver.find_element(
                                By.XPATH,
                                "//button[contains(., 'Continue') or contains(., 'Next')]"
                            )
                            self.driver.execute_script("arguments[0].click();", cont)
                            print("    [+] Continue (after GPT fix)")
                            speed_sleep(2, "apply")
                        except:
                            pass
                
                continue
            except:
                pass
            break

        # FINAL SUBMIT
        try:
            submit = self.driver.find_element(
                By.XPATH,
                "//button[contains(., 'Submit application')]"
            )
            self.driver.execute_script("arguments[0].click();", submit)
            print("    [+] SUBMITTED.")
            speed_sleep(3, "apply")

            # LOG SUCCESSFUL SUBMISSION
            try:
                # Use the original job URL, not the confirmation page URL
                self.log_job(job_title, company, job_url)
            except Exception as e:
                print("    [-] Logging failed:", e)

            # COUNT REAL SUBMISSION
            self.successful_submits += 1
            print(f"    [+] Successful submissions: {self.successful_submits}")

        except:
            print("    [-] No Submit button found.")


    # ---------- NEXT PAGE ----------
    def go_to_next_page(self):
        try:
            # New SEEK pagination uses aria-label, not data-automation
            selectors = [
                "//a[@aria-label='Next']",
                "//a[contains(text(), 'Next')]",
                "//button[@aria-label='Next']",
                "//button[contains(text(), 'Next')]",
            ]

            for sel in selectors:
                try:
                    next_btn = self.driver.find_element(By.XPATH, sel)
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
                    speed_sleep(0.5, "scan")
                    throttle()
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    print("[*] Next page clicked.")
                    speed_sleep(3, "scan")
                    throttle()
                    return True
                except:
                    continue

            print("[!] Next page button not found.")
            return False

        except Exception as e:
            print("Next page error:", e)
            return False

    # ---------- MAIN LOOP ----------
    def run(self):
        self.ensure_logged_in()

        job_titles = CONFIG.get("JOB_TITLES", [])
        location = CONFIG.get("LOCATION", "Brisbane")

        for search_title in job_titles:
            # Check for stop signal between searches
            if check_control() == "stop":
                print("[!] Stop signal received. Shutting down...")
                return
            
            print(f"\n==============================")
            print(f"🔎 SEARCHING FOR: {search_title}")
            print(f"==============================\n")

            search_url = build_search_url(search_title, location)
            print(f"[*] Opening search for: {search_title}")
            print(f"    URL: {search_url}")

            self.driver.get(search_url)
            speed_sleep(3, "scan")
            throttle()

            page = 1

            while self.successful_submits < MAX_JOBS:
                # Check for stop signal
                if check_control() == "stop":
                    print("[!] Stop signal received. Shutting down...")
                    return
                
                print(f"\n===== PAGE {page} =====")
                cards = self.get_job_cards()

                if not cards:
                    print("[!] No job cards found.")
                    break

                for idx, card in enumerate(cards):
                    # Check for pause/stop before each job
                    status = check_control()
                    if status == "stop":
                        print("[!] Stop signal received. Shutting down...")
                        return
                    elif status == "pause":
                        print("[*] Bot paused. Waiting to resume...")
                        if not wait_while_paused():
                            return  # Stop signal received while paused
                        print("[*] Bot resumed.")
                    
                    try:
                        title = card.find_element(By.CSS_SELECTOR, "[data-automation='jobTitle']").text
                    except:
                        title = "Unknown"

                    if not title_matches(title):
                        print(f"    [-] SKIPPED (title mismatch): {title}")
                        continue
                    
                    # Check if title is blocked
                    if is_title_blocked(title):
                        print(f"    [🚫] BLOCKED (title): {title}")
                        continue

                    if self.successful_submits >= MAX_JOBS:
                        break

                    try:
                        company = card.find_element(By.CSS_SELECTOR, "[data-automation='jobCompany']").text
                    except:
                        company = "Unknown"
                    
                    # Check if company is blocked
                    if is_company_blocked(company):
                        print(f"    [🚫] BLOCKED (company): {company}")
                        continue

                    print(f"\n[*] Job {idx + 1}: {title} | {company}")
                    
                    # Stealth: Random pause before opening job
                    stealth_random_pause()

                    job_url = self.open_job(card)
                    if not job_url:
                        continue

                    speed_sleep(2, "scan")

                    try:
                        self.apply(title, company, job_url)
                    except Exception as e:
                        print(f"    [!] Error during apply: {e}")

                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                        
                        # Stealth: Scroll around on main page between jobs
                        stealth_random_scroll(self.driver)

                    # Apply cooldown between jobs
                    job_cooldown()

                if self.successful_submits >= MAX_JOBS:
                    break

                moved = self.go_to_next_page()
                if not moved:
                    break

                page += 1

        print(f"\n[*] DONE — Successfully submitted {self.successful_submits} REAL applications.")


def main():
    driver = init_browser()
    bot = SeekBot(driver)
    bot.run()


if __name__ == "__main__":
    main()

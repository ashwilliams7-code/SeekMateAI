"""
Indeed Bot - Separate from SEEK bot
Applies to jobs on Indeed.com.au using the same config and logic
"""
import os
import json
import time
import sys
import subprocess
import threading
import random

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

from openai import OpenAI
import openpyxl
from openpyxl import Workbook
from datetime import datetime
import re
import urllib.request
import urllib.parse

# Gmail cleanup
try:
    from gmail_cleanup import GmailCleanup
    GMAIL_CLEANUP_AVAILABLE = True
except ImportError:
    GMAIL_CLEANUP_AVAILABLE = False
    print("    [!] Gmail cleanup module not available")

# 2Captcha for CAPTCHA solving
try:
    from twocaptcha import TwoCaptcha
    TWOCAPTCHA_AVAILABLE = True
except ImportError:
    TWOCAPTCHA_AVAILABLE = False
    print("    [!] 2captcha-python not installed. Run: pip install 2captcha-python")


# ============================================
# PATH & CONFIG
# ============================================
def resource_path(relative_path):
    """Get path for bundled or dev mode"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def get_data_dir():
    """Get a consistent, user-writable data directory for logs (same as GUI)"""
    if sys.platform == "darwin":  # macOS
        data_dir = os.path.expanduser("~/Library/Application Support/SeekMateAI")
    elif sys.platform == "win32":  # Windows
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SeekMateAI")
    else:  # Linux
        data_dir = os.path.expanduser("~/.seekmateai")
    
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


CONFIG_FILE = resource_path("config.json")
CONTROL_FILE = resource_path("control.json")
LOG_FILE = os.path.join(get_data_dir(), "log.txt")  # Same path as GUI


# ============================================
# OVERRIDE PRINT TO LOG TO FILE
# ============================================
import builtins
_orig_print = builtins.print

def print(*args, **kwargs):
    """Override print to also write to log file for GUI"""
    # Write to log file with flush
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            builtins.print(*args, file=f, **kwargs)
            f.flush()
    except Exception as e:
        pass
    # Also print to console with flush
    kwargs['flush'] = True
    _orig_print(*args, **kwargs)

builtins.print = print


if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("config.json not found. Run config_gui.exe first.")

with open(CONFIG_FILE, "r") as f:
    CONFIG = json.load(f)

# Config values
FULL_NAME = CONFIG.get("FULL_NAME", "")
LOCATION = CONFIG.get("LOCATION", "Brisbane")
JOB_TITLES = CONFIG.get("JOB_TITLES", [])
MAX_JOBS = CONFIG.get("MAX_JOBS", 10)
EXPECTED_SALARY = CONFIG.get("EXPECTED_SALARY", 100000)
OPENAI_API_KEY = CONFIG.get("OPENAI_API_KEY", "")
SCAN_SPEED = CONFIG.get("SCAN_SPEED", 50)
APPLY_SPEED = CONFIG.get("APPLY_SPEED", 50)
COOLDOWN_DELAY = CONFIG.get("COOLDOWN_DELAY", 5)
STEALTH_MODE = CONFIG.get("STEALTH_MODE", True)
BLOCKED_COMPANIES = [c.lower().strip() for c in CONFIG.get("BLOCKED_COMPANIES", [])]
BLOCKED_TITLES = [t.lower().strip() for t in CONFIG.get("BLOCKED_TITLES", [])]

print(f"[INDEED BOT] Scan: {SCAN_SPEED}% | Apply: {APPLY_SPEED}% | Cooldown: {COOLDOWN_DELAY}s | Stealth: {'ON' if STEALTH_MODE else 'OFF'}")

# ============================================
# TWILIO WHATSAPP NOTIFICATIONS
# ============================================
TWILIO_ACCOUNT_SID = CONFIG.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = CONFIG.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = CONFIG.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_NOTIFICATIONS = CONFIG.get("WHATSAPP_NOTIFICATIONS", True)

# Profile phone numbers for WhatsApp notifications
PROFILE_PHONES = {
    "Ash Williams": "+61490077979",
    "Jennifer Berrio": "+61491723617",
    "Rafael Hurtado": "+6411557289",
}

def send_whatsapp_summary(full_name, jobs_applied, duration_minutes, job_titles=None):
    """Send a WhatsApp summary via Twilio when run completes"""
    if not WHATSAPP_NOTIFICATIONS:
        print("[WhatsApp] Notifications disabled")
        return False
    
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("[WhatsApp] Twilio credentials not configured")
        return False
    
    # Get phone number for the current profile
    phone = PROFILE_PHONES.get(full_name)
    if not phone:
        print(f"[WhatsApp] No phone number configured for {full_name}")
        return False
    
    # Format job titles list
    titles_text = ""
    if job_titles and len(job_titles) > 0:
        # Get unique titles and limit to first 20 to avoid message being too long
        unique_titles = list(dict.fromkeys(job_titles))[:20]
        titles_list = "\n".join([f"• {title}" for title in unique_titles])
        if len(job_titles) > 20:
            titles_list += f"\n• ... and {len(job_titles) - 20} more"
        titles_text = f"\n\n📋 *Job Titles Applied To:*\n{titles_list}"
    
    # Format the message
    message = f"""🎯 *SeekMate AI Run Complete*

👤 Profile: {full_name}
✅ Jobs Applied: {jobs_applied}
⏱️ Duration: {duration_minutes} minutes
📅 Time: {datetime.now().strftime('%I:%M %p, %d %b %Y')}{titles_text}

Great work! Your applications have been submitted."""

    try:
        # Twilio API endpoint
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        # Format phone for WhatsApp
        to_number = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        
        # Prepare data
        data = urllib.parse.urlencode({
            'From': TWILIO_WHATSAPP_FROM,
            'To': to_number,
            'Body': message
        }).encode('utf-8')
        
        # Create request with basic auth
        request = urllib.request.Request(url, data=data)
        credentials = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
        import base64
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        request.add_header('Authorization', f'Basic {encoded_credentials}')
        
        # Send request
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status == 201:
                print(f"[WhatsApp] ✅ Summary sent to {full_name} ({phone})")
                return True
            else:
                print(f"[WhatsApp] Failed: Status {response.status}")
                return False
                
    except Exception as e:
        print(f"[WhatsApp] Error sending message: {e}")
        return False


# ============================================
# CONTROL CHECK
# ============================================
def check_control():
    """Check control.json for pause/stop signals"""
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
    """Block while paused, return False if stopped"""
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
# SPEED HELPERS
# ============================================
def speed_sleep(base_seconds, mode="scan"):
    """Sleep adjusted by speed settings"""
    speed = SCAN_SPEED if mode == "scan" else APPLY_SPEED
    multiplier = 2 - (speed / 50)
    actual = base_seconds * multiplier
    if STEALTH_MODE:
        actual *= random.uniform(0.8, 1.3)
    time.sleep(max(0.3, actual))


def stealth_random_pause():
    """Random human-like pause"""
    if STEALTH_MODE:
        time.sleep(random.uniform(0.5, 2.0))


def stealth_random_scroll(driver):
    """Random scroll like human reading"""
    if STEALTH_MODE:
        scroll_amount = random.randint(100, 400)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.3, 0.8))


def job_cooldown():
    """Cooldown between job applications"""
    if COOLDOWN_DELAY > 0:
        print(f"    [*] Cooldown: waiting {COOLDOWN_DELAY}s before next job...")
        time.sleep(COOLDOWN_DELAY)


# ============================================
# TITLE MATCHING
# ============================================
def title_matches(title: str) -> bool:
    """Check if job title matches user's target titles"""
    allowed = [t.lower().strip() for t in JOB_TITLES]
    title_clean = title.lower().strip()
    
    # Direct match
    if any(a in title_clean for a in allowed):
        return True
    
    # Reverse match
    title_words = [w for w in title_clean.replace('-', ' ').split() if len(w) > 3]
    for word in title_words:
        if any(word in a for a in allowed):
            return True
    
    return False


def is_title_blocked(title: str) -> bool:
    """Check if title is in blocklist"""
    title_clean = title.lower().strip()
    return any(blocked in title_clean for blocked in BLOCKED_TITLES)


def is_company_blocked(company: str) -> bool:
    """Check if company is in blocklist"""
    company_clean = company.lower().strip()
    return any(blocked in company_clean for blocked in BLOCKED_COMPANIES)


# ============================================
# INDEED URL BUILDER
# ============================================
def build_indeed_url(job_title, location):
    """Build Indeed Australia search URL"""
    # Strip ", Australia" from location
    safe_location = location.replace(", Australia", "").strip()
    
    job_query = job_title.replace(" ", "+")
    loc_query = safe_location.replace(" ", "+")
    
    return f"https://au.indeed.com/jobs?q={job_query}&l={loc_query}&sort=date"


# ============================================
# BROWSER INIT
# ============================================
def init_browser():
    """Initialize Chrome for Indeed"""
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Use separate profile for Indeed
    profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_indeed_profile")
    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Stealth tweaks
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """
    })
    
    return driver


# ============================================
# INDEED BOT CLASS
# ============================================
class IndeedBot:
    def __init__(self, driver):
        self.driver = driver
        self.successful_submits = 0
        self.wait = WebDriverWait(driver, 10)
        
        # OpenAI client
        if OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            self.client = None
        
        # Initialize Gmail cleanup if available and enabled
        self.gmail_cleanup = None
        self.gmail_thread = None
        use_gmail_cleanup = CONFIG.get("USE_GMAIL_CLEANUP", False)
        if GMAIL_CLEANUP_AVAILABLE and use_gmail_cleanup:
            try:
                # Create Gmail cleanup with separate window (doesn't interfere with main bot)
                if self.client:
                    self.gmail_cleanup = GmailCleanup(
                        driver=None,  # Will create its own browser
                        openai_client=self.client,
                        create_separate_window=True
                    )
                    print("[Gmail] Gmail cleanup initialized with GPT analysis in separate window")
                else:
                    # Fallback to API key if client not available
                    self.gmail_cleanup = GmailCleanup(
                        driver=None,
                        openai_api_key=OPENAI_API_KEY,
                        create_separate_window=True
                    )
                    print("[Gmail] Gmail cleanup initialized in separate window")
            except Exception as e:
                print(f"[Gmail] Failed to initialize: {e}")
        elif not use_gmail_cleanup:
            print("[Gmail] Gmail cleanup is disabled in config")

    def log_job(self, title, company, url):
        """Log applied job to Excel"""
        file_path = "job_log.xlsx"
        
        if not os.path.exists(file_path):
            wb = Workbook()
            ws = wb.active
            ws.append(["Timestamp", "Job Title", "Company", "URL", "Platform"])
            wb.save(file_path)
        
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        ws.append([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            title,
            company,
            url,
            "Indeed"
        ])
        wb.save(file_path)
        print(f"    [+] Logged to Excel → {title} @ {company} (Indeed)")
        
        # Track job title for WhatsApp summary
        if title not in self.applied_job_titles:
            self.applied_job_titles.append(title)

    def gpt(self, system_prompt: str, user_prompt: str) -> str:
        """Call GPT for cover letter or job check"""
        if not self.client:
            return ""
        try:
            res = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=800,
                temperature=0.4,
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            print(f"GPT ERROR: {e}")
            return ""

    def gpt_should_apply(self, job_title: str, job_description: str) -> bool:
        """Use GPT to check if job matches user's target roles"""
        if not OPENAI_API_KEY:
            return True
        
        prompt = f"""Analyze if this job is a good match for someone looking for: {', '.join(JOB_TITLES)}

JOB TITLE: {job_title}

JOB DESCRIPTION (first 800 chars):
{job_description[:800]}

Rules:
- If the job is primarily SALES, CUSTOMER SERVICE, RETAIL, CALL CENTRE focused, say NO
- If the job matches the target roles, say YES
- Be strict: "Project Manager" should NOT apply to "Sales Manager"

Reply with ONLY "YES" or "NO" followed by a brief reason (max 15 words).
"""
        
        try:
            response = self.gpt(
                "You are a job matching assistant. Be strict about role relevance.",
                prompt
            )
            print(f"    [🤖 GPT] Job check: {response}")
            return response.upper().startswith("YES")
        except:
            return True

    def gpt_answer_question(self, question: str, options: list = None) -> str:
        """Use GPT to answer screening questions intelligently"""
        q_lower = question.lower()
        experience_title = JOB_TITLES[0] if JOB_TITLES else "Project Manager"
        salary = str(EXPECTED_SALARY) if EXPECTED_SALARY else "100000"
        
        # Handle specific field types directly - DON'T send to GPT
        if "job title" in q_lower or "jobtitle" in q_lower or "position" in q_lower:
            print(f"    [*] Detected Job Title field - using: {experience_title}")
            return experience_title
        if "company" in q_lower and "salary" not in q_lower and "how" not in q_lower:
            print("    [*] Detected Company field - using: Previous Company")
            return "Previous Company"
        if "salary" in q_lower or "rate expectation" in q_lower or "expected pay" in q_lower:
            print(f"    [*] Detected Salary field - using: {salary}")
            return salary
        if "notice" in q_lower and "period" in q_lower:
            return "2 weeks"
        if "years" in q_lower and ("experience" in q_lower or "how many" in q_lower):
            return "5"
        
        if not OPENAI_API_KEY or not self.client:
            # Default answers without GPT
            if "work in australia" in q_lower or "legally entitled" in q_lower or "citizen" in q_lower:
                return "Yes"
            if "willing" in q_lower or "participate" in q_lower:
                return "Yes"
            if "acknowledge" in q_lower or "true and correct" in q_lower:
                return "Yes"
            return "Yes"  # Default to Yes for most questions
        
        options_text = f"\nAvailable options: {', '.join(options)}" if options else ""
        
        prompt = f"""You are filling out a job application for an Australian citizen applying for a {experience_title} role.

QUESTION: {question}
{options_text}

Important context:
- The applicant IS an Australian Citizen (answer Yes to work rights questions)
- The applicant is willing to undergo background checks, medical tests, drug tests
- The applicant acknowledges all information is true and correct
- For driver's license questions: answer Yes (most professionals have one)
- For white card/construction induction: answer Yes if applying to construction jobs, otherwise No
- For questions about experience: default to Yes with relevant experience
- For notice period: suggest "2 weeks" or "Immediately available"
- NEVER put salary values in job title fields
- Job title should be: {experience_title}
- Company name should be a previous employer name, NOT a number

Reply with ONLY the answer (Yes, No, or the text to fill in). Keep it brief.
"""
        
        try:
            response = self.gpt(
                "You are a job application assistant. Give brief, appropriate answers to screening questions.",
                prompt
            )
            # Clean up the response
            answer = response.strip().strip('"').strip("'")
            print(f"    [🤖 GPT] Q: {question[:50]}... A: {answer}")
            return answer
        except:
            return "Yes"  # Default fallback

    def answer_screening_questions_with_gpt(self):
        """Find and answer all screening questions on the page using GPT"""
        try:
            # Find all question containers
            page_text = self.driver.page_source
            
            # Find all unanswered radio button groups
            fieldsets = self.driver.find_elements(By.CSS_SELECTOR, "fieldset, div[role='radiogroup'], div[role='group']")
            
            for fieldset in fieldsets:
                try:
                    # Get the question text
                    question_text = ""
                    try:
                        legend = fieldset.find_element(By.CSS_SELECTOR, "legend, label, span")
                        question_text = legend.text.strip()
                    except:
                        question_text = fieldset.text.split('\n')[0] if fieldset.text else ""
                    
                    if not question_text or len(question_text) < 10:
                        continue
                    
                    # Find radio buttons in this group
                    radios = fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                    if not radios:
                        continue
                    
                    # Check if any is already selected
                    any_selected = any(r.is_selected() for r in radios)
                    if any_selected:
                        continue
                    
                    # Get available options
                    options = []
                    for radio in radios:
                        try:
                            label = radio.find_element(By.XPATH, "./following-sibling::label | ./ancestor::label | ../label")
                            options.append(label.text.strip())
                        except:
                            try:
                                parent = radio.find_element(By.XPATH, "./..")
                                options.append(parent.text.strip())
                            except:
                                pass
                    
                    # Get GPT's answer
                    gpt_answer = self.gpt_answer_question(question_text, options)
                    
                    # Click the appropriate option
                    for radio in radios:
                        try:
                            label_text = ""
                            try:
                                label = radio.find_element(By.XPATH, "./following-sibling::label | ./ancestor::label | ../label")
                                label_text = label.text.strip().lower()
                            except:
                                parent = radio.find_element(By.XPATH, "./..")
                                label_text = parent.text.strip().lower()
                            
                            if gpt_answer.lower() in label_text or label_text in gpt_answer.lower():
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", radio)
                                time.sleep(0.3)
                                try:
                                    radio.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", radio)
                                print(f"    [+] Answered: {question_text[:40]}... → {label_text}")
                                break
                        except:
                            continue
                            
                except Exception as e:
                    continue
            
            # Also handle any text inputs (empty or with wrong values)
            try:
                text_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type]), textarea")
                experience_title = JOB_TITLES[0] if JOB_TITLES else "Project Manager"
                salary = str(EXPECTED_SALARY) if EXPECTED_SALARY else "100000"
                
                for inp in text_inputs:
                    try:
                        if not inp.is_displayed():
                            continue
                            
                        current_val = inp.get_attribute("value") or ""
                        
                        # Find the associated label/question
                        question = ""
                        try:
                            label = inp.find_element(By.XPATH, "./preceding::label[1]")
                            question = label.text.strip()
                        except:
                            try:
                                parent = inp.find_element(By.XPATH, "./ancestor::*[4]")
                                question = parent.text.split('\n')[0]
                            except:
                                pass
                        
                        if question:
                            q_lower = question.lower()
                            
                            # CRITICAL: Fix job title fields that have salary values
                            if "job title" in q_lower or "jobtitle" in q_lower:
                                if current_val == "" or current_val.isdigit() or current_val == salary:
                                    inp.clear()
                                    inp.send_keys(experience_title)
                                    print(f"    [+] Fixed Job title: {experience_title} (was: '{current_val}')")
                                continue
                            
                            # Only fill empty fields for other types
                            if current_val == "":
                                answer = self.gpt_answer_question(question)
                                inp.clear()
                                inp.send_keys(answer)
                                print(f"    [+] Filled: {question[:40]}... → {answer}")
                    except:
                        continue
            except:
                pass
                
        except Exception as e:
            print(f"    [!] GPT question answering error: {e}")

    def ensure_logged_in(self):
        """Navigate to Indeed and check login status"""
        self.driver.get("https://au.indeed.com/")
        time.sleep(3)
        
        # Check if logged in by looking for profile elements
        try:
            # Indeed shows different elements when logged in
            profile = self.driver.find_elements(By.CSS_SELECTOR, "[data-gnav-element-name='Account']")
            if profile:
                print("[*] Indeed: Already logged in.")
                return
        except:
            pass
        
        print("[!] Indeed: Please log in manually...")
        print("[*] Waiting for login (checking every 5 seconds)...")
        
        # Wait for user to log in
        for _ in range(60):  # Wait up to 5 minutes
            time.sleep(5)
            try:
                profile = self.driver.find_elements(By.CSS_SELECTOR, "[data-gnav-element-name='Account']")
                if profile:
                    print("[*] Indeed: Login detected!")
                    return
            except:
                pass
            
            if check_control() == "stop":
                return
        
        print("[!] Indeed: Login timeout. Continuing anyway...")

    def get_job_cards(self):
        """Get job cards from Indeed search results"""
        selectors = [
            "div.job_seen_beacon",
            "div.jobsearch-ResultsList > div",
            "td.resultContent",
            "div[data-jk]",
            "li.css-5lfssm",
        ]
        
        for sel in selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if cards:
                    print(f"[*] Found {len(cards)} Indeed jobs on this page.")
                    return cards
            except:
                continue
        
        # Fallback
        cards = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='job']")
        print(f"[*] Found {len(cards)} Indeed jobs on this page.")
        return cards

    def get_job_title(self, card):
        """Extract job title from card"""
        selectors = [
            "h2.jobTitle a span",
            "h2.jobTitle span",
            "a[data-jk] span",
            ".jobTitle",
            "h2 a",
        ]
        for sel in selectors:
            try:
                el = card.find_element(By.CSS_SELECTOR, sel)
                if el.text.strip():
                    return el.text.strip()
            except:
                continue
        return "Unknown"

    def get_company_name(self, card):
        """Extract company name from card"""
        selectors = [
            "[data-testid='company-name']",
            ".companyName",
            "span.css-92r8pb",
            ".company",
        ]
        for sel in selectors:
            try:
                el = card.find_element(By.CSS_SELECTOR, sel)
                if el.text.strip():
                    return el.text.strip()
            except:
                continue
        return "Unknown"

    def has_easily_apply(self, card):
        """Check if job card has 'Easily apply' badge (blue arrow)"""
        try:
            # Look for "Easily apply" text/badge on the card
            easily_apply_selectors = [
                ".//span[contains(text(), 'Easily apply')]",
                ".//span[contains(text(), 'easily apply')]",
                ".//div[contains(@class, 'iaLabel')]",
                ".//span[contains(@class, 'iaLabel')]",
                ".//*[contains(text(), 'Easily apply')]",
            ]
            
            for xpath in easily_apply_selectors:
                try:
                    badge = card.find_element(By.XPATH, xpath)
                    if badge:
                        return True
                except:
                    continue
            
            # Also check CSS selectors
            css_selectors = [
                "span.iaLabel",
                "div.iaLabel", 
                "[data-testid='attribute_snippet_testid']",
            ]
            
            for sel in css_selectors:
                try:
                    badge = card.find_element(By.CSS_SELECTOR, sel)
                    if badge and "easily" in badge.text.lower():
                        return True
                except:
                    continue
            
            return False
            
        except:
            return False

    def open_job(self, card):
        """Click on job card to open details"""
        try:
            # Try clicking the title link
            link_selectors = [
                "h2.jobTitle a",
                "a[data-jk]",
                "a.jcs-JobTitle",
                "h2 a",
            ]
            
            for sel in link_selectors:
                try:
                    link = card.find_element(By.CSS_SELECTOR, sel)
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(2)
                    return True
                except:
                    continue
            
            # Try clicking the card itself
            self.driver.execute_script("arguments[0].click();", card)
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"    [-] Failed to open job: {e}")
            return False

    def get_description(self):
        """Get job description from Indeed job panel"""
        selectors = [
            "#jobDescriptionText",
            ".jobsearch-jobDescriptionText",
            "[id*='jobDescription']",
            ".job-description",
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

    def solve_recaptcha_with_gpt(self):
        """Use GPT-4 Vision to solve reCAPTCHA image challenges"""
        import base64
        
        try:
            # Take screenshot of the page
            screenshot = self.driver.get_screenshot_as_png()
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
            
            # Ask GPT-4 Vision to analyze the CAPTCHA
            prompt = """You are solving a reCAPTCHA image challenge. Look at the popup with the blue header.

STEP 1: Read the blue header to see what object to find (e.g., "motorcycles", "bicycles", "cars", "traffic lights", "crosswalks", "buses", "fire hydrants")

STEP 2: Look at the image grid below the header. Count the squares:
- If it's a 3x3 grid (9 images), number them:
  1  2  3
  4  5  6
  7  8  9

- If it's a 4x4 grid (16 images), number them:
  1  2  3  4
  5  6  7  8
  9  10 11 12
  13 14 15 16

STEP 3: Identify which squares contain the target object:
- A bicycle = two wheels, handlebars, frame, pedals
- A motorcycle = larger than bicycle, has engine/motor, often has rider
- A car = four wheels, enclosed vehicle
- Traffic light = vertical pole with red/yellow/green lights
- Crosswalk = white painted stripes on road for pedestrians
- Bus = large vehicle for passengers
- Fire hydrant = red/yellow post on sidewalk for water

STEP 4: Look for squares with BLUE CHECKMARKS (✓) - these are ALREADY SELECTED, skip them!

STEP 5: Reply with ONLY the numbers of squares that:
- Contain the target object (even partially visible)
- Do NOT have a blue checkmark already

Format: Just numbers separated by commas, nothing else.
Example: 2,5,8

If no squares need clicking or you can't see the CAPTCHA clearly: SKIP"""

            if not self.client:
                print("    [!] No OpenAI client - can't solve CAPTCHA with GPT")
                return None
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # GPT-4 Vision model
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at solving visual puzzles. Be very precise about identifying objects in images. When looking at a grid of images, carefully examine each square."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_b64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150,
                temperature=0.1  # Low temperature for more precise answers
            )
            
            answer = response.choices[0].message.content.strip()
            print(f"    [🤖 GPT Vision] CAPTCHA answer: {answer}")
            
            if answer == "SKIP" or not answer:
                return None
            
            # Parse the numbers
            try:
                squares = [int(x.strip()) for x in answer.replace(" ", "").split(",") if x.strip().isdigit()]
                return squares
            except:
                return None
                
        except Exception as e:
            print(f"    [!] GPT Vision error: {e}")
            return None

    def click_recaptcha_squares(self, squares):
        """Click on specific squares in the reCAPTCHA grid"""
        try:
            # Find the reCAPTCHA challenge iframe and switch to it
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            captcha_iframe = None
            
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                title = iframe.get_attribute("title") or ""
                # Look specifically for the bframe (challenge frame), not anchor frame
                if "recaptcha" in src.lower() and "bframe" in src.lower():
                    captcha_iframe = iframe
                    break
                if "recaptcha challenge" in title.lower():
                    captcha_iframe = iframe
                    break
            
            if captcha_iframe:
                self.driver.switch_to.frame(captcha_iframe)
                time.sleep(1)
            else:
                print("    [!] Could not find reCAPTCHA challenge iframe")
                return False
            
            # Find all the image tiles - be more specific
            tiles = []
            
            # Method 1: Table cells (most common for 3x3 and 4x4 grids)
            tiles = self.driver.find_elements(By.CSS_SELECTOR, "table.rc-imageselect-table-33 td, table.rc-imageselect-table-44 td")
            
            # Method 2: Generic table cells
            if not tiles or len(tiles) < 9:
                tiles = self.driver.find_elements(By.CSS_SELECTOR, "table.rc-imageselect-table td")
            
            # Method 3: Tile divs
            if not tiles or len(tiles) < 9:
                tiles = self.driver.find_elements(By.CSS_SELECTOR, "td.rc-imageselect-tile")
            
            # Method 4: Image wrappers
            if not tiles or len(tiles) < 9:
                tiles = self.driver.find_elements(By.CSS_SELECTOR, "div.rc-image-tile-wrapper")
            
            # Validate we have a proper grid (9 or 16 tiles)
            if len(tiles) not in [9, 16]:
                print(f"    [!] Unexpected tile count: {len(tiles)} (expected 9 or 16)")
                # Try one more method - all clickable tile areas
                tiles = self.driver.find_elements(By.CSS_SELECTOR, ".rc-imageselect-tile")
            
            print(f"    [*] Found {len(tiles)} CAPTCHA tiles")
            
            # Verify grid size matches GPT's assumption
            grid_size = len(tiles)
            max_square = max(squares) if squares else 0
            
            if max_square > grid_size:
                print(f"    [!] GPT suggested square {max_square} but only {grid_size} tiles exist!")
                print(f"    [!] Adjusting - will only click valid squares")
            
            # Click on the specified squares (1-indexed)
            clicked = []
            for sq in squares:
                if 1 <= sq <= len(tiles):
                    tile = tiles[sq - 1]
                    try:
                        # Check if tile is already selected (has checkmark)
                        tile_class = tile.get_attribute("class") or ""
                        if "rc-imageselect-tileselected" in tile_class:
                            print(f"    [*] Tile {sq} already selected, skipping")
                            continue
                        
                        # Scroll tile into view
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tile)
                        time.sleep(0.3)
                        
                        tile.click()
                        clicked.append(sq)
                        print(f"    [+] Clicked tile {sq}")
                        time.sleep(0.5)
                    except Exception as e:
                        try:
                            self.driver.execute_script("arguments[0].click();", tile)
                            clicked.append(sq)
                            print(f"    [+] Clicked tile {sq} (JS)")
                            time.sleep(0.5)
                        except:
                            print(f"    [!] Failed to click tile {sq}: {e}")
                else:
                    print(f"    [!] Invalid tile number: {sq} (grid has {len(tiles)} tiles)")
            
            print(f"    [*] Successfully clicked tiles: {clicked}")
            
            time.sleep(1)
            
            # Click Verify button
            verify_btn = None
            verify_selectors = [
                "//button[@id='recaptcha-verify-button']",
                "//button[contains(text(),'Verify')]",
                "//button[contains(text(),'VERIFY')]",
                "#recaptcha-verify-button",
            ]
            
            for sel in verify_selectors:
                try:
                    if sel.startswith("//"):
                        verify_btn = self.driver.find_element(By.XPATH, sel)
                    else:
                        verify_btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if verify_btn and verify_btn.is_displayed():
                        break
                except:
                    continue
            
            if verify_btn:
                verify_btn.click()
                print("    [+] Clicked Verify")
                time.sleep(3)
            
            # Switch back to main content
            self.driver.switch_to.default_content()
            return True
            
        except Exception as e:
            print(f"    [!] Error clicking CAPTCHA squares: {e}")
            self.driver.switch_to.default_content()
            return False

    def check_for_image_challenge(self):
        """Check if reCAPTCHA image challenge is visible (checks iframes too)"""
        try:
            # First check main page
            page_source = self.driver.page_source.lower()
            if "select all images" in page_source or "select all squares" in page_source:
                return True
            
            # Check for reCAPTCHA challenge iframe (the popup with images)
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    src = iframe.get_attribute("src") or ""
                    title = iframe.get_attribute("title") or ""
                    # The challenge iframe has "bframe" in the src or specific title
                    if "recaptcha" in src.lower() and "bframe" in src.lower():
                        print("    [*] Found reCAPTCHA challenge iframe")
                        return True
                    if "recaptcha challenge" in title.lower():
                        return True
                except:
                    continue
            
            # Also check if there's a visible reCAPTCHA popup by looking for the challenge div
            try:
                challenge_divs = self.driver.find_elements(By.CSS_SELECTOR, "div[style*='visibility: visible'] iframe[src*='recaptcha']")
                if challenge_divs:
                    return True
            except:
                pass
            
            # Check for the challenge popup container
            try:
                popup = self.driver.find_elements(By.CSS_SELECTOR, "div:not([style*='display: none']) > div > iframe[src*='google.com/recaptcha'][src*='bframe']")
                if popup:
                    return True
            except:
                pass
                
            return False
        except:
            return False

    def check_for_try_again(self):
        """Check if reCAPTCHA shows 'Please try again' message"""
        try:
            # Switch to challenge iframe to check for error
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if "recaptcha" in src.lower() and "bframe" in src.lower():
                    self.driver.switch_to.frame(iframe)
                    time.sleep(0.5)
                    
                    # Check for error message
                    try:
                        error_elem = self.driver.find_elements(By.CSS_SELECTOR, ".rc-imageselect-incorrect-response, .rc-imageselect-error-select-more, .rc-imageselect-error-dynamic-more")
                        if error_elem:
                            for elem in error_elem:
                                if elem.is_displayed():
                                    print("    [!] 'Please try again' - need to select more/different images")
                                    self.driver.switch_to.default_content()
                                    return True
                    except:
                        pass
                    
                    # Also check page text
                    try:
                        page_text = self.driver.page_source.lower()
                        if "please try again" in page_text or "please select all" in page_text:
                            print("    [!] 'Please try again' detected in page")
                            self.driver.switch_to.default_content()
                            return True
                    except:
                        pass
                    
                    self.driver.switch_to.default_content()
                    break
            return False
        except:
            self.driver.switch_to.default_content()
            return False

    def handle_recaptcha(self):
        """Detect and solve reCAPTCHA using 2Captcha service"""
        try:
            # Check for reCAPTCHA elements
            page_source = self.driver.page_source.lower()
            
            # Check if there's any reCAPTCHA on the page
            has_recaptcha = False
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if "recaptcha" in src.lower():
                    has_recaptcha = True
                    break
            
            if "recaptcha" in page_source or "i'm not a robot" in page_source:
                has_recaptcha = True
            
            if not has_recaptcha:
                return True  # No CAPTCHA, continue
            
            print("    [!] ⚠️ reCAPTCHA detected on page!")
            
            # Check if 2Captcha is available and configured
            api_key = self.config.get("TWOCAPTCHA_API_KEY", "")
            
            if not TWOCAPTCHA_AVAILABLE:
                print("    [!] 2Captcha not installed - solve CAPTCHA manually (30 sec)...")
                time.sleep(30)
                return True
            
            if not api_key:
                print("    [!] No 2Captcha API key configured - solve manually (30 sec)...")
                time.sleep(30)
                return True
            
            # Find the reCAPTCHA sitekey
            sitekey = None
            
            # Method 1: From iframe src
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if "recaptcha" in src and "k=" in src:
                    match = re.search(r'k=([^&]+)', src)
                    if match:
                        sitekey = match.group(1)
                        print(f"    [*] Found sitekey from iframe: {sitekey[:20]}...")
                        break
            
            # Method 2: From data-sitekey attribute
            if not sitekey:
                recaptcha_divs = self.driver.find_elements(By.CSS_SELECTOR, "[data-sitekey]")
                if recaptcha_divs:
                    sitekey = recaptcha_divs[0].get_attribute("data-sitekey")
                    print(f"    [*] Found sitekey from data attribute: {sitekey[:20]}...")
            
            # Method 3: Search in page source
            if not sitekey:
                match = re.search(r'data-sitekey=["\']([^"\']+)["\']', self.driver.page_source)
                if match:
                    sitekey = match.group(1)
                    print(f"    [*] Found sitekey from page source: {sitekey[:20]}...")
            
            if not sitekey:
                print("    [!] Could not find reCAPTCHA sitekey - solve manually...")
                time.sleep(30)
                return True
            
            print("    [*] 🔄 Sending to 2Captcha service...")
            print("    [*] This may take 10-30 seconds...")
            
            try:
                # Initialize 2Captcha solver
                solver = TwoCaptcha(api_key)
                
                # Solve the reCAPTCHA
                result = solver.recaptcha(
                    sitekey=sitekey,
                    url=self.driver.current_url
                )
                
                token = result['code']
                print(f"    [+] ✅ 2Captcha solved! Token received: {token[:50]}...")
                
                # Inject the token into the page
                # Method 1: Direct element manipulation
                self.driver.execute_script(f'''
                    var responseElement = document.getElementById("g-recaptcha-response");
                    if (responseElement) {{
                        responseElement.style.display = "block";
                        responseElement.innerHTML = "{token}";
                        responseElement.value = "{token}";
                    }}
                ''')
                
                # Method 2: Set all response textareas
                self.driver.execute_script(f'''
                    var responses = document.querySelectorAll('[name="g-recaptcha-response"], textarea.g-recaptcha-response');
                    responses.forEach(function(el) {{
                        el.style.display = "block";
                        el.innerHTML = "{token}";
                        el.value = "{token}";
                    }});
                ''')
                
                # Method 3: Try to trigger the callback function
                self.driver.execute_script(f'''
                    if (typeof ___grecaptcha_cfg !== 'undefined') {{
                        Object.keys(___grecaptcha_cfg.clients).forEach(function(key) {{
                            var client = ___grecaptcha_cfg.clients[key];
                            Object.keys(client).forEach(function(clientKey) {{
                                var item = client[clientKey];
                                if (item && item.callback) {{
                                    try {{
                                        item.callback("{token}");
                                    }} catch(e) {{}}
                                }}
                            }});
                        }});
                    }}
                ''')
                
                # Also try window callback
                self.driver.execute_script(f'''
                    if (typeof window.captchaCallback === 'function') {{
                        window.captchaCallback("{token}");
                    }}
                    if (typeof window.onRecaptchaSuccess === 'function') {{
                        window.onRecaptchaSuccess("{token}");
                    }}
                ''')
                
                print("    [+] ✅ reCAPTCHA token injected successfully!")
                time.sleep(2)
                
                # Try clicking submit/continue button to trigger form submission
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], button.continue, button.submit")
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            print("    [+] Clicked submit button to trigger validation")
                            break
                except:
                    pass
                
                return True
                
            except Exception as e:
                error_msg = str(e)
                if "ERROR_ZERO_BALANCE" in error_msg:
                    print("    [!] ❌ 2Captcha balance is $0 - add funds at 2captcha.com")
                elif "ERROR_CAPTCHA_UNSOLVABLE" in error_msg:
                    print("    [!] ❌ 2Captcha couldn't solve this CAPTCHA")
                else:
                    print(f"    [!] ❌ 2Captcha error: {e}")
                
                print("    [*] Falling back to manual solve (30 seconds)...")
                time.sleep(30)
                return True
            
        except Exception as e:
            print(f"    [!] CAPTCHA handler error: {e}")
            self.driver.switch_to.default_content()
            return True  # Continue anyway

    def handle_error_popup(self):
        """Handle 'Something went wrong' error popup by clicking 'Try again'"""
        try:
            page_source = self.driver.page_source.lower()
            
            if "something went wrong" in page_source or "systems are having some trouble" in page_source:
                print("    [!] Error popup detected - clicking 'Try again'...")
                
                # Try to find and click the "Try again" button
                try_again_selectors = [
                    "//button[contains(text(),'Try again')]",
                    "//button[normalize-space()='Try again']",
                    "//button[contains(@class,'primary')][contains(text(),'Try')]",
                    "//a[contains(text(),'Try again')]",
                    "//span[contains(text(),'Try again')]/ancestor::button",
                ]
                
                for xpath in try_again_selectors:
                    try:
                        btn = self.driver.find_element(By.XPATH, xpath)
                        if btn.is_displayed():
                            btn.click()
                            print("    [+] Clicked 'Try again'")
                            time.sleep(3)
                            return True
                    except:
                        continue
                
                # Also try clicking by CSS for the primary button in the modal
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                    for btn in buttons:
                        if "try again" in btn.text.lower():
                            btn.click()
                            print("    [+] Clicked 'Try again' (CSS)")
                            time.sleep(3)
                            return True
                except:
                    pass
        except:
            pass
        return False

    def handle_cloudflare_verification(self):
        """Handle Cloudflare Turnstile verification using 2Captcha"""
        try:
            # Check if we're on a Cloudflare verification page
            page_source = self.driver.page_source
            page_lower = page_source.lower()
            
            if "additional verification" not in page_lower and "cloudflare" not in page_lower and "turnstile" not in page_lower and "verify you are human" not in page_lower:
                return True  # No Cloudflare challenge
            
            print("    [!] ⚠️ Cloudflare Turnstile verification detected!")
            
            # Check if 2Captcha is available
            api_key = self.config.get("TWOCAPTCHA_API_KEY", "")
            
            if not TWOCAPTCHA_AVAILABLE or not api_key:
                print("    [!] 2Captcha not available - trying manual click...")
                # Try to click the checkbox manually
                try:
                    # Look for Turnstile iframe
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        src = iframe.get_attribute("src") or ""
                        if "turnstile" in src.lower() or "challenges.cloudflare.com" in src.lower():
                            self.driver.switch_to.frame(iframe)
                            time.sleep(1)
                            checkbox = self.driver.find_element(By.CSS_SELECTOR, "input[type='checkbox'], .cb-i")
                            checkbox.click()
                            print("    [+] Clicked Turnstile checkbox")
                            self.driver.switch_to.default_content()
                            time.sleep(5)
                            break
                except:
                    self.driver.switch_to.default_content()
                
                # Wait and check if it resolved
                for i in range(15):
                    time.sleep(2)
                    new_source = self.driver.page_source.lower()
                    if "additional verification" not in new_source and "verify you are human" not in new_source:
                        print("    [+] ✅ Verification completed!")
                        return True
                    if i % 3 == 0:
                        print(f"    [*] Waiting for manual verification... ({(i+1)*2}/30 sec)")
                
                return False
            
            # Find Turnstile sitekey
            sitekey = None
            
            # Method 1: From div data attribute
            turnstile_divs = self.driver.find_elements(By.CSS_SELECTOR, "[data-sitekey], .cf-turnstile")
            for div in turnstile_divs:
                sk = div.get_attribute("data-sitekey")
                if sk:
                    sitekey = sk
                    break
            
            # Method 2: From page source
            if not sitekey:
                match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_source)
                if match:
                    sitekey = match.group(1)
            
            # Method 3: From iframe src
            if not sitekey:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    src = iframe.get_attribute("src") or ""
                    if "turnstile" in src.lower() or "challenges.cloudflare.com" in src.lower():
                        match = re.search(r'k=([^&]+)', src)
                        if match:
                            sitekey = match.group(1)
                            break
            
            if not sitekey:
                print("    [!] Could not find Turnstile sitekey - waiting for manual solve...")
                time.sleep(30)
                return True
            
            print(f"    [*] Found Turnstile sitekey: {sitekey[:20]}...")
            print("    [*] 🔄 Sending to 2Captcha Turnstile solver...")
            print("    [*] This may take 15-45 seconds...")
            
            try:
                solver = TwoCaptcha(api_key)
                
                # Solve Turnstile
                result = solver.turnstile(
                    sitekey=sitekey,
                    url=self.driver.current_url
                )
                
                token = result['code']
                print(f"    [+] ✅ 2Captcha solved Turnstile! Token: {token[:50]}...")
                
                # Inject the token
                # Method 1: Find the response input and set it
                self.driver.execute_script(f'''
                    var inputs = document.querySelectorAll('[name="cf-turnstile-response"], input[name*="turnstile"]');
                    inputs.forEach(function(el) {{
                        el.value = "{token}";
                    }});
                ''')
                
                # Method 2: Try to trigger callback
                self.driver.execute_script(f'''
                    if (typeof turnstile !== 'undefined' && turnstile.getResponse) {{
                        // Try to set response
                    }}
                    // Trigger form submit or callback
                    var forms = document.querySelectorAll('form');
                    if (forms.length > 0) {{
                        // Form will validate on submit
                    }}
                ''')
                
                # Method 3: Click any submit/verify buttons
                try:
                    verify_btns = self.driver.find_elements(By.XPATH, 
                        "//button[contains(text(),'Verify')] | //button[contains(text(),'Submit')] | //input[@type='submit']")
                    for btn in verify_btns:
                        if btn.is_displayed():
                            btn.click()
                            print("    [+] Clicked verify/submit button")
                            break
                except:
                    pass
                
                print("    [+] ✅ Turnstile token injected!")
                time.sleep(3)
                
                # Check if page changed
                new_source = self.driver.page_source.lower()
                if "additional verification" not in new_source:
                    print("    [+] ✅ Cloudflare verification passed!")
                    return True
                
                # If still on verification page, try refreshing
                print("    [*] Refreshing page to apply token...")
                self.driver.refresh()
                time.sleep(3)
                return True
                
            except Exception as e:
                error_msg = str(e)
                if "ERROR_ZERO_BALANCE" in error_msg:
                    print("    [!] ❌ 2Captcha balance is $0 - add funds at 2captcha.com")
                else:
                    print(f"    [!] ❌ 2Captcha Turnstile error: {e}")
                
                print("    [*] Waiting for manual verification (30 sec)...")
                time.sleep(30)
                return True
                
        except Exception as e:
            print(f"    [!] Cloudflare handler error: {e}")
            self.driver.switch_to.default_content()
        
        return True

    def fill_form_fields(self, applying_job_title):
        """Fill in any form fields and screening questions on Indeed application"""
        try:
            experience_title = JOB_TITLES[0] if JOB_TITLES else "Project Manager"
            salary = str(EXPECTED_SALARY) if EXPECTED_SALARY else "100000"
            
            # ============================================
            # RADIO BUTTONS - Work Rights (Australian Citizen)
            # ============================================
            citizen_options = [
                "//input[@type='radio'][following-sibling::*[contains(text(),'Australian Citizen')]]",
                "//input[@type='radio'][..//*[contains(text(),'Australian Citizen')]]",
                "//label[contains(text(),'Australian Citizen')]//input[@type='radio']",
                "//label[contains(text(),'Australian Citizen')]/preceding-sibling::input[@type='radio']",
                "//span[contains(text(),'Australian Citizen')]/ancestor::label//input[@type='radio']",
                "//*[contains(text(),'Australian Citizen')]/ancestor::label",
            ]
            
            for xpath in citizen_options:
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    if element.is_displayed():
                        element.click()
                        print("    [+] Selected: Australian Citizen")
                        break
                except:
                    continue
            
            # ============================================
            # RADIO BUTTONS - Yes to participating in medical/drug tests
            # ============================================
            yes_participate_options = [
                "//input[@type='radio'][following-sibling::*[contains(text(),'Yes, I am willing')]]",
                "//input[@type='radio'][..//*[contains(text(),'Yes, I am willing')]]",
                "//label[contains(text(),'Yes, I am willing')]//input[@type='radio']",
                "//label[contains(text(),'Yes, I am willing')]",
                "//span[contains(text(),'Yes, I am willing')]/ancestor::label",
            ]
            
            for xpath in yes_participate_options:
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    if element.is_displayed():
                        element.click()
                        print("    [+] Selected: Yes, willing to participate")
                        break
                except:
                    continue
            
            # ============================================
            # RADIO BUTTONS - Yes to acknowledgment (true and correct info)
            # ============================================
            # Find all Yes radio buttons and click them for acknowledgments
            try:
                # Multiple approaches to find "Yes" options
                yes_selectors = [
                    "//label[normalize-space()='Yes']",
                    "//label[text()='Yes']",
                    "//span[text()='Yes']/ancestor::label",
                    "//input[@type='radio']/following-sibling::*[text()='Yes']",
                    "//input[@type='radio'][following-sibling::label[text()='Yes']]",
                ]
                
                for xpath in yes_selectors:
                    try:
                        yes_elements = self.driver.find_elements(By.XPATH, xpath)
                        for elem in yes_elements:
                            try:
                                if elem.is_displayed():
                                    # Scroll into view and click
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                    time.sleep(0.3)
                                    elem.click()
                                    print("    [+] Selected: Yes (acknowledgment)")
                            except:
                                continue
                    except:
                        continue
                
                # Also try clicking radio buttons directly that are near "Yes" text
                try:
                    all_radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                    for radio in all_radios:
                        try:
                            # Check if this radio is associated with "Yes"
                            parent = radio.find_element(By.XPATH, "./..")
                            if parent.text.strip() == "Yes" and not radio.is_selected():
                                radio.click()
                                print("    [+] Selected: Yes radio button")
                        except:
                            continue
                except:
                    pass
                    
            except:
                pass
            
            # ============================================
            # RADIO BUTTONS - Aboriginal/Torres Strait Islander (Select NO)
            # ============================================
            try:
                aboriginal_no_selectors = [
                    "//label[normalize-space()='No'][preceding::*[contains(text(),'Aboriginal')]]",
                    "//*[contains(text(),'Aboriginal')]//following::label[normalize-space()='No'][1]",
                    "//*[contains(text(),'Aboriginal')]//following::input[@type='radio'][2]",  # Usually 2nd option is No
                    "//input[@type='radio'][following-sibling::*[text()='No']]",
                    "//label[text()='No']//input[@type='radio']",
                    "//span[text()='No']/ancestor::label",
                ]
                
                # Check if this is the Aboriginal question page
                page_text = self.driver.page_source
                if "Aboriginal" in page_text or "Torres Strait" in page_text:
                    # First, make sure we DON'T click Yes - uncheck if selected
                    try:
                        yes_checkbox = self.driver.find_element(By.XPATH, 
                            "//*[contains(text(),'Aboriginal')]//following::input[@type='checkbox'][1]")
                        if yes_checkbox.is_selected():
                            yes_checkbox.click()
                            print("    [+] Unchecked 'Yes' for Aboriginal question")
                            time.sleep(0.3)
                    except:
                        pass
                    
                    # Try to find and click "No" option
                    for xpath in aboriginal_no_selectors:
                        try:
                            elem = self.driver.find_element(By.XPATH, xpath)
                            if elem.is_displayed():
                                # Check if it's a checkbox or label
                                if elem.tag_name == "input":
                                    if not elem.is_selected():
                                        elem.click()
                                        print("    [+] Selected: No (not Aboriginal/Torres Strait Islander)")
                                        break
                                else:
                                    elem.click()
                                    print("    [+] Selected: No (not Aboriginal/Torres Strait Islander)")
                                    break
                        except:
                            continue
                    
                    # Also try clicking the No checkbox directly
                    try:
                        checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                        for i, cb in enumerate(checkboxes):
                            try:
                                parent_text = cb.find_element(By.XPATH, "./..").text.strip()
                                if parent_text == "No":
                                    if not cb.is_selected():
                                        cb.click()
                                        print("    [+] Checked: No (Aboriginal question)")
                            except:
                                continue
                    except:
                        pass
            except:
                pass
            
            # ============================================
            # TEXT FIELDS - Gender
            # ============================================
            try:
                gender_inputs = [
                    "//input[contains(@id,'gender')]",
                    "//input[contains(@name,'gender')]",
                    "//*[contains(text(),'gender')]/following::input[1]",
                    "//*[contains(text(),'Gender')]/following::input[1]",
                    "//label[contains(text(),'gender')]/..//input",
                ]
                
                for xpath in gender_inputs:
                    try:
                        field = self.driver.find_element(By.XPATH, xpath)
                        if field.is_displayed():
                            current_val = field.get_attribute("value") or ""
                            if current_val == "":
                                field.clear()
                                field.send_keys("Male")
                                print("    [+] Filled Gender: Male")
                                break
                    except:
                        continue
            except:
                pass
            
            # ============================================
            # CHECKBOXES - Agree/Privacy Policy/Terms
            # ============================================
            try:
                agree_selectors = [
                    "//input[@type='checkbox'][following-sibling::*[contains(text(),'Agree')]]",
                    "//input[@type='checkbox'][..//*[contains(text(),'Agree')]]",
                    "//label[contains(text(),'Agree')]//input[@type='checkbox']",
                    "//label[contains(text(),'Agree')]",
                    "//span[contains(text(),'Agree')]/ancestor::label",
                    "//input[@type='checkbox'][ancestor::*[contains(text(),'privacy')]]",
                    "//input[@type='checkbox'][ancestor::*[contains(text(),'Privacy')]]",
                    "//*[contains(text(),'checking this box')]/following::input[@type='checkbox'][1]",
                    "//*[contains(text(),'checking this box')]//preceding::input[@type='checkbox'][1]",
                ]
                
                for xpath in agree_selectors:
                    try:
                        elem = self.driver.find_element(By.XPATH, xpath)
                        if elem.is_displayed():
                            if elem.tag_name == "input":
                                if not elem.is_selected():
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                    time.sleep(0.2)
                                    elem.click()
                                    print("    [+] Checked: Agree/Privacy Policy checkbox")
                                    break
                            else:
                                # It's a label, click it
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                time.sleep(0.2)
                                elem.click()
                                print("    [+] Clicked: Agree label")
                                break
                    except:
                        continue
                
                # Also look for any unchecked checkboxes near "agree" or "privacy" text
                try:
                    all_checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                    for cb in all_checkboxes:
                        try:
                            if not cb.is_displayed() or cb.is_selected():
                                continue
                            # Check parent text
                            parent = cb.find_element(By.XPATH, "./ancestor::*[5]")
                            parent_text = parent.text.lower()
                            if "agree" in parent_text or "privacy" in parent_text or "checking this box" in parent_text:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cb)
                                time.sleep(0.2)
                                cb.click()
                                print("    [+] Checked Agree checkbox (by context)")
                        except:
                            continue
                except:
                    pass
            except:
                pass
            
            # ============================================
            # TEXT FIELDS - Notice Period
            # ============================================
            notice_inputs = [
                "//input[contains(@id,'notice')]",
                "//input[contains(@name,'notice')]",
                "//*[contains(text(),'notice period')]/following::input[1]",
                "//*[contains(text(),'Notice period')]/following::input[1]",
            ]
            
            for xpath in notice_inputs:
                try:
                    field = self.driver.find_element(By.XPATH, xpath)
                    if field.is_displayed() and field.get_attribute("value") == "":
                        field.clear()
                        field.send_keys("2 weeks")
                        print("    [+] Filled Notice period: 2 weeks")
                        break
                except:
                    continue
            
            # ============================================
            # TEXT FIELDS - Salary Expectations
            # ============================================
            salary_inputs = [
                "//input[contains(@id,'salary')]",
                "//input[contains(@name,'salary')]",
                "//*[contains(text(),'salary')]/following::input[1]",
                "//*[contains(text(),'Salary')]/following::input[1]",
                "//*[contains(text(),'rate expectations')]/following::input[1]",
            ]
            
            for xpath in salary_inputs:
                try:
                    field = self.driver.find_element(By.XPATH, xpath)
                    if field.is_displayed() and field.get_attribute("value") == "":
                        field.clear()
                        field.send_keys(salary)
                        print(f"    [+] Filled Salary: {salary}")
                        break
                except:
                    continue
            
            # ============================================
            # TEXT FIELDS - Job Title / Experience (CRITICAL - fix wrong values)
            # ============================================
            job_inputs = [
                "//input[contains(@id,'jobTitle')]",
                "//input[contains(@name,'jobTitle')]",
                "//*[contains(text(),'Job title')]/following::input[1]",
                "//label[contains(text(),'Job title')]/following::input[1]",
                "//label[contains(text(),'Job title')]/..//input",
            ]
            
            for xpath in job_inputs:
                try:
                    field = self.driver.find_element(By.XPATH, xpath)
                    if field.is_displayed():
                        current_val = field.get_attribute("value") or ""
                        # Fix if empty OR if contains a wrong value (like salary)
                        if current_val == "" or current_val.isdigit() or current_val == salary:
                            field.clear()
                            field.send_keys(experience_title)
                            print(f"    [+] Filled Job title: {experience_title} (was: '{current_val}')")
                            break
                except:
                    continue
            
            # ============================================
            # TEXT FIELDS - Years of Experience
            # ============================================
            years_inputs = [
                "//input[contains(@id,'years')]",
                "//input[contains(@name,'years')]",
                "//*[contains(text(),'years')]/following::input[1]",
            ]
            
            for xpath in years_inputs:
                try:
                    field = self.driver.find_element(By.XPATH, xpath)
                    if field.is_displayed() and field.get_attribute("value") == "":
                        field.clear()
                        field.send_keys("5")
                        print("    [+] Filled Years: 5")
                        break
                except:
                    continue
            
            # ============================================
            # FILL ALL EMPTY TEXT INPUTS (catch-all)
            # ============================================
            try:
                all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
                for inp in all_inputs:
                    try:
                        if not inp.is_displayed():
                            continue
                            
                        current_val = inp.get_attribute("value") or ""
                        
                        # Check what kind of field it is by looking at nearby labels
                        parent_text = ""
                        try:
                            parent_text = inp.find_element(By.XPATH, "./ancestor::*[3]").text.lower()
                        except:
                            pass
                        
                        # Also try to get the label text
                        label_text = ""
                        try:
                            label = inp.find_element(By.XPATH, "./preceding::label[1]")
                            label_text = label.text.lower()
                        except:
                            pass
                        
                        combined_text = parent_text + " " + label_text
                        
                        # Handle specific field types correctly - FIX wrong values too
                        if "job title" in combined_text or "jobtitle" in combined_text:
                            # Fix if empty OR wrong value (like salary number)
                            if current_val == "" or current_val.isdigit() or current_val == salary:
                                inp.clear()
                                inp.send_keys(experience_title)
                                print(f"    [+] Fixed Job title: {experience_title} (was: '{current_val}')")
                        elif "company" in combined_text and "salary" not in combined_text and current_val == "":
                            inp.send_keys("Previous Company")
                            print("    [+] Filled Company: Previous Company")
                        elif "notice" in combined_text and current_val == "":
                            inp.send_keys("2 weeks")
                            print("    [+] Filled Notice: 2 weeks")
                        elif ("salary" in combined_text or "rate expectation" in combined_text) and "job" not in combined_text and "title" not in combined_text:
                            if current_val == "":
                                inp.send_keys(salary)
                                print(f"    [+] Filled Salary: {salary}")
                        elif "year" in combined_text and current_val == "":
                            inp.send_keys("5")
                            print("    [+] Filled Years: 5")
                    except:
                        continue
            except:
                pass
                    
        except Exception as e:
            print(f"    [!] Form fill error: {e}")

    def apply(self, job_title, company):
        """Apply to Indeed job"""
        speed_sleep(1, "scan")
        stealth_random_pause()
        
        # First check if this is an "Apply on company site" job - SKIP these
        try:
            external_xpaths = [
                "//button[contains(., 'Apply on company site')]",
                "//a[contains(., 'Apply on company site')]",
                "//button[contains(., 'company site')]",
                "//a[contains(., 'company site')]",
            ]
            for xpath in external_xpaths:
                try:
                    external_btn = self.driver.find_element(By.XPATH, xpath)
                    if external_btn.is_displayed():
                        print("    [-] External company site. Skipping.")
                        return False
                except:
                    continue
        except:
            pass
        
        # ONLY look for "Apply now" button (the blue direct apply button)
        apply_btn = None
        
        # Priority 1: Look for the exact "Apply now" button
        apply_now_xpaths = [
            "//button[normalize-space(text())='Apply now']",
            "//button[contains(., 'Apply now')]",
            "//button[contains(@class, 'jobsearch-IndeedApplyButton')]",
            "//button[contains(@id, 'indeedApply')]",
            "//button[@data-testid='indeedApplyButton']",
        ]
        
        for xpath in apply_now_xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed() and btn.is_enabled():
                    # Double-check it's NOT "Apply on company site"
                    btn_text = btn.text.strip().lower()
                    if "company site" not in btn_text:
                        apply_btn = btn
                        print(f"    [+] Found Apply now button")
                        break
            except:
                continue
        
        # Priority 2: CSS selectors for Indeed Apply
        if not apply_btn:
            css_selectors = [
                "button.ia-IndeedApplyButton",
                "button[id*='indeedApply']",
                "button[data-testid='indeedApplyButton']",
            ]
            for sel in css_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if btn.is_displayed() and btn.is_enabled():
                        btn_text = btn.text.strip().lower()
                        if "company site" not in btn_text:
                            apply_btn = btn
                            print(f"    [+] Found Indeed Apply button")
                            break
                except:
                    continue
        
        if not apply_btn:
            print("    [-] No 'Apply now' button found (may be external site).")
            return False
        
        # GPT check before applying
        desc = self.get_description()
        if desc and OPENAI_API_KEY:
            if not self.gpt_should_apply(job_title, desc):
                print(f"    [🤖 SKIP] GPT says job doesn't match your target roles")
                return False
        
        # Click apply
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", apply_btn)
            print("    [+] Clicked Indeed Apply button")
            time.sleep(3)
        except Exception as e:
            print(f"    [-] Failed to click apply: {e}")
            return False
        
        # Handle Indeed's apply form (multi-step process)
        try:
            # Check if it opened in new tab
            time.sleep(3)
            print("    [*] Checking for new windows...")
            windows = self.driver.window_handles
            print(f"    [*] Found {len(windows)} window(s)")
            
            if len(windows) > 1:
                self.driver.switch_to.window(windows[-1])
                print("    [*] Switched to apply window")
            
            # Handle Cloudflare verification if it appears
            self.handle_cloudflare_verification()
            
            # Indeed apply form has multiple steps - keep clicking Continue/Submit
            max_steps = 10
            
            for step in range(max_steps):
                print(f"    [*] Form step {step + 1}...")
                time.sleep(3)
                
                # Check for error popup and handle it
                self.handle_error_popup()
                
                # Check for Cloudflare verification at each step
                self.handle_cloudflare_verification()
                
                # Check current URL to understand which page we're on
                current_url = self.driver.current_url.lower()
                print(f"    [*] Current URL: {current_url[:80]}...")
                
                # Check if we're REALLY done (confirmation page - very specific check)
                # Must be on a post-apply URL and have thank you text
                if "post" in current_url or "confirmation" in current_url or "complete" in current_url:
                    page_text = self.driver.page_source.lower()
                    if "thank you" in page_text or "application has been submitted" in page_text or "your application" in page_text:
                        self.successful_submits += 1
                        self.log_job(job_title, company, self.driver.current_url)
                        print(f"    [+] SUBMITTED to Indeed!")
                        print(f"    [+] Successful submissions: {self.successful_submits}")
                        
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                        
                        return True
                
                # Fill in any form fields that appear
                self.fill_form_fields(job_title)
                
                # Check for error popup after filling fields
                self.handle_error_popup()
                
                # Use GPT to answer any remaining screening questions
                if OPENAI_API_KEY:
                    self.answer_screening_questions_with_gpt()
                
                # Check for error popup after answering questions
                self.handle_error_popup()
                
                # Scroll to bottom to ensure Continue button is visible
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                print("    [*] Scrolled to bottom of page")
                
                # Check for reCAPTCHA before trying to submit
                if not self.handle_recaptcha():
                    print("    [!] CAPTCHA not solved - skipping job")
                    return False
                
                # Find and click Continue/Submit button
                button_found = False
                
                # First try: Look for the big blue Continue button specifically
                try:
                    # Indeed's Continue button is usually a prominent button
                    continue_selectors = [
                        "//button[text()='Continue']",
                        "//button[normalize-space()='Continue']",
                        "//button[contains(@class,'continue')]",
                        "//button[contains(@class,'Continue')]", 
                        "//button[contains(text(),'Continue')]",
                        "//button[text()='Submit your application']",
                        "//button[contains(text(),'Submit')]",
                        "//button[text()='Review your application']",
                    ]
                    
                    for xpath in continue_selectors:
                        try:
                            btn = self.driver.find_element(By.XPATH, xpath)
                            if btn.is_displayed() and btn.is_enabled():
                                print(f"    [*] Found Continue button via XPath")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(1)
                                try:
                                    btn.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                print(f"    [+] Clicked: {btn.text.strip()}")
                                button_found = True
                                time.sleep(2)
                                break
                        except:
                            continue
                except Exception as e:
                    print(f"    [!] XPath search error: {e}")
                
                # Second try: Get ALL buttons and find Continue/Submit
                if not button_found:
                    try:
                        all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                        print(f"    [*] Searching {len(all_buttons)} buttons...")
                        
                        for btn in all_buttons:
                            try:
                                btn_text = btn.text.strip().lower()
                                if btn_text and btn.is_displayed() and btn.is_enabled():
                                    if btn_text in ['continue', 'submit', 'submit your application', 'review your application', 'review', 'next']:
                                        print(f"    [*] Found button: '{btn.text.strip()}'")
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                        time.sleep(1)
                                        try:
                                            btn.click()
                                        except:
                                            self.driver.execute_script("arguments[0].click();", btn)
                                        print(f"    [+] Clicked: {btn.text.strip()}")
                                        button_found = True
                                        time.sleep(2)
                                        break
                            except:
                                continue
                    except Exception as e:
                        print(f"    [!] Button search error: {e}")
                
                if not button_found:
                    print(f"    [?] No Continue/Submit button found at step {step + 1}")
                    time.sleep(2)
                else:
                    # Wait for next page to load after clicking
                    time.sleep(3)
                    # Check for error popup after clicking Continue/Submit
                    if self.handle_error_popup():
                        print("    [*] Retrying after error popup...")
                        continue  # Retry this step
            
            # Final check for success - be specific about the URL
            time.sleep(2)
            current_url = self.driver.current_url.lower()
            page_text = self.driver.page_source.lower()
            
            # Only count as success if URL indicates completion
            is_success = False
            if "post" in current_url or "confirmation" in current_url or "complete" in current_url or "success" in current_url:
                if "thank you" in page_text or "application has been submitted" in page_text:
                    is_success = True
            
            # Also check for very specific success indicators
            if "your application has been sent" in page_text or "successfully submitted" in page_text:
                is_success = True
                
            if is_success:
                self.successful_submits += 1
                self.log_job(job_title, company, self.driver.current_url)
                print(f"    [+] SUBMITTED to Indeed!")
                print(f"    [+] Successful submissions: {self.successful_submits}")
                
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                return True
            
            print("    [?] Indeed form incomplete - may need manual completion")
            print(f"    [?] Final URL: {current_url[:80]}...")
            
            # Close apply window if exists
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            
            return False
            
        except Exception as e:
            print(f"    [!] Indeed apply form error: {e}")
            # Close any extra windows
            while len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return False

    def go_to_next_page(self):
        """Navigate to next page of Indeed results"""
        try:
            next_selectors = [
                "a[data-testid='pagination-page-next']",
                "a[aria-label='Next Page']",
                "a[aria-label='Next']",
                "nav a:last-child",
            ]
            
            for sel in next_selectors:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    print("[*] Next page clicked.")
                    time.sleep(3)
                    return True
                except:
                    continue
            
            # Try XPath
            try:
                next_btn = self.driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Next')]")
                self.driver.execute_script("arguments[0].click();", next_btn)
                print("[*] Next page clicked.")
                time.sleep(3)
                return True
            except:
                pass
            
            print("[!] No next page button found.")
            return False
            
        except Exception as e:
            print(f"Next page error: {e}")
            return False

    def send_summary_and_exit(self, run_start_time):
        """Helper to send WhatsApp summary and exit"""
        duration_minutes = int((time.time() - run_start_time) / 60)
        full_name = CONFIG.get("FULL_NAME", "User")
        send_whatsapp_summary(full_name, self.successful_submits, duration_minutes, self.applied_job_titles)

    def run(self):
        """Main Indeed bot loop"""
        run_start_time = time.time()  # Track start time for WhatsApp summary
        
        print("\n" + "="*50)
        print("🟣 INDEED BOT STARTED")
        print("="*50)
        print(f"Target: {MAX_JOBS} applications")
        print(f"Location: {LOCATION}")
        print(f"Job Titles: {', '.join(JOB_TITLES)}")
        print("="*50 + "\n")
        
        # Start Gmail cleanup in visible tab (runs continuously when bot starts)
        if self.gmail_cleanup:
            def gmail_cleanup_loop():
                """Gmail cleanup runs continuously in a visible tab, independent of application cycles"""
                # Wait a bit before first cleanup to let browser settle
                time.sleep(30)
                
                # Open Gmail tab first - this will be visible to the user
                if not self.gmail_cleanup.open_gmail_tab():
                    print("[Gmail] Failed to open Gmail tab, will retry later")
                    return
                
                print("[Gmail] Gmail tab opened and visible - cleanup will run continuously")
                time.sleep(5)
                
                # Run cleanup continuously every 5 minutes in the separate window
                while True:
                    try:
                        status = check_control()
                        if status == "stop":
                            print("[Gmail] Gmail cleanup stopped (bot stopped)")
                            # Close the separate window
                            if self.gmail_cleanup:
                                self.gmail_cleanup.close()
                            break
                        if status == "pause":
                            # Still run cleanup when paused (it's independent)
                            time.sleep(10)
                            continue
                        
                        # Make sure we're on the Gmail window (keep it visible)
                        if not self.gmail_cleanup.switch_to_gmail_tab():
                            print("[Gmail] Gmail window lost, reopening...")
                            if not self.gmail_cleanup.open_gmail_tab():
                                print("[Gmail] Failed to reopen Gmail window")
                                time.sleep(60)
                                continue
                        
                        # Run cleanup in the separate window
                        print("[Gmail] Running cleanup in separate Gmail window...")
                        self.gmail_cleanup.cleanup_emails(max_emails=50)
                        
                        # Wait 5 minutes before next cleanup
                        print("[Gmail] Next cleanup in 5 minutes...")
                        time.sleep(300)
                    except Exception as e:
                        print(f"[Gmail] Cleanup error: {e}")
                        time.sleep(60)  # Wait 1 minute before retry
            
            self.gmail_thread = threading.Thread(target=gmail_cleanup_loop, daemon=True)
            self.gmail_thread.start()
            print("[Gmail] Gmail cleanup started - will open visible tab and run continuously")
        
        self.ensure_logged_in()
        
        for search_title in JOB_TITLES:
            if check_control() == "stop":
                print("[!] Stop signal received. Shutting down Indeed bot...")
                self.send_summary_and_exit(run_start_time)
                return
            
            if self.successful_submits >= MAX_JOBS:
                break
            
            print(f"\n==============================")
            print(f"🟣 INDEED: Searching for '{search_title}'")
            print(f"==============================\n")
            
            search_url = build_indeed_url(search_title, LOCATION)
            print(f"[*] URL: {search_url}")
            
            self.driver.get(search_url)
            speed_sleep(3, "scan")
            
            page = 1
            
            while self.successful_submits < MAX_JOBS:
                if check_control() == "stop":
                    print("[!] Stop signal received.")
                    self.send_summary_and_exit(run_start_time)
                    return
                
                print(f"\n===== PAGE {page} =====")
                cards = self.get_job_cards()
                
                if not cards:
                    print("[!] No job cards found.")
                    break
                
                for idx, card in enumerate(cards):
                    status = check_control()
                    if status == "stop":
                        return
                    elif status == "pause":
                        print("[*] Bot paused...")
                        if not wait_while_paused():
                            return
                        print("[*] Bot resumed.")
                    
                    title = self.get_job_title(card)
                    company = self.get_company_name(card)
                    
                    if not title_matches(title):
                        print(f"    [-] SKIPPED (title mismatch): {title}")
                        continue
                    
                    if is_title_blocked(title):
                        print(f"    [🚫] BLOCKED (title): {title}")
                        continue
                    
                    if is_company_blocked(company):
                        print(f"    [🚫] BLOCKED (company): {company}")
                        continue
                    
                    # Check for "Easily apply" badge BEFORE clicking
                    if not self.has_easily_apply(card):
                        print(f"    [-] SKIPPED (no Easily Apply): {title}")
                        continue
                    
                    if self.successful_submits >= MAX_JOBS:
                        break
                    
                    print(f"\n[*] Indeed Job {idx + 1}: {title} | {company} ✓ Easily Apply")
                    
                    stealth_random_pause()
                    
                    if self.open_job(card):
                        speed_sleep(2, "scan")
                        self.apply(title, company)
                    
                    job_cooldown()
                
                if self.successful_submits >= MAX_JOBS:
                    break
                
                if not self.go_to_next_page():
                    break
                
                page += 1
        
        print(f"\n[*] INDEED BOT COMPLETE — Successfully submitted {self.successful_submits} applications.")
        
        # Send WhatsApp summary
        duration_minutes = int((time.time() - run_start_time) / 60)
        full_name = CONFIG.get("FULL_NAME", "User")
        send_whatsapp_summary(full_name, self.successful_submits, duration_minutes, self.applied_job_titles)


def main():
    """Main entry point for Indeed bot"""
    # Check if Indeed is enabled
    if not CONFIG.get("USE_INDEED", False):
        print("[*] Indeed is disabled in config. Skipping...")
        return
    
    print("[*] Starting Indeed bot...")
    driver = init_browser()
    
    try:
        bot = IndeedBot(driver)
        bot.run()
    except Exception as e:
        print(f"[!] Indeed bot error: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    main()


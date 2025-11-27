import os
import sys
import time
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Excel Logging
import openpyxl
from openpyxl import Workbook
from datetime import datetime

# ============================================
# DIRECT PATHS
# ============================================
CONFIG_FILE  = "config.json"
CONTROL_FILE = "control.json"
LOG_FILE     = "log.txt"
JOB_LOG_FILE = "job_log.xlsx"
PROFILE_DIR  = "chrome_seek_profile"
LOGO_FILE    = "seekmate_logo.png"

# Ensure directories/files exist
if not os.path.exists(PROFILE_DIR):
    os.makedirs(PROFILE_DIR, exist_ok=True)

# ============================================
# Load config safely
# ============================================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ============================================
# Pause/Stop control file
# ============================================
def write_control(pause=None, stop=None):
    data = {"pause": False, "stop": False}

    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except:
            pass

    if pause is not None:
        data["pause"] = pause
    if stop is not None:
        data["stop"] = stop

    with open(CONTROL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ============================================
# INIT BROWSER (REQUIRED FOR CHROME TO OPEN)
# ============================================
def init_browser():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(f"user-data-dir={PROFILE_DIR}")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-extensions")

    # Force correct Chrome path (if needed)
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        chrome_options.binary_location = chrome_path

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(3)
    return driver


# ============================================
# Safe print → writes to GUI log
# (GUI will override this through a callback)
# ============================================
_gui_log_callback = None

def set_gui_log_callback(func):
    global _gui_log_callback
    _gui_log_callback = func

def print(*args, **kwargs):
    text = " ".join(str(a) for a in args)

    # write to file
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except:
        pass

    # write to GUI log if callback available
    if _gui_log_callback:
        try:
            _gui_log_callback(text)
        except:
            pass

    # still print to console (dev mode)
    try:
        sys.__stdout__.write(text + "\n")
    except:
        pass
# ============================================
# GUI CLASS — Full Version (unchanged layout)
# ============================================
class SeekMateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekMate AI — Auto Apply Launcher")
        self.root.geometry("1500x950")
        self.root.configure(bg="white")

        # DATA
        self.config = load_config()
        self.paused = False
        self.bot_thread = None
        self.bot_instance = None

        self.start_time = None
        self.timer_running = False
        self.money_running = False
        self.money_saved = 0.0

        # Link GUI print to console
        set_gui_log_callback(self._gui_log)

        # MAIN SPLIT LAYOUT
        container = tk.Frame(root, bg="white")
        container.pack(fill="both", expand=True)

        left = tk.Frame(container, bg="white")
        left.pack(side="left", fill="y", padx=20, pady=10)

        right = tk.Frame(container, bg="white")
        right.pack(side="right", fill="both", expand=True, padx=20, pady=10)

        # =====================================================
        # EXECUTIVE BLACK HEADER BAR
        # =====================================================
        header = tk.Frame(self.root, bg="black", height=60)
        header.place(relx=0, rely=0, relwidth=1)

        tk.Label(
            header,
            text="SEEKMATE AI — PROFESSIONAL EDITION by Ash",
            bg="black",
            fg="white",
            font=("Arial", 20, "bold")
        ).pack(side="left", padx=20)

        self.header_status = tk.Label(
            header,
            text="● IDLE",
            bg="black",
            fg="grey",
            font=("Arial", 14, "bold")
        )
        self.header_status.pack(side="right", padx=20)

        self.header_money = tk.Label(
            header,
            text="Money Saved: $0.00",
            bg="black",
            fg="white",
            font=("Arial", 14)
        )
        self.header_money.pack(side="right", padx=20)

        self.header_timer = tk.Label(
            header,
            text="00:00:00",
            bg="black",
            fg="white",
            font=("Arial", 14)
        )
        self.header_timer.pack(side="right", padx=20)

        # OFFSET BELOW HEADER
        offset = tk.Frame(self.root, bg="white", height=70)
        offset.pack()

        # =====================================================
        # LOGO
        # =====================================================
        if os.path.exists(LOGO_FILE):
            img = Image.open(LOGO_FILE).resize((165, 165))
            self.logo = ImageTk.PhotoImage(img)
            tk.Label(left, image=self.logo, bg="white").pack()
        else:
            tk.Label(left, text="SeekMate AI", font=("Arial", 26, "bold"), bg="white").pack(pady=10)

        # =====================================================
        # FORM SECTION
        # =====================================================
        form = tk.Frame(left, bg="white")
        form.pack()

        # Helper field
        def field(label, key, default=None):
            tk.Label(form, text=label, bg="white").pack(anchor="w")
            entry = tk.Entry(form)
            entry.insert(0, self.config.get(key, default))
            entry.pack(fill="x", pady=4)
            return entry

        # Fields
        self.full_name_entry      = field("Full Name", "FULL_NAME")
        self.background_bio_entry = field("Background Bio", "BACKGROUND_BIO")
        self.seek_email_entry     = field("SEEK Email", "SEEK_EMAIL")

        tk.Label(form, text="Location", bg="white").pack(anchor="w")
        self.location_var = tk.StringVar()
        locations = [
            "Brisbane, Australia", "Gold Coast, Australia", "Sydney, Australia",
            "Melbourne, Australia", "Perth, Australia", "Adelaide, Australia",
            "Canberra, Australia", "Hobart, Australia", "Darwin, Australia"
        ]
        self.location_dropdown = ttk.Combobox(
            form, textvariable=self.location_var,
            values=locations, state="readonly"
        )
        self.location_dropdown.set(self.config.get("LOCATION", "Brisbane, Australia"))
        self.location_dropdown.pack(fill="x", pady=4)

        # Job rotation
        tk.Label(form, text="Job Titles (Rotation)", bg="white").pack(anchor="w")
        self.job_entry = tk.Entry(form)
        raw = self.config.get("JOB_TITLES", [])
        self.job_entry.insert(0, ", ".join(raw))
        self.job_entry.pack(fill="x", pady=4)

        # Presets
        preset_frame = tk.Frame(form, bg="white")
        preset_frame.pack()

        presets = [
            ("Project/Program", ["Project Manager", "Senior PM", "Program Manager"]),
            ("Change/Transformation", ["Change Manager", "OCM Lead", "Transformation Manager"]),
            ("BDM", ["BDM", "Sales Manager", "Account Manager"]),
            ("Director Roles", ["Director", "Operations Director", "Program Director"]),
            ("Office Admin", ["Office Manager", "EA", "Admin Manager"]),
            ("IT & Digital", ["IT Manager", "Service Delivery Manager", "Digital Manager"]),
        ]

        for i, (name, roles) in enumerate(presets):
            tk.Button(
                preset_frame,
                text=name,
                width=20,
                command=lambda r=roles: self.set_presets(r)
            ).grid(row=i // 2, column=i % 2, padx=4, pady=4)

        self.max_entry     = field("Max Jobs", "MAX_JOBS", default=50)
        self.salary_entry  = field("Expected Salary (AUD)", "EXPECTED_SALARY", default=100000)

        # API KEY
        api = tk.Frame(form, bg="white")
        api.pack(fill="x")
        tk.Label(api, text="OpenAI API Key", bg="white").grid(row=0, column=0, sticky="w")
        self.api_entry = tk.Entry(api, show="*")
        self.api_entry.insert(0, self.config.get("OPENAI_API_KEY", ""))
        self.api_entry.grid(row=1, column=0, sticky="ew")
        tk.Button(api, text="Show", command=self.toggle_api).grid(row=1, column=1)
        tk.Button(api, text="💾 Save API", bg="#0078ff", fg="white",
                  command=self.save_api).grid(row=1, column=2)
        api.grid_columnconfigure(0, weight=1)

        # =====================================================
        # MONEY SAVED (BIG PANEL)
        # =====================================================
        money_panel = tk.LabelFrame(left, text="💰 MONEY SAVED", bg="white", font=("Arial", 14, "bold"))
        money_panel.pack(fill="x", pady=10)

        self.money_label = tk.Label(
            money_panel, text="$0.00", font=("Arial", 26, "bold"), bg="white", fg="green"
        )
        self.money_label.pack()

        # =====================================================
        # CONTROL BUTTONS
        # =====================================================
        controls = tk.Frame(left, bg="white")
        controls.pack(pady=10)

        self.start_btn = tk.Button(
            controls, text="▶ START", bg="#0cb600", fg="white",
            font=("Arial", 14, "bold"), command=self.start_bot_threaded, width=13
        )
        self.start_btn.grid(row=0, column=0, padx=5)

        self.pause_btn = tk.Button(
            controls, text="⏸ PAUSE", bg="#ffae00", fg="white",
            font=("Arial", 14, "bold"), command=self.pause_bot_threaded, width=13
        )
        self.pause_btn.grid(row=0, column=1, padx=5)

        tk.Button(
            controls, text="⛔ STOP", bg="#d40000", fg="white",
            font=("Arial", 14, "bold"), width=13, command=self.stop_bot
        ).grid(row=0, column=2, padx=5)

        tk.Button(
            controls, text="🔍 RUN TEST", bg="#0078ff", fg="white",
            font=("Arial", 14, "bold"), width=13, command=self.run_test
        ).grid(row=1, column=0, columnspan=3, pady=8)

        self.counter_label = tk.Label(left, text="Jobs Applied: 0",
                                      font=("Arial", 15, "bold"), bg="white")
        self.counter_label.pack(pady=10)

        # =====================================================
        # LOG VIEWER
        # =====================================================
        right_header = tk.Frame(right, bg="white")
        right_header.pack(fill="x")

        tk.Label(right_header, text="Logs", bg="white", font=("Arial", 14, "bold")).pack(side="left")

        self.filter_var = tk.StringVar()
        tk.Entry(right_header, textvariable=self.filter_var, width=20).pack(side="left", padx=5)
        tk.Button(right_header, text="Filter", command=self.apply_filter).pack(side="left")

        self.wrap_enabled = True
        tk.Button(right_header, text="Wrap: ON", command=self.toggle_wrap).pack(side="left", padx=5)

        tk.Button(right_header, text="Clear", command=self.clear_log).pack(side="left", padx=5)

        self.console = tk.Text(
            right, bg="#f5f5f5", fg="black", wrap="word", font=("Consolas", 11)
        )
        self.console.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(right, command=self.console.yview)
        scroll.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=scroll.set)

    # ============================================================
    # GUI Logic Below (unchanged)
    # ============================================================
    def _gui_log(self, text):
        self.console.insert("end", text + "\n")
        self.console.see("end")

    def set_presets(self, titles):
        self.job_entry.delete(0, tk.END)
        self.job_entry.insert(0, ", ".join(titles))

    def toggle_api(self):
        self.api_entry.config(show="" if self.api_entry.cget("show") == "*" else "*")

    def save_api(self):
        self.config["OPENAI_API_KEY"] = self.api_entry.get()
        save_config(self.config)
        self._gui_log("[SUCCESS] API Key saved.")

    def apply_filter(self):
        keyword = self.filter_var.get().strip().lower()
        content = self.console.get("1.0", tk.END)
        self.console.delete("1.0", tk.END)
        for line in content.splitlines():
            if keyword in line.lower():
                self.console.insert(tk.END, line + "\n")

    def toggle_wrap(self):
        self.wrap_enabled = not self.wrap_enabled
        self.console.config(wrap="word" if self.wrap_enabled else "none")

    def clear_log(self):
        self.console.delete("1.0", tk.END)

    def run_test(self):
        self._gui_log("[INFO] Running system test…")
        if not self.api_entry.get().strip():
            self._gui_log("[ERROR] API Key missing.")
        else:
            self._gui_log("[SUCCESS] API Key present.")

    # ============================================================
    # Save Config
    # ============================================================
    def save_all_config(self):
        self.config["FULL_NAME"] = self.full_name_entry.get().strip()
        self.config["LOCATION"] = self.location_var.get().strip()
        self.config["BACKGROUND_BIO"] = self.background_bio_entry.get().strip()
        self.config["SEEK_EMAIL"] = self.seek_email_entry.get().strip()
        self.config["JOB_TITLES"] = [j.strip() for j in self.job_entry.get().split(",") if j.strip()]
        self.config["MAX_JOBS"] = int(self.max_entry.get().strip())
        self.config["EXPECTED_SALARY"] = int(self.salary_entry.get().strip())
        self.config["OPENAI_API_KEY"] = self.api_entry.get().strip()

        save_config(self.config)
        self._gui_log("[SUCCESS] Config saved.")

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
                time.sleep(0.5)
                ta.clear()
                ta.send_keys(answer)
                time.sleep(0.3)

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

                    # --- RULE 1: YES/NO QUESTIONS ---
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
                                time.sleep(0.2)
                                break
                        continue

                    # --- RULE 2: EXPERIENCE ---
                    if "experience" in question_text:
                        r, lbl = options[-1]  # highest experience
                        self.driver.execute_script("arguments[0].click();", r)
                        time.sleep(0.2)
                        continue

                    # --- RULE 3: KNOWLEDGE ---
                    if any(x in question_text for x in ["familiar", "knowledge", "domain", "government"]):
                        r, lbl = options[-1]
                        self.driver.execute_script("arguments[0].click();", r)
                        time.sleep(0.2)
                        continue

                    # --- RULE 4: POLICE CHECK ---
                    if "police" in question_text or "check" in question_text:
                        for r, lbl in options:
                            if "yes" in lbl:
                                self.driver.execute_script("arguments[0].click();", r)
                                time.sleep(0.2)
                                break
                        continue

                    # --- RULE 5: RELOCATION ---
                    if "relocat" in question_text or "move" in question_text:
                        for r, lbl in options:
                            if "already" in lbl or "yes" in lbl:
                                self.driver.execute_script("arguments[0].click();", r)
                                time.sleep(0.2)
                                break
                        continue

                    # --- DEFAULT RULE (if not negative) ---
                    for r, lbl in reversed(options):
                        if not lbl.startswith("no"):
                            self.driver.execute_script("arguments[0].click();", r)
                            time.sleep(0.2)
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
                    time.sleep(0.2)
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
                    time.sleep(0.2)
                except:
                    continue

        except Exception as e:
            print("Checkbox handler error:", e)

    # ---------- DROPDOWNS (Choose MOST senior option + Citizenship patch) ----------
    def answer_dropdowns(self):
        try:
            selects = self.driver.find_elements(By.TAG_NAME, "select")

            for s in selects:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", s)
                    time.sleep(0.3)

                    options = s.find_elements(By.TAG_NAME, "option")
                    if len(options) < 2:
                        continue

                    # ---------- CITIZENSHIP PATCH ----------
                    label_text = ""
                    try:
                        label = s.find_element(By.XPATH, "./preceding::label[1]")
                        label_text = label.text.strip().lower()
                    except:
                        pass

                    if "right to work" in label_text or "best describes your right" in label_text:
                        for opt in options:
                            if "australian citizen" in opt.text.lower():
                                opt.click()
                                print("    [+] Selected: Australian citizen")
                                break
                        continue
                    # ---------------------------------------

                    # ---------- EXISTING SENIOR SELECTION LOGIC ----------
                    selected = False
                    keywords = ["more", "5", "5+", "senior"]

                    for opt in options:
                        label = opt.text.strip().lower()
                        if any(k in label for k in keywords):
                            opt.click()
                            selected = True
                            break

                    if not selected:
                        options[-1].click()

                    time.sleep(0.2)

                except:
                    continue

        except Exception as e:
            print("Dropdown handler error:", e)

    # ---------- APPLY FLOW ----------
    def apply(self, job_title, company):
        time.sleep(2)

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
        time.sleep(1)

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
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", btn)
                    print("    [+] Clicked apply button:", sel)
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            print("    [-] No apply button found.")
            return

        time.sleep(3)
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
            time.sleep(3)
        except:
            print("    [-] Cannot continue from page 1.")
            return

        # --------------------------
        # PAGE 2+ — full automation
        # --------------------------
        for _ in range(6):
            self.answer_questions(job_title, company, desc)
            self.answer_radio_buttons()
            self.answer_checkboxes()
            self.answer_dropdowns()

            try:
                cont = self.driver.find_element(
                    By.XPATH,
                    "//button[contains(., 'Continue') or contains(., 'Next')]"
                )
                self.driver.execute_script("arguments[0].click();", cont)
                print("    [+] Continue")
                time.sleep(3)
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
            time.sleep(3)

            # LOG SUCCESSFUL SUBMISSION
            try:
                current_url = self.driver.current_url
                self.log_job(job_title, company, current_url)
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
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    print("[*] Next page clicked.")
                    time.sleep(3)
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
        self.open_search()

        applied = 0
        page = 1

        # >>> STOP ONLY AFTER REAL SUCCESSFUL SUBMISSIONS
        while self.successful_submits < MAX_JOBS:
            print(f"\n===== PAGE {page} =====")
            cards = self.get_job_cards()

            if not cards:
                print("[!] No job cards found.")
                break

            for idx, card in enumerate(cards):

                if self.successful_submits >= MAX_JOBS:
                    break

                try:
                    title = card.find_element(By.CSS_SELECTOR, "[data-automation='jobTitle']").text
                except:
                    title = "Unknown"

                try:
                    company = card.find_element(By.CSS_SELECTOR, "[data-automation='jobCompany']").text
                except:
                    company = "Unknown"

                print(f"\n[*] Job {idx + 1}: {title} | {company}")

                if not self.open_job(card):
                    continue

                time.sleep(2)

                try:
                    self.apply(title, company)
                except Exception as e:
                    print("    [!] Error during apply:", e)

                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])

                applied += 1

            if self.successful_submits >= MAX_JOBS:
                break

            moved = self.go_to_next_page()
            if not moved:
                break

            page += 1

        print(f"\n[*] DONE — Successfully submitted {self.successful_submits} REAL applications.")
# ============================================================
# SECTION 4 — GLUE BETWEEN GUI AND SEEK BOT
# ============================================================

class UnifiedSeekBotRunner:
    """
    This wrapper simply connects your full untouched SeekBot (from main.py)
    to the GUI without modifying your logic.
    """

    def __init__(self, gui):
        self.gui = gui
        self.driver = None
        self.bot = None
        self.thread = None
        self.running = False

    def start(self):
        if self.running:
            self.gui.log("ERROR", "Bot is already running.")
            return

        self.running = True

        # --------------------------------------------
        # Start in background thread (no freezing GUI)
        # --------------------------------------------
        self.thread = threading.Thread(target=self._run_bot, daemon=True)
        self.thread.start()

    def _run_bot(self):
        try:
            # Tell unified print() to send logs to GUI
            set_gui_log_callback(self.gui.log_raw)

            self.gui.log("INFO", "Launching Chrome...")

            # Use your ORIGINAL init_browser()
            driver = init_browser()

            # Create bot instance EXACTLY as your original logic
            self.bot = SeekBot(driver)

            self.gui.log("SUCCESS", "Chrome launched. Bot is starting...")

            # Run the bot normally (100% untouched logic)
            self.bot.run()

            self.gui.log("SUCCESS", "Bot finished running.")

        except Exception as e:
            self.gui.log("ERROR", f"Bot crashed: {e}")

        finally:
            self.running = False
            self.gui.on_bot_finished()

    def stop(self):
        """ Sends a stop signal using your control.json system. """
        try:
            write_control(stop=True)
            self.gui.log("INFO", "Stop signal sent to bot.")
        except Exception as e:
            self.gui.log("ERROR", f"Stop failed: {e}")
# ============================================================
# SECTION 5 — FINAL MAIN LAUNCHER + GUI BINDINGS
# ============================================================

class UnifiedSeekMateApp(SeekMateGUI):
    """
    Extends your SeekMateGUI and hooks in the UnifiedSeekBotRunner.
    Everything else in your GUI stays EXACTLY the same.
    """

    def __init__(self, root):
        super().__init__(root)

        # Glue the bot runner into GUI
        self.bot_runner = UnifiedSeekBotRunner(self)

        # Replace old start/pause/stop bindings to use internal bot runner
        self.start_btn.config(command=self.start_bot_threaded)
        self.pause_btn.config(command=self.pause_bot_threaded)

    # --------------------------------------------
    # Log passthrough for unified print()
    # --------------------------------------------
    def log_raw(self, text):
        """
        Raw text from bot print() → GUI textbox.
        No formatting, no coloring.
        """
        self.console.insert(tk.END, text + "\n")
        self.console.see(tk.END)

    # --------------------------------------------
    # Threaded bot starter (instead of subprocess)
    # --------------------------------------------
    def start_bot_threaded(self):
        # Save and reset
        self.save_all_config()
        self.console.delete("1.0", tk.END)
        write_control(pause=False, stop=False)

        # UI changes
        self.start_btn.config(text="RUNNING...", bg="green", state="disabled")
        self.header_status.config(text="● RUNNING", fg="green")

        # Start money + timer logic
        self.start_time = time.time()
        self.timer_running = True
        self.money_running = True
        threading.Thread(target=self.timer_loop, daemon=True).start()
        threading.Thread(target=self.money_loop, daemon=True).start()

        # Start bot (SEEKBOT logic untouched)
        self.bot_runner.start()

    # --------------------------------------------
    # Bot finished signal
    # --------------------------------------------
    def on_bot_finished(self):
        try:
            self.timer_running = False
            self.money_running = False

            self.start_btn.config(text="START", bg="#0cb600", state="normal")
            self.header_status.config(text="● FINISHED", fg="grey")
            self.log("SUCCESS", "Bot finished.")
        except:
            pass

    # --------------------------------------------
    # Pause uses your existing control.json logic
    # --------------------------------------------
    def pause_bot_threaded(self):
        self.paused = not self.paused
        write_control(pause=self.paused)

        if self.paused:
            self.log("INFO", "Bot paused.")
            self.header_status.config(text="● PAUSED", fg="orange")
        else:
            self.log("INFO", "Bot resumed.")
            self.header_status.config(text="● RUNNING", fg="green")

    # --------------------------------------------
    # STOP button still uses your original system
    # --------------------------------------------
    def stop_bot(self):
        write_control(stop=True)
        self.log("INFO", "Stop signal sent.")
        self.header_status.config(text="● STOPPED", fg="red")
        try:
            self.timer_running = False
            self.money_running = False
        except:
            pass


# ============================================================
# RUN THE APP
# ============================================================
def main():
    root = tk.Tk()
    app = UnifiedSeekMateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

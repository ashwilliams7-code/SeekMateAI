"""
Claude Code Form Extractor — Scans SEEK, finds external jobs, extracts form fields.
Claude Code itself acts as the AI brain (no API costs).
"""
import os, sys, json, time, tempfile, shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def resource_path(p):
    try: return os.path.join(sys._MEIPASS, p)
    except: return os.path.join(os.path.abspath("."), p)

CONFIG = json.load(open(resource_path("config.json")))


def init_browser():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        chrome_options.binary_location = chrome_path
    profile_dir = os.path.join(tempfile.gettempdir(), "seekmate_chrome_profile")
    if os.path.exists(profile_dir):
        for f in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
            try: os.remove(os.path.join(profile_dir, f))
            except: pass
    os.makedirs(profile_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    service = Service(ChromeDriverManager().install())
    try:
        return webdriver.Chrome(service=service, options=chrome_options)
    except:
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir = os.path.join(tempfile.gettempdir(), f"seekmate_cc_{int(time.time())}")
        os.makedirs(profile_dir, exist_ok=True)
        opts2 = Options()
        opts2.add_argument("--start-maximized")
        opts2.add_argument("--disable-blink-features=AutomationControlled")
        opts2.add_argument("--no-sandbox")
        opts2.add_argument("--disable-dev-shm-usage")
        if os.path.exists(chrome_path):
            opts2.binary_location = chrome_path
        opts2.add_argument(f"--user-data-dir={profile_dir}")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts2)


def get_label(driver, element):
    """Get the label text for a form element."""
    aria = element.get_attribute("aria-label")
    if aria: return aria.strip()
    eid = element.get_attribute("id")
    if eid:
        try:
            lbl = driver.find_element(By.CSS_SELECTOR, f"label[for='{eid}']")
            if lbl.text.strip(): return lbl.text.strip()
        except: pass
    try:
        parent_label = element.find_element(By.XPATH, "ancestor::label")
        text = parent_label.text.strip()
        if text: return text
    except: pass
    try:
        parent = element.find_element(By.XPATH, "..")
        for child in parent.find_elements(By.XPATH, "./*"):
            if child != element and child.text.strip():
                return child.text.strip()[:100]
    except: pass
    return element.get_attribute("placeholder") or element.get_attribute("name") or ""


def build_selector(element):
    eid = element.get_attribute("id")
    if eid: return f"#{eid}"
    name = element.get_attribute("name")
    tag = element.tag_name
    if name: return f"{tag}[name='{name}']"
    return ""


def extract_form_fields(driver):
    """Extract all form fields from the current page."""
    fields = []

    for inp in driver.find_elements(By.CSS_SELECTOR,
        "input[type='text'], input[type='email'], input[type='tel'], input[type='url'], "
        "input[type='number'], input[type='date'], input:not([type])"):
        try:
            if not inp.is_displayed(): continue
            label = get_label(driver, inp)
            fields.append({
                "type": "text", "input_type": inp.get_attribute("type") or "text",
                "name": inp.get_attribute("name") or "", "id": inp.get_attribute("id") or "",
                "placeholder": inp.get_attribute("placeholder") or "", "label": label,
                "value": inp.get_attribute("value") or "",
                "required": inp.get_attribute("required") is not None,
                "selector": build_selector(inp),
            })
        except: pass

    for ta in driver.find_elements(By.CSS_SELECTOR, "textarea"):
        try:
            if not ta.is_displayed(): continue
            fields.append({
                "type": "textarea", "name": ta.get_attribute("name") or "",
                "id": ta.get_attribute("id") or "", "label": get_label(driver, ta),
                "placeholder": ta.get_attribute("placeholder") or "",
                "value": ta.text or "", "maxlength": ta.get_attribute("maxlength") or "",
                "selector": build_selector(ta),
            })
        except: pass

    for sel in driver.find_elements(By.CSS_SELECTOR, "select"):
        try:
            if not sel.is_displayed(): continue
            options = []
            for opt in sel.find_elements(By.TAG_NAME, "option"):
                options.append({"text": opt.text.strip(), "value": opt.get_attribute("value") or ""})
            fields.append({
                "type": "select", "name": sel.get_attribute("name") or "",
                "id": sel.get_attribute("id") or "", "label": get_label(driver, sel),
                "options": options, "selector": build_selector(sel),
            })
        except: pass

    radio_groups = {}
    for radio in driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
        try:
            if not radio.is_displayed(): continue
            name = radio.get_attribute("name") or ""
            if name not in radio_groups:
                label = get_label(driver, radio)
                try:
                    fieldset = radio.find_element(By.XPATH, "ancestor::fieldset")
                    legend = fieldset.find_element(By.TAG_NAME, "legend")
                    label = legend.text.strip() or label
                except: pass
                radio_groups[name] = {"label": label, "options": [], "name": name}
            val = radio.get_attribute("value") or ""
            ol = ""
            try:
                lid = radio.get_attribute("id")
                if lid: ol = driver.find_element(By.CSS_SELECTOR, f"label[for='{lid}']").text.strip()
            except: pass
            radio_groups[name]["options"].append(ol or val)
        except: pass
    for name, group in radio_groups.items():
        fields.append({"type": "radio", "name": name, "label": group["label"],
                        "options": group["options"], "selector": f"input[name='{name}']"})

    for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        try:
            if not cb.is_displayed(): continue
            fields.append({
                "type": "checkbox", "name": cb.get_attribute("name") or "",
                "id": cb.get_attribute("id") or "", "label": get_label(driver, cb),
                "checked": cb.is_selected(), "selector": build_selector(cb),
            })
        except: pass

    for fi in driver.find_elements(By.CSS_SELECTOR, "input[type='file']"):
        try:
            fields.append({
                "type": "file", "name": fi.get_attribute("name") or "",
                "label": get_label(driver, fi), "accept": fi.get_attribute("accept") or "",
                "selector": build_selector(fi),
            })
        except: pass

    return fields


def scan_and_extract():
    """Scan SEEK, find first external job, navigate to portal, extract form."""
    driver = init_browser()

    try:
        # Check login
        driver.get("https://www.seek.com.au/")
        time.sleep(4)
        if driver.find_elements(By.XPATH, "//a[contains(., 'Sign in')]"):
            print("ERROR: Not logged in to SEEK")
            driver.quit()
            return

        print("OK: Logged in to SEEK")

        # Search for jobs
        search_url = "https://www.seek.com.au/jobs?keywords=director&where=Gold%20Coast&sortmode=ListedDate"
        driver.get(search_url)
        time.sleep(5)

        # Collect job URLs from search results
        cards = driver.find_elements(By.CSS_SELECTOR, "article[data-automation='normalJob']")
        print(f"JOBS: {len(cards)} found on page")

        job_urls = []
        for card in cards[:15]:
            try:
                title_el = card.find_element(By.CSS_SELECTOR, "[data-automation='jobTitle']")
                try:
                    comp_el = card.find_element(By.CSS_SELECTOR, "[data-automation='jobCompany']")
                    company = comp_el.text
                except:
                    company = "Unknown"
                job_urls.append({
                    "title": title_el.text,
                    "href": title_el.get_attribute("href"),
                    "company": company,
                })
            except:
                continue

        print(f"COLLECTED: {len(job_urls)} job URLs")

        # Now visit each job one by one (no tab switching)
        external_found = None

        for i, job in enumerate(job_urls):
            print(f"\n--- Checking [{i+1}/{len(job_urls)}]: {job['title'][:50]} ---")
            driver.get(job["href"])

            try:
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-automation='job-detail-apply']"))
                )
            except:
                print(f"  No apply button found")
                continue

            el = driver.find_element(By.CSS_SELECTOR, "a[data-automation='job-detail-apply']")
            btn_text = el.text.strip().lower().replace('\u2060', '')

            # Get description
            desc = ""
            for sel in ["[data-automation='jobDescription']", "div[data-automation*='jobAdDetails']"]:
                try:
                    desc = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if len(desc) > 50: break
                except: continue

            if "quick" in btn_text:
                print(f"  QUICK APPLY — skipping")
                continue

            print(f"  EXTERNAL (btn='{btn_text}') — {job['company']}")
            external_found = {**job, "description": desc[:2000]}

            # Click Apply to navigate to external portal
            print(f"  Clicking Apply...")
            original_handles = set(driver.window_handles)
            driver.execute_script("arguments[0].click();", el)
            time.sleep(6)

            # Handle new tab
            new_handles = set(driver.window_handles)
            if new_handles - original_handles:
                new_tab = list(new_handles - original_handles)[0]
                driver.switch_to.window(new_tab)
                time.sleep(3)

            # Check for redirect (SEEK /apply page)
            current = driver.current_url
            if "seek.com.au" in current and "/apply" in current:
                print(f"  On SEEK redirect page, waiting for redirect...")
                time.sleep(5)
                current = driver.current_url

            if "seek.com.au" in current:
                print(f"  Still on SEEK — not external, skipping")
                # Close extra tabs
                while len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                continue

            print(f"  PORTAL: {current}")

            # Wait for form to fully load
            time.sleep(4)

            # Extract form fields
            fields = extract_form_fields(driver)
            page_text = ""
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text[:5000]
            except: pass

            form_data = {
                "job": external_found,
                "portal_url": current,
                "page_text": page_text,
                "fields": fields,
                "field_count": len(fields),
            }

            with open("cc_form_data.json", "w") as f:
                json.dump(form_data, f, indent=2, ensure_ascii=False)

            print(f"\n{'='*60}")
            print(f"FORM EXTRACTED: {len(fields)} fields")
            print(f"Job: {external_found['title']} @ {external_found['company']}")
            print(f"Portal: {current}")
            print(f"{'='*60}")

            for fi, field in enumerate(fields):
                ftype = field.get("type", "?")
                label = field.get("label", "?")[:60]
                if ftype == "select":
                    opts = [o["text"] for o in field.get("options", [])][:5]
                    print(f"  [{fi+1}] {ftype}: \"{label}\" options={opts}")
                elif ftype == "radio":
                    print(f"  [{fi+1}] {ftype}: \"{label}\" options={field.get('options', [])}")
                elif ftype == "file":
                    print(f"  [{fi+1}] {ftype}: \"{label}\" accept={field.get('accept', '')}")
                else:
                    req = "*" if field.get("required") else ""
                    val = field.get("value", "")
                    print(f"  [{fi+1}] {ftype}{req}: \"{label}\" {f'value=\"{val}\"' if val else ''}")

            print(f"\nSaved to cc_form_data.json")
            print(f"Browser staying open on portal page.")

            # Keep browser alive — don't quit
            # The fill step will connect to this browser
            try:
                input("\nPress ENTER to close browser (or Ctrl+C)...")
            except (EOFError, KeyboardInterrupt):
                pass

            break  # Found and extracted first external job

        if not external_found:
            print("\nNo external jobs found in first 15 results")

        driver.quit()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        try: driver.quit()
        except: pass


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "scan":
        scan_and_extract()
    else:
        print(f"Unknown mode: {mode}")

"""
CAPTCHA detection and solving via 2Captcha API.

Supports reCAPTCHA v2, hCaptcha, and Cloudflare Turnstile.
Extracted and generalized from the existing indeed_bot.py CAPTCHA handling.
"""

import time
import requests
from selenium.webdriver.common.by import By


class CaptchaSolver:
    TWOCAPTCHA_API = "http://2captcha.com"

    def __init__(self, driver, api_key):
        self.driver = driver
        self.api_key = api_key
        self.max_retries = 3
        self.poll_interval = 5  # seconds between status checks
        self.max_wait = 120  # max seconds to wait for solution

    def detect_captcha(self):
        """Detect if a CAPTCHA is present on the page. Returns type string or None."""
        # reCAPTCHA v2
        try:
            recaptcha = self.driver.find_elements(
                By.CSS_SELECTOR, "iframe[src*='recaptcha'], .g-recaptcha, #g-recaptcha"
            )
            if recaptcha:
                return "recaptcha_v2"
        except Exception:
            pass

        # hCaptcha
        try:
            hcaptcha = self.driver.find_elements(
                By.CSS_SELECTOR, "iframe[src*='hcaptcha'], .h-captcha, [data-hcaptcha-widget-id]"
            )
            if hcaptcha:
                return "hcaptcha"
        except Exception:
            pass

        # Cloudflare Turnstile
        try:
            turnstile = self.driver.find_elements(
                By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare'], .cf-turnstile"
            )
            if turnstile:
                return "turnstile"
        except Exception:
            pass

        return None

    def solve(self):
        """Detect and solve any CAPTCHA on the page. Returns True if solved or no CAPTCHA."""
        captcha_type = self.detect_captcha()
        if not captcha_type:
            return True  # No CAPTCHA present

        if not self.api_key:
            print("    [CAPTCHA] No 2Captcha API key configured. Cannot solve CAPTCHA.")
            return False

        print(f"    [CAPTCHA] Detected {captcha_type}, solving...")

        for attempt in range(self.max_retries):
            try:
                if captcha_type == "recaptcha_v2":
                    result = self._solve_recaptcha()
                elif captcha_type == "hcaptcha":
                    result = self._solve_hcaptcha()
                elif captcha_type == "turnstile":
                    result = self._solve_turnstile()
                else:
                    print(f"    [CAPTCHA] Unsupported type: {captcha_type}")
                    return False

                if result:
                    print(f"    [CAPTCHA] Solved successfully on attempt {attempt + 1}")
                    return True

            except Exception as e:
                print(f"    [CAPTCHA] Attempt {attempt + 1} failed: {e}")

            if attempt < self.max_retries - 1:
                time.sleep(5)

        print(f"    [CAPTCHA] Failed to solve after {self.max_retries} attempts")
        return False

    def _solve_recaptcha(self):
        """Solve reCAPTCHA v2 using 2Captcha API."""
        sitekey = self._extract_recaptcha_sitekey()
        if not sitekey:
            print("    [CAPTCHA] Could not extract reCAPTCHA sitekey")
            return False

        page_url = self.driver.current_url

        # Submit task to 2Captcha
        response = requests.get(f"{self.TWOCAPTCHA_API}/in.php", params={
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }, timeout=30)

        data = response.json()
        if data.get("status") != 1:
            print(f"    [CAPTCHA] 2Captcha submit error: {data.get('request')}")
            return False

        task_id = data["request"]
        print(f"    [CAPTCHA] Task submitted (ID: {task_id}), polling for result...")

        # Poll for solution
        token = self._poll_for_result(task_id)
        if not token:
            return False

        # Inject token into page
        return self._inject_recaptcha_token(token)

    def _solve_hcaptcha(self):
        """Solve hCaptcha using 2Captcha API."""
        sitekey = self._extract_hcaptcha_sitekey()
        if not sitekey:
            print("    [CAPTCHA] Could not extract hCaptcha sitekey")
            return False

        page_url = self.driver.current_url

        response = requests.get(f"{self.TWOCAPTCHA_API}/in.php", params={
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }, timeout=30)

        data = response.json()
        if data.get("status") != 1:
            print(f"    [CAPTCHA] 2Captcha submit error: {data.get('request')}")
            return False

        task_id = data["request"]
        print(f"    [CAPTCHA] hCaptcha task submitted (ID: {task_id}), polling...")

        token = self._poll_for_result(task_id)
        if not token:
            return False

        return self._inject_hcaptcha_token(token)

    def _solve_turnstile(self):
        """Solve Cloudflare Turnstile using 2Captcha API."""
        sitekey = self._extract_turnstile_sitekey()
        if not sitekey:
            print("    [CAPTCHA] Could not extract Turnstile sitekey")
            return False

        page_url = self.driver.current_url

        response = requests.get(f"{self.TWOCAPTCHA_API}/in.php", params={
            "key": self.api_key,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }, timeout=30)

        data = response.json()
        if data.get("status") != 1:
            print(f"    [CAPTCHA] 2Captcha submit error: {data.get('request')}")
            return False

        task_id = data["request"]
        print(f"    [CAPTCHA] Turnstile task submitted (ID: {task_id}), polling...")

        token = self._poll_for_result(task_id)
        if not token:
            return False

        return self._inject_turnstile_token(token)

    # --- Sitekey extraction ---

    def _extract_recaptcha_sitekey(self):
        """Extract reCAPTCHA sitekey from the page."""
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, ".g-recaptcha")
            sitekey = el.get_attribute("data-sitekey")
            if sitekey:
                return sitekey
        except Exception:
            pass

        try:
            el = self.driver.find_element(By.CSS_SELECTOR, "[data-sitekey]")
            return el.get_attribute("data-sitekey")
        except Exception:
            pass

        # Try from iframe src
        try:
            iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
            src = iframe.get_attribute("src")
            import re
            match = re.search(r'[?&]k=([^&]+)', src)
            if match:
                return match.group(1)
        except Exception:
            pass

        return None

    def _extract_hcaptcha_sitekey(self):
        """Extract hCaptcha sitekey from the page."""
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, ".h-captcha")
            sitekey = el.get_attribute("data-sitekey")
            if sitekey:
                return sitekey
        except Exception:
            pass

        try:
            el = self.driver.find_element(By.CSS_SELECTOR, "[data-hcaptcha-widget-id]")
            parent = el.find_element(By.XPATH, "./..")
            return parent.get_attribute("data-sitekey")
        except Exception:
            pass

        try:
            iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe[src*='hcaptcha']")
            src = iframe.get_attribute("src")
            import re
            match = re.search(r'sitekey=([^&]+)', src)
            if match:
                return match.group(1)
        except Exception:
            pass

        return None

    def _extract_turnstile_sitekey(self):
        """Extract Cloudflare Turnstile sitekey from the page."""
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, ".cf-turnstile")
            return el.get_attribute("data-sitekey")
        except Exception:
            pass

        try:
            el = self.driver.find_element(By.CSS_SELECTOR, "[data-sitekey]")
            return el.get_attribute("data-sitekey")
        except Exception:
            pass

        return None

    # --- Polling & Token injection ---

    def _poll_for_result(self, task_id):
        """Poll 2Captcha for the solution token."""
        start = time.time()
        time.sleep(15)  # Initial wait for solving

        while time.time() - start < self.max_wait:
            try:
                response = requests.get(f"{self.TWOCAPTCHA_API}/res.php", params={
                    "key": self.api_key,
                    "action": "get",
                    "id": task_id,
                    "json": 1,
                }, timeout=30)

                data = response.json()
                if data.get("status") == 1:
                    return data["request"]
                elif data.get("request") == "CAPCHA_NOT_READY":
                    time.sleep(self.poll_interval)
                else:
                    print(f"    [CAPTCHA] Polling error: {data.get('request')}")
                    return None
            except Exception as e:
                print(f"    [CAPTCHA] Polling exception: {e}")
                time.sleep(self.poll_interval)

        print("    [CAPTCHA] Timeout waiting for solution")
        return None

    def _inject_recaptcha_token(self, token):
        """Inject solved reCAPTCHA token into the page."""
        try:
            self.driver.execute_script(f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                // Try known callback functions
                if (typeof captchaCallback === 'function') captchaCallback('{token}');
                if (typeof onRecaptchaSuccess === 'function') onRecaptchaSuccess('{token}');
                // Try grecaptcha callback
                try {{
                    var widgetId = Object.keys(___grecaptcha_cfg.clients).find(function(id) {{
                        return ___grecaptcha_cfg.clients[id];
                    }});
                    if (widgetId !== undefined) {{
                        var callback = ___grecaptcha_cfg.clients[widgetId].aa.l.callback;
                        if (typeof callback === 'function') callback('{token}');
                    }}
                }} catch(e) {{}}
            """)
            time.sleep(1)
            return True
        except Exception as e:
            print(f"    [CAPTCHA] Token injection error: {e}")
            # Fallback: try setting textarea directly
            try:
                self.driver.execute_script(f"""
                    var ta = document.querySelector('[name="g-recaptcha-response"]') ||
                             document.getElementById('g-recaptcha-response');
                    if (ta) {{ ta.innerHTML = '{token}'; ta.value = '{token}'; }}
                """)
                return True
            except Exception:
                return False

    def _inject_hcaptcha_token(self, token):
        """Inject solved hCaptcha token into the page."""
        try:
            self.driver.execute_script(f"""
                var response = document.querySelector('[name="h-captcha-response"]') ||
                               document.querySelector('textarea[name*="hcaptcha"]');
                if (response) {{
                    response.innerHTML = '{token}';
                    response.value = '{token}';
                }}
                // Try hcaptcha callback
                try {{
                    var iframe = document.querySelector('iframe[src*="hcaptcha"]');
                    if (iframe) {{
                        var widget = iframe.closest('.h-captcha');
                        if (widget && widget.dataset.callback) {{
                            window[widget.dataset.callback](token);
                        }}
                    }}
                }} catch(e) {{}}
            """)
            time.sleep(1)
            return True
        except Exception as e:
            print(f"    [CAPTCHA] hCaptcha injection error: {e}")
            return False

    def _inject_turnstile_token(self, token):
        """Inject solved Turnstile token into the page."""
        try:
            self.driver.execute_script(f"""
                var input = document.querySelector('[name="cf-turnstile-response"]') ||
                            document.querySelector('input[name*="turnstile"]');
                if (input) {{
                    input.value = '{token}';
                }}
                // Try turnstile callback
                try {{
                    var widget = document.querySelector('.cf-turnstile');
                    if (widget && widget.dataset.callback) {{
                        window[widget.dataset.callback]('{token}');
                    }}
                }} catch(e) {{}}
            """)
            time.sleep(1)
            return True
        except Exception as e:
            print(f"    [CAPTCHA] Turnstile injection error: {e}")
            return False

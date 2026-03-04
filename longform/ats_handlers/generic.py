"""
Generic ATS handler - Universal form filler.

Works on any HTML form regardless of the ATS portal. Detects page state,
fills fields using AI + profile data, navigates multi-page forms, and handles
login/registration flows.
"""

import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from longform.field_detector import FieldDetector, FormField


class GenericATSHandler:
    def __init__(self, driver, field_detector, ai_responder, doc_manager, captcha_solver, config):
        self.driver = driver
        self.field_detector = field_detector
        self.ai = ai_responder
        self.docs = doc_manager
        self.captcha = captcha_solver
        self.config = config

        # Stealth settings
        self.stealth = config.get("STEALTH_MODE", True)
        self.apply_speed = config.get("APPLY_SPEED", 50)

    def can_handle(self, url):
        """Generic handler can handle any URL."""
        return True

    def detect_page_type(self):
        """
        Detect what type of page we're currently on.
        Returns: 'form', 'login', 'registration', 'captcha', 'success', 'error', 'unknown'
        """
        try:
            page_source = self.driver.page_source.lower()
        except Exception:
            return "unknown"

        # CAPTCHA check first
        if self.captcha.detect_captcha():
            return "captcha"

        # Success indicators
        success_patterns = [
            "thank you for your application",
            "application has been submitted",
            "application received",
            "successfully submitted",
            "thanks for applying",
            "application complete",
            "we have received your application",
            "your application has been sent",
        ]
        for pattern in success_patterns:
            if pattern in page_source:
                return "success"

        # Login detection
        try:
            password_fields = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            visible_passwords = [f for f in password_fields if self._is_visible(f)]
            if visible_passwords:
                # Distinguish login from registration
                if any(kw in page_source for kw in ["create account", "sign up", "register", "new account"]):
                    return "registration"
                if any(kw in page_source for kw in ["sign in", "log in", "login", "existing account"]):
                    return "login"
                # Default: if there are few fields, it's login; many fields = registration
                all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden'])")
                visible_inputs = [i for i in all_inputs if self._is_visible(i)]
                return "registration" if len(visible_inputs) > 4 else "login"
        except Exception:
            pass

        # Error detection
        error_patterns = [
            "please correct the errors",
            "fix the following",
            "there were errors",
            "validation failed",
        ]
        for pattern in error_patterns:
            if pattern in page_source:
                return "error"

        # Form detection - has fillable fields
        try:
            inputs = self.driver.find_elements(By.CSS_SELECTOR,
                "input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select"
            )
            visible_inputs = [i for i in inputs if self._is_visible(i)]
            if len(visible_inputs) >= 1:
                return "form"
        except Exception:
            pass

        return "unknown"

    def fill_current_page(self):
        """
        Fill all detected fields on the current page.
        Returns dict with: fields_filled (int), fields_failed (int), files_uploaded (list)
        """
        result = {"fields_filled": 0, "fields_failed": 0, "files_uploaded": []}

        fields = self.field_detector.detect_fields()
        if not fields:
            print("    [ATS] No fillable fields detected on this page")
            return result

        print(f"    [ATS] Detected {len(fields)} fields on page")

        for field in fields:
            try:
                # Skip already filled fields
                if field.current_value and field.field_type not in ("radio", "checkbox"):
                    continue

                filled = self._fill_field(field)
                if filled:
                    result["fields_filled"] += 1
                else:
                    if field.required:
                        result["fields_failed"] += 1

            except Exception as e:
                print(f"    [ATS] Error filling field '{field.label}': {e}")
                if field.required:
                    result["fields_failed"] += 1

            # Human-like delay between fields
            self._field_delay()

        # Handle file uploads separately
        file_fields = [f for f in fields if f.field_type == "file"]
        for ff in file_fields:
            filename = self.docs.handle_file_upload(ff)
            if filename:
                result["files_uploaded"].append(filename)
                result["fields_filled"] += 1

        return result

    def _fill_field(self, field):
        """Fill a single form field. Returns True if filled successfully."""
        if field.field_type == "file":
            return False  # Handled separately

        # Scroll into view
        self._scroll_to(field.element)

        if field.field_type in ("text", "email", "tel", "number", "url"):
            return self._fill_text_input(field)
        elif field.field_type == "password":
            return False  # Never auto-fill passwords
        elif field.field_type == "textarea":
            return self._fill_textarea(field)
        elif field.field_type == "select":
            return self._fill_select(field)
        elif field.field_type == "radio":
            return self._fill_radio(field)
        elif field.field_type == "checkbox":
            return self._fill_checkbox(field)
        elif field.field_type == "date":
            return self._fill_date(field)

        return False

    def _fill_text_input(self, field):
        """Fill a text-type input field."""
        label = field.label or field.placeholder or field.name

        # Get answer (rule-based or GPT)
        answer = self.ai.answer_text_question(label, field.max_length or None)
        if not answer:
            return False

        return self._set_input_value(field.element, answer)

    def _fill_textarea(self, field):
        """Fill a textarea field."""
        label = field.label or field.placeholder or field.name

        # Detect if this is a cover letter field
        is_cover_letter = any(kw in (label or "").lower() for kw in
                              ["cover letter", "covering letter", "letter of application"])

        if is_cover_letter:
            answer = self.ai.generate_cover_letter()
        else:
            answer = self.ai.answer_text_question(label, field.max_length or None)

        if not answer:
            return False

        return self._set_input_value(field.element, answer)

    def _fill_select(self, field):
        """Fill a select/dropdown field."""
        label = field.label or field.name

        if not field.options:
            return False

        answer = self.ai.select_dropdown_option(label, field.options)
        if not answer:
            return False

        try:
            select = Select(field.element)
            # Try by visible text first
            try:
                select.select_by_visible_text(answer)
                return True
            except Exception:
                pass

            # Try partial text match
            for option in select.options:
                if answer.lower() in option.text.lower():
                    select.select_by_visible_text(option.text)
                    return True

            # Try by value
            for option in select.options:
                if answer.lower() == (option.get_attribute("value") or "").lower():
                    select.select_by_value(option.get_attribute("value"))
                    return True

        except Exception as e:
            print(f"    [ATS] Select fill error: {e}")

        return False

    def _fill_radio(self, field):
        """Fill a radio button group."""
        label = field.label or field.group_name

        if field.current_value:
            return True  # Already selected

        answer = self.ai.select_radio_option(label, field.options)
        if not answer:
            return False

        # Find and click the matching radio button
        try:
            group_name = field.group_name or field.name
            if group_name:
                radios = self.driver.find_elements(
                    By.CSS_SELECTOR, f"input[type='radio'][name='{group_name}']"
                )
            else:
                radios = [field.element]

            for radio in radios:
                radio_label = self._get_radio_label(radio)
                if radio_label and (
                    answer.lower() == radio_label.lower() or
                    answer.lower() in radio_label.lower() or
                    radio_label.lower() in answer.lower()
                ):
                    self._click_element(radio)
                    return True

            # Fallback: click by value match
            for radio in radios:
                value = radio.get_attribute("value") or ""
                if answer.lower() in value.lower():
                    self._click_element(radio)
                    return True

        except Exception as e:
            print(f"    [ATS] Radio fill error: {e}")

        return False

    def _fill_checkbox(self, field):
        """Fill checkbox field(s)."""
        label = field.label or field.group_name

        if not field.options:
            # Single checkbox - check it if it looks affirmative
            if not field.element.is_selected():
                label_lower = (label or "").lower()
                if any(kw in label_lower for kw in ["agree", "accept", "confirm", "acknowledge",
                                                     "consent", "i have read", "terms"]):
                    self._click_element(field.element)
                    return True
            return field.element.is_selected()

        # Multiple checkboxes
        selected = self.ai.select_checkbox_options(label, field.options)
        if not selected:
            return False

        group_name = field.group_name or field.name
        checkboxes = self.driver.find_elements(
            By.CSS_SELECTOR, f"input[type='checkbox'][name^='{group_name}']"
        ) if group_name else [field.element]

        filled_count = 0
        for cb in checkboxes:
            cb_label = self._get_radio_label(cb)
            if cb_label and cb_label in selected:
                if not cb.is_selected():
                    self._click_element(cb)
                filled_count += 1

        return filled_count > 0

    def _fill_date(self, field):
        """Fill a date input field."""
        label = field.label or field.name
        answer = self.ai.answer_date_question(label)
        if answer:
            return self._set_input_value(field.element, answer)
        return False

    # --- Login/Registration handling ---

    def handle_login_page(self, profile):
        """
        Attempt to handle a login page using stored credentials.
        Returns True if login was handled (or skipped).
        """
        email = profile.get_field("personal.email")
        if not email:
            print("    [ATS] No email in profile for login")
            return False

        # Find email/username field
        try:
            email_field = None
            for selector in ["input[type='email']", "input[name*='email']",
                             "input[name*='user']", "input[id*='email']",
                             "input[id*='user']", "input[autocomplete='email']",
                             "input[autocomplete='username']"]:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if self._is_visible(el):
                        email_field = el
                        break
                if email_field:
                    break

            if email_field:
                self._set_input_value(email_field, email)

        except Exception as e:
            print(f"    [ATS] Login email fill error: {e}")
            return False

        # Don't auto-fill passwords - indicate that manual intervention may be needed
        print("    [ATS] Filled email on login page. Password entry may be required.")
        return True

    def handle_registration_page(self, profile):
        """
        Attempt to fill a registration/account creation form.
        Returns True if form was filled.
        """
        # Just treat it like a normal form - the field detector + AI responder
        # will handle name, email, phone, etc. from the profile.
        result = self.fill_current_page()
        return result["fields_filled"] > 0

    def click_next(self):
        """Click the next/continue button. Returns True if clicked."""
        btn = self.field_detector.detect_next_button()
        if btn:
            self._click_element(btn)
            time.sleep(2)
            return True
        return False

    def click_submit(self):
        """Click the submit/apply button. Returns True if clicked."""
        btn = self.field_detector.detect_submit_button()
        if btn:
            self._click_element(btn)
            time.sleep(2)
            return True
        return False

    def is_submission_complete(self):
        """Check if we've reached a success/confirmation page."""
        return self.detect_page_type() == "success"

    def get_errors(self):
        """Get any validation errors on the current page."""
        return self.field_detector.detect_errors()

    # --- Internal helpers ---

    def _set_input_value(self, element, value):
        """Set the value of an input field with human-like behavior."""
        try:
            self._scroll_to(element)
            self._stealth_before_click()

            # Click to focus
            try:
                element.click()
            except Exception:
                self.driver.execute_script("arguments[0].focus();", element)

            # Clear existing value
            element.clear()
            time.sleep(0.1)

            # Type with optional human-like delays
            if self.stealth and len(value) < 100:
                self._human_type(element, value)
            else:
                element.send_keys(value)

            # Dispatch events for React/Angular forms
            self.driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.dispatchEvent(new Event('blur', {bubbles: true}));
            """, element)

            return True

        except Exception as e:
            # Fallback: JavaScript injection
            try:
                escaped_value = value.replace("'", "\\'").replace("\n", "\\n")
                self.driver.execute_script(f"""
                    var el = arguments[0];
                    el.value = '{escaped_value}';
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                """, element)
                return True
            except Exception as e2:
                print(f"    [ATS] Value set failed: {e2}")
                return False

    def _click_element(self, element):
        """Click an element with stealth behavior."""
        try:
            self._scroll_to(element)
            self._stealth_before_click()

            # Try regular click
            try:
                element.click()
                return
            except Exception:
                pass

            # Try clicking the associated label
            field_id = element.get_attribute("id")
            if field_id:
                try:
                    label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                    label.click()
                    return
                except Exception:
                    pass

            # Fallback: JavaScript click
            self.driver.execute_script("arguments[0].click();", element)

        except Exception as e:
            print(f"    [ATS] Click failed: {e}")

    def _scroll_to(self, element):
        """Scroll element into view."""
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            time.sleep(0.3)
        except Exception:
            pass

    def _human_type(self, element, text):
        """Type text with human-like delays between keystrokes."""
        import random
        for char in text:
            element.send_keys(char)
            delay = random.uniform(0.03, 0.12)
            # Adjust speed based on APPLY_SPEED setting
            speed_factor = max(0.1, (100 - self.apply_speed) / 100)
            time.sleep(delay * speed_factor)

    def _get_radio_label(self, radio_element):
        """Get the label text for a radio/checkbox element."""
        field_id = radio_element.get_attribute("id")
        if field_id:
            try:
                label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                return label.text.strip()
            except Exception:
                pass

        try:
            parent = radio_element.find_element(By.XPATH, "./ancestor::label")
            return parent.text.strip()
        except Exception:
            pass

        try:
            sibling = radio_element.find_element(By.XPATH, "./following-sibling::*[1]")
            return sibling.text.strip()
        except Exception:
            pass

        return radio_element.get_attribute("value") or ""

    def _is_visible(self, element):
        """Check if element is visible."""
        try:
            return element.is_displayed() and element.size["width"] > 0
        except Exception:
            return False

    def _stealth_before_click(self):
        """Add a small random delay before clicking (stealth mode)."""
        if self.stealth:
            import random
            time.sleep(random.uniform(0.15, 0.5))

    def _field_delay(self):
        """Delay between filling fields for human-like behavior."""
        if self.stealth:
            import random
            time.sleep(random.uniform(0.3, 1.0))
        else:
            time.sleep(0.1)

"""
LongFormEngine - Main orchestrator for external job applications.

Coordinates all agents: field detection, AI response generation, CAPTCHA solving,
email verification, document upload, and database logging. Handles the full lifecycle
of an external application from clicking "Apply on company site" to submission.
"""

import time
import os
from datetime import datetime

from longform.database import Database
from longform.profile import MasterProfile
from longform.field_detector import FieldDetector
from longform.ai_responder import AIResponder
from longform.captcha_solver import CaptchaSolver
from longform.email_verifier import EmailVerifier
from longform.document_manager import DocumentManager
from longform.ats_handlers.generic import GenericATSHandler


class LongFormEngine:
    VERSION = "1.0.0"

    def __init__(self, driver, config, gpt_func):
        """
        Args:
            driver: Selenium WebDriver instance (shared with SeekBot)
            config: Configuration dict (from config.json)
            gpt_func: The gpt(system_prompt, user_prompt) function from SeekBot
        """
        self.driver = driver
        self.config = config
        self.gpt = gpt_func

        # Settings
        self.max_pages = config.get("LONGFORM_MAX_PAGES", 10)
        self.retry_limit = config.get("LONGFORM_RETRY_LIMIT", 3)
        self.timeout = config.get("LONGFORM_TIMEOUT", 180)

        # Initialize sub-components
        db_path = config.get("LONGFORM_DB_PATH", "seekmate.db")
        self.db = Database(db_path)

        profile_path = config.get("MASTER_PROFILE_PATH", "master_profile.json")
        self.profile = MasterProfile(profile_path)
        self.profile.fill_from_config(config)

        self.field_detector = FieldDetector(driver)
        self.captcha = CaptchaSolver(driver, config.get("TWOCAPTCHA_API_KEY", ""))
        self.email_verifier = EmailVerifier(config)
        self.doc_manager = DocumentManager(driver, config)

    def run(self, external_button, job_title, company, job_url, description=""):
        """
        Execute the full long-form application flow.

        Args:
            external_button: WebElement of the "Apply on company site" button
            job_title: Job title string
            company: Company name string
            job_url: SEEK job URL
            description: Job description text

        Returns:
            dict with keys: success (bool), reason (str), pages_completed (int), duration (float)
        """
        start_time = time.time()
        result = {
            "success": False,
            "reason": "",
            "pages_completed": 0,
            "duration": 0,
            "captcha_triggered": False,
            "email_verification": False,
            "resume_used": None,
            "ats_portal": None,
        }

        # Log job to database
        job_id = self.db.log_job({
            "title": job_title,
            "company": company,
            "job_url": job_url,
            "description": description[:5000] if description else "",
            "status": "opened",
        })

        # Store original SEEK window handle
        original_window = self.driver.current_window_handle
        original_windows = set(self.driver.window_handles)

        print(f"\n    [LongForm] Starting external application for: {job_title} @ {company}")

        try:
            # Step 1: Navigate to external page
            if external_button is not None:
                # Called from SeekBot hook — need to click button and switch tabs
                if not self._click_external_and_switch(external_button, original_windows):
                    result["reason"] = "Failed to open external application page"
                    self._finalize(job_id, result, start_time, original_window)
                    return result
            else:
                # Called from standalone longform_bot — already on external page
                print("    [LongForm] Already on external portal (standalone mode)")

            # Record external URL
            external_url = self.driver.current_url
            result["ats_portal"] = self._detect_ats_name(external_url)
            print(f"    [LongForm] External portal: {external_url}")
            print(f"    [LongForm] ATS detected: {result['ats_portal'] or 'Unknown'}")

            # Initialize AI responder with job context
            job_context = {
                "title": job_title,
                "company": company,
                "description": description,
                "job_url": job_url,
            }
            ai_responder = AIResponder(self.gpt, self.profile, job_context)

            # Initialize ATS handler
            handler = GenericATSHandler(
                self.driver, self.field_detector, ai_responder,
                self.doc_manager, self.captcha, self.config
            )

            # Step 2: Multi-page form filling loop
            self.db.update_status(job_id, "attempted")

            for page_num in range(1, self.max_pages + 1):
                print(f"\n    [LongForm] --- Page {page_num} ---")

                # Wait for page to load
                time.sleep(2)

                # Check for timeout
                if time.time() - start_time > self.timeout:
                    result["reason"] = f"Timeout after {self.timeout}s"
                    self.db.log_failure(job_id, "timeout", result["reason"], self.driver.current_url)
                    break

                # Detect page type
                page_type = handler.detect_page_type()
                print(f"    [LongForm] Page type: {page_type}")

                # Handle based on page type
                if page_type == "success":
                    result["success"] = True
                    result["reason"] = "Application submitted successfully"
                    print("    [LongForm] Application submitted successfully!")
                    break

                elif page_type == "captcha":
                    result["captcha_triggered"] = True
                    solved = self.captcha.solve()
                    if not solved:
                        result["reason"] = "CAPTCHA solving failed"
                        self.db.log_failure(job_id, "captcha", "CAPTCHA solving failed", self.driver.current_url)
                        break
                    time.sleep(2)
                    continue  # Re-detect page after CAPTCHA

                elif page_type == "login":
                    handled = handler.handle_login_page(self.profile)
                    if not handled:
                        result["reason"] = "Login page detected, could not handle"
                        self.db.log_failure(job_id, "login_required", "Login page cannot be automated", self.driver.current_url)
                        break
                    # Try to proceed past login
                    handler.click_next() or handler.click_submit()
                    time.sleep(2)
                    continue

                elif page_type == "registration":
                    handled = handler.handle_registration_page(self.profile)
                    if handled:
                        handler.click_next() or handler.click_submit()
                        time.sleep(2)
                        # Check if email verification is triggered
                        if self._check_email_verification_needed():
                            result["email_verification"] = True
                            verified = self._handle_email_verification()
                            if not verified:
                                result["reason"] = "Email verification failed"
                                self.db.log_failure(job_id, "email_verification", "Verification timeout", self.driver.current_url)
                                break
                    else:
                        result["reason"] = "Registration page could not be filled"
                        self.db.log_failure(job_id, "login_required", "Registration failed", self.driver.current_url)
                        break
                    continue

                elif page_type == "form":
                    # Main form filling
                    fill_result = handler.fill_current_page()
                    result["pages_completed"] = page_num

                    if fill_result["files_uploaded"]:
                        result["resume_used"] = fill_result["files_uploaded"][0]

                    print(f"    [LongForm] Filled {fill_result['fields_filled']} fields, "
                          f"{fill_result['fields_failed']} failed, "
                          f"{len(fill_result['files_uploaded'])} files uploaded")

                    # Try to navigate to next page
                    for attempt in range(self.retry_limit):
                        # Try submit first (might be final page)
                        submit_btn = self.field_detector.detect_submit_button()
                        next_btn = self.field_detector.detect_next_button()

                        if submit_btn and not next_btn:
                            # This looks like the final page
                            handler.click_submit()
                            time.sleep(3)

                            # Check if submission was successful
                            if handler.is_submission_complete():
                                result["success"] = True
                                result["reason"] = "Application submitted successfully"
                                print("    [LongForm] Application submitted successfully!")
                                break

                            # Check for errors
                            errors = handler.get_errors()
                            if errors:
                                print(f"    [LongForm] Submission errors: {errors[:3]}")
                                if attempt < self.retry_limit - 1:
                                    # Try to fix errors and retry
                                    handler.fill_current_page()
                                    continue
                                else:
                                    result["reason"] = f"Submission errors: {'; '.join(errors[:3])}"
                                    self.db.log_failure(job_id, "form_error", result["reason"], self.driver.current_url)
                            break

                        elif next_btn:
                            handler.click_next()
                            time.sleep(2)

                            # Check for errors after clicking next
                            errors = handler.get_errors()
                            if errors:
                                print(f"    [LongForm] Page errors: {errors[:3]}")
                                if attempt < self.retry_limit - 1:
                                    handler.fill_current_page()
                                    continue
                                else:
                                    result["reason"] = f"Form errors on page {page_num}: {'; '.join(errors[:3])}"
                                    self.db.log_failure(job_id, "form_error", result["reason"], self.driver.current_url)
                            break

                        else:
                            # No submit or next button found
                            # Try clicking any prominent button
                            print("    [LongForm] No next/submit button found, looking for alternatives...")
                            if attempt == 0:
                                time.sleep(2)
                                continue
                            result["reason"] = "No navigation button found"
                            self.db.log_failure(job_id, "form_error", "No next/submit button", self.driver.current_url)
                            break

                    if result["success"]:
                        break

                elif page_type == "error":
                    errors = handler.get_errors()
                    result["reason"] = f"Error page: {'; '.join(errors[:3]) if errors else 'Unknown error'}"
                    self.db.log_failure(job_id, "form_error", result["reason"], self.driver.current_url)
                    break

                else:
                    # Unknown page type - try filling anyway
                    print(f"    [LongForm] Unknown page type, attempting to fill...")
                    handler.fill_current_page()
                    result["pages_completed"] = page_num
                    if not (handler.click_next() or handler.click_submit()):
                        result["reason"] = "Could not navigate past unknown page"
                        break

            if not result["reason"]:
                result["reason"] = f"Completed {result['pages_completed']} pages without clear outcome"

        except Exception as e:
            result["reason"] = f"Exception: {str(e)}"
            self.db.log_failure(job_id, "crash", str(e),
                                self.driver.current_url if self.driver else None)
            print(f"    [LongForm] Exception: {e}")

        finally:
            self._finalize(job_id, result, start_time, original_window)

        return result

    # --- Internal helpers ---

    def _click_external_and_switch(self, button, original_windows):
        """Click the external apply button and switch to the new tab."""
        try:
            # Click the button
            try:
                button.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", button)

            # Wait for new tab to open
            time.sleep(3)

            new_windows = set(self.driver.window_handles) - original_windows
            if new_windows:
                new_window = new_windows.pop()
                self.driver.switch_to.window(new_window)
                # Wait for page load
                time.sleep(3)
                return True

            # If no new tab, check if we navigated in the same tab
            if self.driver.current_url != "about:blank":
                return True

            print("    [LongForm] No new tab opened after clicking external apply")
            return False

        except Exception as e:
            print(f"    [LongForm] Error clicking external button: {e}")
            return False

    def _detect_ats_name(self, url):
        """Detect which ATS portal we're on based on URL."""
        url_lower = url.lower()

        ats_patterns = {
            "Workday": ["workday", "myworkday"],
            "SmartRecruiters": ["smartrecruiters"],
            "PageUp": ["pageup", "page-up"],
            "Greenhouse": ["greenhouse", "boards.greenhouse"],
            "Lever": ["lever.co", "jobs.lever"],
            "iCIMS": ["icims"],
            "Taleo": ["taleo"],
            "SuccessFactors": ["successfactors"],
            "BambooHR": ["bamboohr"],
            "Jobvite": ["jobvite"],
            "Breezy HR": ["breezy"],
            "JazzHR": ["jazz", "jazzhr"],
            "Recruiterbox": ["recruiterbox"],
            "Applied": ["applied", "beapplied"],
            "Scout Talent": ["scouttalent"],
            "Expr3ss": ["expr3ss"],
            "Livehire": ["livehire"],
            "Seek Employer": ["seek.com.au/employer"],
        }

        for ats_name, patterns in ats_patterns.items():
            if any(p in url_lower for p in patterns):
                return ats_name

        return None

    def _check_email_verification_needed(self):
        """Check if the current page is asking for email verification."""
        try:
            page_text = self.driver.page_source.lower()
            indicators = [
                "verify your email",
                "verification email",
                "check your email",
                "sent you an email",
                "confirm your email",
                "enter the code",
                "verification code",
            ]
            return any(ind in page_text for ind in indicators)
        except Exception:
            return False

    def _handle_email_verification(self):
        """Handle email verification flow."""
        print("    [LongForm] Email verification required, checking inbox...")

        # Detect sender hint from current page
        try:
            domain = self.driver.current_url.split("/")[2]
        except Exception:
            domain = None

        result = self.email_verifier.wait_for_verification(
            sender_hint=domain,
            timeout=120
        )

        if not result:
            return False

        if result["type"] == "otp":
            # Find OTP input field and enter code
            code = result["value"]
            print(f"    [LongForm] Got OTP code: {code}")
            try:
                # Look for OTP input field
                otp_selectors = [
                    "input[name*='code']", "input[name*='otp']", "input[name*='verify']",
                    "input[name*='token']", "input[type='tel']", "input[type='number']",
                    "input[autocomplete='one-time-code']",
                ]
                for selector in otp_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            el.clear()
                            el.send_keys(code)
                            # Try to submit
                            from selenium.webdriver.common.keys import Keys
                            el.send_keys(Keys.RETURN)
                            time.sleep(3)
                            return True
            except Exception as e:
                print(f"    [LongForm] Error entering OTP: {e}")

        elif result["type"] == "link":
            # Navigate to verification link
            link = result["value"]
            print(f"    [LongForm] Got verification link, navigating...")
            try:
                self.driver.get(link)
                time.sleep(5)
                return True
            except Exception as e:
                print(f"    [LongForm] Error navigating to verification link: {e}")

        return False

    def _finalize(self, job_id, result, start_time, original_window):
        """Finalize the application - log results and return to SEEK tab."""
        duration = time.time() - start_time
        result["duration"] = round(duration, 1)

        # Update job status in database
        final_status = "applied" if result["success"] else "failed"
        self.db.update_status(
            job_id, final_status,
            date_applied=datetime.now().isoformat() if result["success"] else None
        )

        # Log application details
        self.db.log_application({
            "job_id": job_id,
            "application_type": "long_form",
            "resume_used": result.get("resume_used"),
            "submission_status": "submitted" if result["success"] else "failed",
            "failure_reason": result.get("reason") if not result["success"] else None,
            "captcha_triggered": result.get("captcha_triggered", False),
            "email_verification": result.get("email_verification", False),
            "pages_completed": result.get("pages_completed", 0),
            "duration_seconds": duration,
            "ats_portal": result.get("ats_portal"),
            "agent_version": self.VERSION,
        })

        status_icon = "[+]" if result["success"] else "[-]"
        print(f"\n    {status_icon} LongForm result: {result['reason']}")
        print(f"    [LongForm] Duration: {result['duration']}s | Pages: {result['pages_completed']} | "
              f"CAPTCHA: {result['captcha_triggered']} | Email verify: {result['email_verification']}")

        # Close external tab and return to SEEK
        try:
            # Close all non-original tabs
            for handle in self.driver.window_handles:
                if handle != original_window:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
            self.driver.switch_to.window(original_window)
        except Exception as e:
            print(f"    [LongForm] Error returning to SEEK tab: {e}")
            try:
                if self.driver.window_handles:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception:
                pass

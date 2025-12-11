"""
Gmail Email Cleanup Selector
Deletes emails matching certain patterns while preserving action-required emails
Uses GPT Vision to analyze emails via screenshots and intelligently decide what to delete
Runs in a separate browser window to avoid interfering with Seek/Indeed bots
"""
import time
import re
import base64
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class GmailCleanup:
    """Handles Gmail email deletion based on patterns and GPT analysis - runs in separate window"""
    
    def __init__(self, driver=None, openai_api_key=None, openai_client=None, create_separate_window=True):
        """
        Initialize Gmail cleanup
        If create_separate_window is True, creates its own browser instance
        Otherwise uses the provided driver (for backward compatibility)
        """
        self.own_driver = None
        self.driver = driver
        self.gmail_tab_handle = None
        self.create_separate_window = create_separate_window
        
        # Create separate browser window if requested
        if create_separate_window:
            self.driver = self._create_separate_browser()
            if not self.driver:
                print("[Gmail] Failed to create separate browser window, falling back to provided driver")
                self.driver = driver
                self.create_separate_window = False
            else:
                self.own_driver = self.driver
                print("[Gmail] Created separate browser window for Gmail cleanup")
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if openai_client:
            self.openai_client = openai_client
        elif openai_api_key and OPENAI_AVAILABLE:
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
                print("[Gmail] GPT analysis enabled")
            except Exception as e:
                print(f"[Gmail] Failed to initialize OpenAI: {e}")
        
        # Patterns to DELETE (fallback if GPT unavailable)
        self.delete_patterns = [
            r"has viewed your application for",
            r"has viewed your application",
            r"application update",
            r"application status",
            r"viewed your profile",
            r"viewed your application",
        ]
        
        # Patterns to PRESERVE (do NOT delete) - safety net
        self.preserve_patterns = [
            r"needs action",
            r"action required",
            r"requires your attention",
            r"please respond",
            r"interview",
            r"next steps",
            r"schedule",
            r"meeting",
        ]
    
    def _create_separate_browser(self):
        """Create a separate browser instance for Gmail cleanup"""
        try:
            def resource_path(relative_path):
                """Get path for bundled or dev mode"""
                if getattr(sys, 'frozen', False):
                    base = sys._MEIPASS
                else:
                    base = os.path.dirname(os.path.abspath(__file__))
                return os.path.join(base, relative_path)
            
            print("[Gmail] Creating separate browser window...")
            
            # Try to use the same user data dir as main bot (so Gmail is logged in)
            # But use a different profile directory to avoid conflicts
            import tempfile
            user_data_dir = os.path.join(tempfile.gettempdir(), "seekmate_chrome_profile")
            gmail_profile_dir = os.path.join(tempfile.gettempdir(), "seekmate_gmail_profile")
            
            # Create directories if they don't exist
            os.makedirs(user_data_dir, exist_ok=True)
            os.makedirs(gmail_profile_dir, exist_ok=True)
            
            chrome_options = Options()
            
            # Use separate profile directory to avoid conflicts
            # This allows Gmail to be logged in if the main bot is using the same account
            chrome_options.add_argument(f"--user-data-dir={gmail_profile_dir}")
            
            # Window settings - make sure it's visible
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--window-size=1200,800")
            chrome_options.add_argument("--window-position=100,100")  # Position it so it's visible
            
            # Other options
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            print(f"[Gmail] Chrome options configured, profile dir: {gmail_profile_dir}")
            
            # Create driver
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                print("[Gmail] Chrome driver created successfully")
            except Exception as e:
                print(f"[Gmail] Failed to create Chrome driver: {e}")
                import traceback
                traceback.print_exc()
                return None
            
            # Set window title to identify it
            try:
                driver.execute_script("document.title = 'Gmail Cleanup - SeekMateAI';")
                print("[Gmail] Window title set")
            except:
                pass
            
            # Make sure window is visible by navigating to a page
            try:
                driver.get("about:blank")
                time.sleep(1)
                print("[Gmail] Browser window opened and visible")
            except Exception as e:
                print(f"[Gmail] Warning: Could not navigate to about:blank: {e}")
            
            return driver
            
        except Exception as e:
            print(f"[Gmail] Error creating separate browser: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def close(self):
        """Close the separate browser window if we created it"""
        if self.own_driver:
            try:
                self.own_driver.quit()
                print("[Gmail] Closed separate browser window")
            except:
                pass
    
    def open_gmail_tab(self):
        """Open Gmail in the browser window"""
        try:
            # If we have a separate window, just navigate to Gmail
            if self.create_separate_window and self.own_driver:
                print("[Gmail] Opening Gmail in separate window...")
                self.driver.get("https://mail.google.com")
                time.sleep(3)
                
                # Wait for Gmail to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    print("[Gmail] ✅ Opened Gmail in separate window")
                    self.gmail_tab_handle = self.driver.current_window_handle
                    return True
                except Exception as e:
                    print(f"[Gmail] ⚠️ Gmail page may not have loaded fully: {e}")
                    return True  # Continue anyway
            else:
                # Fallback: Open in new tab (original behavior)
                original_handle = self.driver.current_window_handle
                
                # Open Gmail in new tab
                self.driver.execute_script("window.open('https://mail.google.com', '_blank');")
                time.sleep(3)
                
                # Switch to the new tab
                handles = self.driver.window_handles
                for handle in handles:
                    if handle != original_handle:
                        self.driver.switch_to.window(handle)
                        self.gmail_tab_handle = handle
                        break
                
                # Wait for Gmail to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    print("[Gmail] Opened Gmail in new tab")
                    return True
                except:
                    print("[Gmail] Gmail page may not have loaded fully")
                    return True  # Continue anyway
                
        except Exception as e:
            print(f"[Gmail] Error opening Gmail: {e}")
            return False
    
    def switch_to_gmail_tab(self):
        """Switch to the Gmail window/tab if it exists"""
        try:
            # If we have a separate window, we're already in it
            if self.create_separate_window and self.own_driver:
                # Make sure we're on Gmail
                if "mail.google.com" not in self.driver.current_url:
                    self.driver.get("https://mail.google.com")
                    time.sleep(2)
                return True
            
            # Fallback: Switch to tab (original behavior)
            if self.gmail_tab_handle:
                self.driver.switch_to.window(self.gmail_tab_handle)
                return True
            else:
                # Try to find Gmail tab by URL
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    if "mail.google.com" in self.driver.current_url:
                        self.gmail_tab_handle = handle
                        return True
                return False
        except Exception as e:
            print(f"[Gmail] Error switching to Gmail: {e}")
            return False
    
    def gpt_analyze_email(self, subject_text, snippet_text=""):
        """Use GPT to analyze if email is important or just an update to delete"""
        if not self.openai_client:
            return None  # GPT not available, use pattern matching
        
        try:
            combined_text = f"{subject_text} {snippet_text}".strip()
            if len(combined_text) < 10:
                return None  # Not enough text to analyze
            
            prompt = f"""You are analyzing job application emails. Decide if this email should be DELETED (just a passive notification) or KEPT (requires action or is important).

EMAIL SUBJECT: {subject_text}
EMAIL PREVIEW/SNIPPET: {snippet_text}

DELETE these types (passive notifications, no action needed):
- "has viewed your application" / "viewed your application for [job]"
- "application update" (generic status updates)
- "viewed your profile" / "someone viewed your profile"
- "new activity on your application" (if it's just a view)
- "application received" confirmations (already submitted)
- Generic automated notifications that don't need response
- Emails that are purely informational with no next steps

KEEP these types (important, requires action):
- Interview invitations: "interview", "schedule", "meeting", "call"
- Action required: "next steps", "action required", "please respond", "requires your attention"
- Job offers or decisions: "offer", "congratulations", "decision", "selected"
- Important updates: "application status changed" (if it's a decision, not just a view)
- Response needed: "please reply", "respond by", "confirmation needed"
- Any email asking you to do something or respond

IMPORTANT: When in doubt, always choose KEEP. Better to keep an unimportant email than delete an important one.

Reply with ONLY one word: "DELETE" or "KEEP"."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {
                        "role": "system",
                        "content": "You are an email filtering assistant. Analyze emails and decide if they are important (KEEP) or just passive notifications (DELETE). Be conservative - when in doubt, KEEP the email."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=10,
                temperature=0.1  # Low temperature for consistent decisions
            )
            
            decision = response.choices[0].message.content.strip().upper()
            
            if "DELETE" in decision:
                return True
            elif "KEEP" in decision:
                return False
            else:
                # If GPT response is unclear, default to keeping
                return False
                
        except Exception as e:
            print(f"[Gmail] GPT analysis error: {e}")
            return None  # Fall back to pattern matching
    
    def should_delete_email(self, subject_text, snippet_text=""):
        """Check if email should be deleted - uses GPT if available, otherwise patterns"""
        combined_text = f"{subject_text} {snippet_text}".lower()
        
        # First check preserve patterns - if any match, DON'T delete (safety net)
        for pattern in self.preserve_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                print(f"[Gmail] PRESERVED (safety pattern): {subject_text[:50]}...")
                return False
        
        # Try GPT analysis first if available
        if self.openai_client:
            gpt_decision = self.gpt_analyze_email(subject_text, snippet_text)
            if gpt_decision is not None:
                if gpt_decision:
                    print(f"[Gmail] GPT says DELETE: {subject_text[:50]}...")
                else:
                    print(f"[Gmail] GPT says KEEP: {subject_text[:50]}...")
                return gpt_decision
        
        # Fallback to pattern matching if GPT unavailable or failed
        for pattern in self.delete_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                print(f"[Gmail] DELETE (pattern match): {subject_text[:50]}...")
                return True
        
        # Default: keep the email if no patterns match
        return False
    
    def get_email_elements(self):
        """Get all email elements from Gmail inbox - improved selectors"""
        try:
            # Wait for emails to load
            time.sleep(2)
            
            # Scroll to top to ensure we see all emails
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            
            # Modern Gmail uses these selectors (updated for current Gmail UI)
            email_selectors = [
                "tr[role='row']:not([style*='display: none'])",  # Standard email row (visible)
                "tr.zA",  # Gmail's main email row class
                "tr[jsaction*='click']",  # Clickable rows
                "div[role='main'] tr[role='row']",  # Email rows in main area
                "table tbody tr[role='row']",  # Table rows
                "div[data-thread-id]",  # Thread containers
                "tr[class*='zA']",  # Gmail row class variants
            ]
            
            emails = []
            for selector in email_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 5:  # Need at least a few to be valid
                        emails = elements
                        print(f"[Gmail] Found {len(elements)} emails using selector: {selector}")
                        break
                except:
                    continue
            
            # If no emails found, try a more aggressive search
            if not emails or len(emails) < 5:
                try:
                    # Try finding any table rows in the main content area
                    main_area = self.driver.find_element(By.CSS_SELECTOR, "div[role='main']")
                    emails = main_area.find_elements(By.CSS_SELECTOR, "tr")
                    if emails:
                        print(f"[Gmail] Found {len(emails)} emails using fallback method")
                except:
                    pass
            
            # Filter to only visible, clickable email rows
            visible_emails = []
            for email in emails:
                try:
                    if email.is_displayed():
                        # Check if it has meaningful content
                        text = email.text.strip()
                        if len(text) > 5:  # Has some content
                            # Make sure it's not a header or empty row
                            if "inbox" not in text.lower() or len(text) > 20:
                                visible_emails.append(email)
                except:
                    continue
            
            print(f"[Gmail] Found {len(visible_emails)} visible email rows")
            return visible_emails[:100]  # Increased limit for faster cleanup
            
        except Exception as e:
            print(f"[Gmail] Error getting email elements: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_email_text(self, email_element):
        """Extract subject and snippet text from email element - faster method"""
        try:
            # Get all text first (faster than multiple searches)
            all_text = email_element.text.strip()
            
            if not all_text:
                return "", ""
            
            # Split by newline
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            
            subject = ""
            snippet = ""
            
            # Try to find subject using selectors (quick check)
            subject_selectors = [
                ".bog",  # Gmail subject class
                ".bqe",  # Another subject class
                "span[email]",  # Subject span
                "span.yW span",  # Nested subject
                ".bA4",  # Subject in new Gmail
            ]
            
            for selector in subject_selectors:
                try:
                    subject_elem = email_element.find_element(By.CSS_SELECTOR, selector)
                    subject = subject_elem.text.strip()
                    if subject and len(subject) > 3:
                        break
                except:
                    continue
            
            # If no subject found via selector, use first meaningful line
            if not subject and lines:
                # First line is usually subject (skip empty/date lines)
                for line in lines[:3]:
                    if len(line) > 10 and not line.startswith(('Jan ', 'Feb ', 'Mar ', 'Apr ', 'May ', 'Jun ', 
                                                               'Jul ', 'Aug ', 'Sep ', 'Oct ', 'Nov ', 'Dec ')):
                        subject = line
                        break
            
            # Get snippet (usually 2nd or 3rd line)
            if lines and len(lines) > 1:
                snippet_lines = [l for l in lines[1:4] if l != subject and len(l) > 5]
                snippet = ' '.join(snippet_lines[:2])  # First 2 snippet lines
            
            return subject, snippet
            
        except Exception as e:
            print(f"[Gmail] Error getting email text: {e}")
            return "", ""
    
    def select_email(self, email_element):
        """Select an email by clicking its checkbox - improved method"""
        try:
            # Scroll email into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'auto'});", email_element)
            time.sleep(0.05)
            
            # Method 1: Try to find and click checkbox directly in the row
            checkbox_selectors = [
                "td:first-child input[type='checkbox']",  # First cell checkbox
                "td:first-child div[role='checkbox']",  # First cell checkbox div
                "input[type='checkbox']",  # Any checkbox in row
                "div[role='checkbox']",  # Checkbox div
                "td .T-Jo",  # Gmail checkbox class
                "td:first-child",  # First cell (where checkbox usually is)
            ]
            
            for selector in checkbox_selectors:
                try:
                    checkbox = email_element.find_element(By.CSS_SELECTOR, selector)
                    if checkbox.is_displayed():
                        # Try JavaScript click first (more reliable)
                        self.driver.execute_script("arguments[0].click();", checkbox)
                        time.sleep(0.05)
                        # Verify it's selected by checking aria-checked or checked attribute
                        checked = self.driver.execute_script("""
                            return arguments[0].getAttribute('aria-checked') === 'true' || 
                                   arguments[0].checked === true ||
                                   arguments[0].classList.contains('T-Jo-Jp');
                        """, checkbox)
                        if checked:
                            return True
                except:
                    continue
            
            # Method 2: Click on the left side of the row (where checkbox is visually)
            try:
                # Get the row's position and click where checkbox should be
                result = self.driver.execute_script("""
                    var row = arguments[0];
                    var rect = row.getBoundingClientRect();
                    // Click at x=30 (where checkbox usually is) and center of row
                    var x = rect.left + 30;
                    var y = rect.top + (rect.height / 2);
                    
                    // Create and dispatch click event
                    var clickEvent = new MouseEvent('mousedown', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: x,
                        clientY: y,
                        button: 0
                    });
                    row.dispatchEvent(clickEvent);
                    
                    var clickEvent2 = new MouseEvent('mouseup', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: x,
                        clientY: y,
                        button: 0
                    });
                    row.dispatchEvent(clickEvent2);
                    
                    var clickEvent3 = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: x,
                        clientY: y,
                        button: 0
                    });
                    row.dispatchEvent(clickEvent3);
                    
                    return true;
                """, email_element)
                time.sleep(0.1)
                return True
            except Exception as e:
                pass
            
            # Method 3: Try clicking the row itself (Gmail sometimes selects on row click)
            try:
                self.driver.execute_script("arguments[0].click();", email_element)
                time.sleep(0.05)
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            return False
    
    def delete_selected_emails(self):
        """Delete all selected emails - improved method"""
        try:
            # Method 1: Keyboard shortcut (fastest and most reliable)
            try:
                from selenium.webdriver.common.keys import Keys
                # Focus on the body to ensure keyboard events work
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.click()  # Focus first
                time.sleep(0.05)
                body.send_keys(Keys.DELETE)
                time.sleep(0.5)  # Wait for deletion to process
                print("[Gmail] Deleted using keyboard shortcut (Delete key)")
                return True
            except Exception as e:
                print(f"[Gmail] Keyboard shortcut failed: {e}")
            
            # Method 2: Find and click delete button in toolbar
            delete_selectors = [
                "div[aria-label*='Delete'][role='button']",
                "div[title*='Delete'][role='button']",
                "button[aria-label*='Delete']",
                "div[data-tooltip*='Delete'][role='button']",
                ".T-I[aria-label*='Delete']",
                ".T-I-J3[aria-label*='Delete']",
                "div[act='10']",  # Gmail delete action code
                "div[role='button'][aria-label*='Delete']",
                # Try finding by icon or text
                "div[aria-label='Delete']",
                "div[title='Delete']",
            ]
            
            for selector in delete_selectors:
                try:
                    delete_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if delete_btn.is_displayed() and delete_btn.is_enabled():
                        # Scroll into view
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", delete_btn)
                        time.sleep(0.1)
                        # Click using JavaScript (more reliable)
                        self.driver.execute_script("arguments[0].click();", delete_btn)
                        time.sleep(0.5)
                        print(f"[Gmail] Deleted using delete button (selector: {selector})")
                        return True
                except:
                    continue
            
            # Method 3: Try to find delete button by searching all buttons
            try:
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
                for btn in all_buttons:
                    try:
                        aria_label = btn.get_attribute("aria-label") or ""
                        title = btn.get_attribute("title") or ""
                        if "delete" in aria_label.lower() or "delete" in title.lower():
                            if btn.is_displayed():
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(0.5)
                                print("[Gmail] Deleted using delete button (found by searching)")
                                return True
                    except:
                        continue
            except:
                pass
            
            # Method 4: Use JavaScript to trigger delete action directly
            try:
                result = self.driver.execute_script("""
                    // Try to find and click delete button via DOM traversal
                    var buttons = document.querySelectorAll('div[role="button"]');
                    for (var i = 0; i < buttons.length; i++) {
                        var btn = buttons[i];
                        var label = (btn.getAttribute('aria-label') || '').toLowerCase();
                        var title = (btn.getAttribute('title') || '').toLowerCase();
                        if (label.includes('delete') || title.includes('delete')) {
                            if (btn.offsetParent !== null) { // Is visible
                                btn.click();
                                return true;
                            }
                        }
                    }
                    return false;
                """)
                if result:
                    time.sleep(0.5)
                    print("[Gmail] Deleted using JavaScript search")
                    return True
            except:
                pass
            
            print("[Gmail] Could not find delete button or method")
            return False
            
        except Exception as e:
            print(f"[Gmail] Error deleting emails: {e}")
            return False
    
    def analyze_emails_with_vision(self, emails):
        """Use GPT Vision to analyze visible emails from screenshot - cheaper than per-email"""
        if not self.openai_client:
            return []
        
        try:
            # Scroll to top to see all emails
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            
            # Take screenshot of the entire page (Gmail inbox)
            # This is more reliable than trying to screenshot a specific element
            screenshot = self.driver.get_screenshot_as_png()
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
            
            print("[Gmail] Analyzing emails with GPT Vision...")
            
            prompt = """You are analyzing a Gmail inbox screenshot. Your job is to identify which emails should be DELETED (passive notifications) vs KEPT (important, requires action).

Look at each email row in the list. For each email, identify:
1. The sender name
2. The subject line
3. Any visible snippet/preview text

DELETE these types (passive notifications, no action needed):
- "has viewed your application for [job title]"
- "has viewed your application"
- "application update" (generic status updates without action required)
- "viewed your profile"
- "application received" confirmations (already submitted)
- Generic automated notifications that don't need response
- Job closures ("job has closed")
- Emails that are purely informational with no next steps

KEEP these types (important, requires action):
- Interview invitations: "interview", "schedule", "meeting", "call"
- Action required: "next steps", "action required", "please respond", "requires your attention"
- Job offers or decisions: "offer", "congratulations", "decision", "selected"
- Response needed: "please reply", "respond by", "confirmation needed"
- Thank you emails that might need a response
- Any email asking you to do something or respond

IMPORTANT: When in doubt, always choose KEEP. Better to keep an unimportant email than delete an important one.

Reply with a JSON array of objects. Each object should have:
- "row_number": the row number (1 = top email, 2 = second, etc.)
- "sender": the sender name
- "subject": the subject line
- "action": either "DELETE" or "KEEP"
- "reason": brief reason (max 10 words)

Example format:
[
  {"row_number": 1, "sender": "SEEK Applications", "subject": "has viewed your application for Manager", "action": "DELETE", "reason": "passive notification"},
  {"row_number": 2, "sender": "Company HR", "subject": "Interview invitation", "action": "KEEP", "reason": "requires action"}
]

Only analyze emails that are clearly visible in the screenshot. If you can't read an email clearly, mark it as KEEP for safety."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective vision model
                messages=[
                    {
                        "role": "system",
                        "content": "You are an email filtering assistant. Analyze Gmail inbox screenshots and identify which emails should be deleted (passive notifications) vs kept (important, requires action). Be conservative - when in doubt, KEEP the email."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            # Try to extract JSON from the response (might have markdown code blocks)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            try:
                analysis = json.loads(result_text)
                print(f"[Gmail] GPT Vision analyzed {len(analysis)} emails")
                return analysis
            except json.JSONDecodeError as e:
                print(f"[Gmail] Failed to parse GPT Vision response: {e}")
                print(f"[Gmail] Response was: {result_text[:200]}...")
                return []
                
        except Exception as e:
            print(f"[Gmail] GPT Vision analysis error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def cleanup_emails(self, max_emails=50):
        """Main cleanup function - uses GPT Vision to analyze emails, then deletes them"""
        try:
            # Switch to Gmail window (make sure it's visible)
            if not self.switch_to_gmail_tab():
                if not self.open_gmail_tab():
                    print("[Gmail] Could not open/switch to Gmail window")
                    return False
            
            # Make sure the window is visible and active
            try:
                # If separate window, just refresh to get latest emails
                if self.create_separate_window and self.own_driver:
                    self.driver.refresh()
                else:
                    # Fallback: switch to tab and refresh
                    self.driver.switch_to.window(self.gmail_tab_handle)
                    self.driver.refresh()
            except:
                # If window/tab handle is lost, reopen
                if not self.open_gmail_tab():
                    return False
                self.driver.refresh()
            
            time.sleep(3)
            
            # Get email elements
            emails = self.get_email_elements()
            if not emails:
                print("[Gmail] No emails found")
                return False
            
            print(f"[Gmail] Found {len(emails)} emails to check")
            
            emails_to_delete = []
            
            # Use GPT Vision if available (cheaper than per-email analysis)
            if self.openai_client:
                print("[Gmail] Using GPT Vision to analyze emails from screenshot...")
                vision_analysis = self.analyze_emails_with_vision(emails[:max_emails])
                
                # Map vision analysis to actual email elements
                for analysis_item in vision_analysis:
                    try:
                        row_num = analysis_item.get("row_number", 0)
                        action = analysis_item.get("action", "KEEP")
                        sender = analysis_item.get("sender", "")
                        subject = analysis_item.get("subject", "")
                        reason = analysis_item.get("reason", "")
                        
                        # Row numbers are 1-indexed, array is 0-indexed
                        if 1 <= row_num <= len(emails):
                            email_element = emails[row_num - 1]
                            
                            if action == "DELETE":
                                emails_to_delete.append((email_element, subject or sender))
                                print(f"[Gmail] Vision says DELETE (row {row_num}): {subject[:50]}... - {reason}")
                            else:
                                print(f"[Gmail] Vision says KEEP (row {row_num}): {subject[:50]}... - {reason}")
                    except Exception as e:
                        print(f"[Gmail] Error processing vision analysis item: {e}")
                        continue
                
                if not emails_to_delete:
                    print("[Gmail] GPT Vision found no emails to delete")
                    return True
            
            # Fallback to text-based analysis if Vision didn't work or isn't available
            if not emails_to_delete and self.openai_client:
                print("[Gmail] Falling back to text-based GPT analysis...")
                for email in emails[:max_emails]:
                    try:
                        subject, snippet = self.get_email_text(email)
                        
                        if not subject and not snippet:
                            continue
                        
                        if self.should_delete_email(subject, snippet):
                            emails_to_delete.append((email, subject))
                            print(f"[Gmail] Text GPT says DELETE: {subject[:50]}...")
                    except Exception as e:
                        continue
            
            # Final fallback to pattern matching
            if not emails_to_delete:
                print("[Gmail] Using pattern matching fallback...")
                for email in emails[:max_emails]:
                    try:
                        subject, snippet = self.get_email_text(email)
                        
                        if not subject and not snippet:
                            continue
                        
                        # Use pattern matching
                        combined_text = f"{subject} {snippet}".lower()
                        
                        # Check preserve patterns first
                        should_preserve = False
                        for pattern in self.preserve_patterns:
                            if re.search(pattern, combined_text, re.IGNORECASE):
                                should_preserve = True
                                break
                        
                        if should_preserve:
                            continue
                        
                        # Check delete patterns
                        should_delete = False
                        for pattern in self.delete_patterns:
                            if re.search(pattern, combined_text, re.IGNORECASE):
                                should_delete = True
                                break
                        
                        if should_delete:
                            emails_to_delete.append((email, subject))
                            print(f"[Gmail] Pattern match DELETE: {subject[:50]}...")
                    except Exception as e:
                        continue
            
            if not emails_to_delete:
                print("[Gmail] No emails match deletion criteria")
                return True
            
            print(f"[Gmail] Found {len(emails_to_delete)} emails to delete")
            
            # Select emails in batches for faster processing
            deleted_count = 0
            batch_size = 10  # Select 10 at a time
            
            print(f"[Gmail] Starting batch deletion of {len(emails_to_delete)} emails...")
            
            for i in range(0, len(emails_to_delete), batch_size):
                batch = emails_to_delete[i:i+batch_size]
                batch_selected = 0
                
                print(f"[Gmail] Processing batch {i//batch_size + 1} ({len(batch)} emails)...")
                
                # Select batch
                for email_element, subject in batch:
                    try:
                        if self.select_email(email_element):
                            batch_selected += 1
                            print(f"[Gmail] ✓ Selected: {subject[:40]}...")
                        else:
                            print(f"[Gmail] ✗ Failed to select: {subject[:40]}...")
                    except Exception as e:
                        print(f"[Gmail] ✗ Error selecting email: {e}")
                        continue
                
                print(f"[Gmail] Selected {batch_selected} out of {len(batch)} emails in this batch")
                
                # Delete batch if any selected
                if batch_selected > 0:
                    time.sleep(0.2)  # Brief pause to let selection register
                    if self.delete_selected_emails():
                        deleted_count += batch_selected
                        print(f"[Gmail] ✓ Successfully deleted batch: {batch_selected} emails")
                        time.sleep(0.5)  # Brief pause between batches
                    else:
                        print(f"[Gmail] ✗ Failed to delete batch of {batch_selected} emails - trying again...")
                        # Try once more
                        time.sleep(0.3)
                        if self.delete_selected_emails():
                            deleted_count += batch_selected
                            print(f"[Gmail] ✓ Successfully deleted batch on retry: {batch_selected} emails")
                        else:
                            print(f"[Gmail] ✗ Failed to delete batch after retry")
                else:
                    print(f"[Gmail] No emails selected in this batch, skipping deletion")
            
            if deleted_count > 0:
                print(f"[Gmail] Successfully deleted {deleted_count} email(s) total")
                time.sleep(1)
                return True
            else:
                print("[Gmail] No emails were deleted")
                return False
            
        except Exception as e:
            print(f"[Gmail] Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_periodic_cleanup(self, interval_seconds=300):
        """Run cleanup periodically (every 5 minutes by default)"""
        try:
            while True:
                time.sleep(interval_seconds)
                print(f"[Gmail] Running periodic cleanup...")
                self.cleanup_emails()
        except Exception as e:
            print(f"[Gmail] Periodic cleanup stopped: {e}")


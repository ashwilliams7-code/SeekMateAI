"""
Email verification handler via IMAP.

Monitors inbox for verification emails during ATS account creation,
extracts OTP codes or verification links, and returns them to the engine.
Uses Python stdlib only (imaplib, email) - zero new dependencies.
"""

import imaplib
import email
from email.header import decode_header
import re
import time


class EmailVerifier:
    def __init__(self, config):
        self.imap_server = config.get("EMAIL_IMAP_SERVER", "imap.gmail.com")
        self.email_address = config.get("SEEK_EMAIL", config.get("EMAIL_ADDRESS", ""))
        self.app_password = config.get("EMAIL_APP_PASSWORD", "")
        self.imap = None

    def connect(self):
        """Connect to IMAP server. Returns True on success."""
        if not self.email_address or not self.app_password:
            print("    [Email] No email credentials configured (SEEK_EMAIL + EMAIL_APP_PASSWORD)")
            return False

        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server)
            self.imap.login(self.email_address, self.app_password)
            print(f"    [Email] Connected to {self.imap_server}")
            return True
        except imaplib.IMAP4.error as e:
            print(f"    [Email] IMAP login failed: {e}")
            return False
        except Exception as e:
            print(f"    [Email] Connection failed: {e}")
            return False

    def wait_for_verification(self, sender_hint=None, subject_hint=None, timeout=120):
        """
        Wait for a verification email and extract OTP or verification link.

        Args:
            sender_hint: Partial sender address to match (e.g., "workday", "smartrecruiters")
            subject_hint: Partial subject text to match (e.g., "verify", "confirm")
            timeout: Max seconds to wait

        Returns:
            dict with keys: type ("otp" or "link"), value (the code or URL), or None
        """
        if not self.imap:
            if not self.connect():
                return None

        print(f"    [Email] Waiting for verification email (timeout: {timeout}s)...")

        start_time = time.time()
        poll_interval = 5  # seconds

        # Mark current time to only look at new emails
        timestamp_before = time.time()

        while time.time() - start_time < timeout:
            result = self._check_for_verification(sender_hint, subject_hint, timestamp_before)
            if result:
                print(f"    [Email] Found verification: {result['type']} = {result['value'][:50]}...")
                return result

            time.sleep(poll_interval)

        print("    [Email] Timeout waiting for verification email")
        return None

    def _check_for_verification(self, sender_hint, subject_hint, since_timestamp):
        """Check inbox for recent verification emails."""
        try:
            self.imap.select("INBOX")

            # Search for recent unread emails
            search_criteria = '(UNSEEN)'
            status, messages = self.imap.search(None, search_criteria)

            if status != "OK":
                return None

            message_ids = messages[0].split()
            if not message_ids:
                return None

            # Check most recent emails first (last 10)
            for msg_id in reversed(message_ids[-10:]):
                try:
                    status, msg_data = self.imap.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Get sender
                    sender = self._decode_header(msg.get("From", ""))
                    subject = self._decode_header(msg.get("Subject", ""))

                    # Filter by sender hint
                    if sender_hint and sender_hint.lower() not in sender.lower():
                        continue

                    # Filter by subject hint
                    if subject_hint and subject_hint.lower() not in subject.lower():
                        continue

                    # Check if it looks like a verification email
                    subject_lower = subject.lower()
                    verification_indicators = [
                        "verify", "verification", "confirm", "activate",
                        "otp", "code", "one-time", "security code",
                        "complete your registration", "email confirmation",
                    ]
                    is_verification = any(ind in subject_lower for ind in verification_indicators)

                    if not is_verification and not sender_hint:
                        continue

                    # Extract body
                    body = self._get_email_body(msg)
                    if not body:
                        continue

                    # Try to extract OTP
                    otp = self.extract_otp(body)
                    if otp:
                        return {"type": "otp", "value": otp, "subject": subject}

                    # Try to extract verification link
                    link = self.extract_verification_link(body)
                    if link:
                        return {"type": "link", "value": link, "subject": subject}

                except Exception as e:
                    continue

        except Exception as e:
            print(f"    [Email] Error checking inbox: {e}")
            # Reconnect if connection lost
            try:
                self.connect()
            except Exception:
                pass

        return None

    def extract_otp(self, email_body):
        """Extract OTP/verification code from email body."""
        if not email_body:
            return None

        # Common OTP patterns (4-8 digit codes, often surrounded by specific text)
        otp_patterns = [
            r'(?:verification|confirm|security|one.?time|otp|code)[:\s]+(\d{4,8})',
            r'(\d{4,8})\s*(?:is your|is the|verification|confirm|security|otp)',
            r'(?:enter|use|type|input)[:\s]+(\d{4,8})',
            r'code[:\s]*["\']?(\d{4,8})["\']?',
            r'<strong>(\d{4,8})</strong>',
            r'<b>(\d{4,8})</b>',
            # Standalone 6-digit code (most common OTP length)
            r'\b(\d{6})\b',
        ]

        for pattern in otp_patterns:
            match = re.search(pattern, email_body, re.IGNORECASE)
            if match:
                code = match.group(1)
                # Validate: avoid matching phone numbers, years, zip codes
                if len(code) >= 4 and not self._is_likely_not_otp(code, email_body, match.start()):
                    return code

        return None

    def extract_verification_link(self, email_body):
        """Extract verification/confirmation link from email body."""
        if not email_body:
            return None

        # Find all URLs
        url_pattern = r'https?://[^\s<>"\']+'
        urls = re.findall(url_pattern, email_body)

        # Score URLs by verification likelihood
        verification_keywords = [
            "verify", "confirm", "activate", "validate", "registration",
            "auth", "token", "click", "complete", "email-verification",
        ]
        exclude_keywords = [
            "unsubscribe", "privacy", "terms", "policy", "logo",
            "facebook", "twitter", "linkedin", "instagram", ".png",
            ".jpg", ".gif", ".css", ".js",
        ]

        for url in urls:
            url_lower = url.lower()
            if any(kw in url_lower for kw in exclude_keywords):
                continue
            if any(kw in url_lower for kw in verification_keywords):
                # Clean trailing punctuation
                url = url.rstrip(".,;:!?)")
                return url

        return None

    def disconnect(self):
        """Close IMAP connection."""
        if self.imap:
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None

    # --- Helpers ---

    def _decode_header(self, header_value):
        """Decode an email header value."""
        if not header_value:
            return ""
        decoded_parts = decode_header(header_value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)

    def _get_email_body(self, msg):
        """Extract the text body from an email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        if body:
                            return body
                    except Exception:
                        continue
                elif content_type == "text/html" and not body:
                    try:
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        continue
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
            except Exception:
                pass
        return body

    def _is_likely_not_otp(self, code, body, position):
        """Check if a number match is likely NOT an OTP (e.g., year, phone, zip)."""
        code_int = int(code)

        # Year range
        if 1900 <= code_int <= 2100:
            return True

        # Check surrounding context for phone-like patterns
        start = max(0, position - 20)
        context = body[start:position + len(code) + 20].lower()
        phone_indicators = ["phone", "tel", "call", "fax", "mobile", "+61", "+1"]
        if any(ind in context for ind in phone_indicators):
            return True

        return False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

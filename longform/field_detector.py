"""
Universal form field detection.

Detects and categorizes ALL form fields on any HTML page regardless of ATS portal.
Extracts labels, options, requirements, and metadata for each field.
"""

from dataclasses import dataclass, field
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re


@dataclass
class FormField:
    element: object  # WebElement
    field_type: str  # text, textarea, select, radio, checkbox, file, date, number, tel, email, password, hidden
    label: str = ""
    name: str = ""
    field_id: str = ""
    required: bool = False
    options: list = field(default_factory=list)
    current_value: str = ""
    max_length: int = 0
    placeholder: str = ""
    group_name: str = ""
    is_visible: bool = True
    aria_label: str = ""


class FieldDetector:
    def __init__(self, driver):
        self.driver = driver

    def detect_fields(self):
        """Detect all fillable form fields on the current page."""
        fields = []

        # Text inputs
        fields.extend(self._detect_text_inputs())

        # Textareas
        fields.extend(self._detect_textareas())

        # Select dropdowns
        fields.extend(self._detect_selects())

        # Radio button groups
        fields.extend(self._detect_radio_groups())

        # Checkbox groups
        fields.extend(self._detect_checkbox_groups())

        # File upload inputs
        fields.extend(self._detect_file_inputs())

        return fields

    def _detect_text_inputs(self):
        """Detect text-type input fields (text, email, tel, number, date, url, password)."""
        fields = []
        text_types = ["text", "email", "tel", "number", "date", "url", "password"]

        for input_type in text_types:
            try:
                elements = self.driver.find_elements(
                    By.CSS_SELECTOR, f"input[type='{input_type}']"
                )
                for el in elements:
                    if not self._is_visible(el):
                        continue
                    if self._is_hidden_or_honeypot(el):
                        continue

                    fields.append(FormField(
                        element=el,
                        field_type=input_type,
                        label=self._get_label(el),
                        name=el.get_attribute("name") or "",
                        field_id=el.get_attribute("id") or "",
                        required=self._is_required(el),
                        current_value=el.get_attribute("value") or "",
                        max_length=self._get_max_length(el),
                        placeholder=el.get_attribute("placeholder") or "",
                        aria_label=el.get_attribute("aria-label") or "",
                        is_visible=True,
                    ))
            except Exception:
                continue

        # Also detect inputs without explicit type (default to text)
        try:
            elements = self.driver.find_elements(
                By.CSS_SELECTOR, "input:not([type])"
            )
            for el in elements:
                if not self._is_visible(el):
                    continue
                if self._is_hidden_or_honeypot(el):
                    continue
                fields.append(FormField(
                    element=el,
                    field_type="text",
                    label=self._get_label(el),
                    name=el.get_attribute("name") or "",
                    field_id=el.get_attribute("id") or "",
                    required=self._is_required(el),
                    current_value=el.get_attribute("value") or "",
                    max_length=self._get_max_length(el),
                    placeholder=el.get_attribute("placeholder") or "",
                    aria_label=el.get_attribute("aria-label") or "",
                    is_visible=True,
                ))
        except Exception:
            pass

        return fields

    def _detect_textareas(self):
        """Detect textarea fields."""
        fields = []
        try:
            elements = self.driver.find_elements(By.TAG_NAME, "textarea")
            for el in elements:
                if not self._is_visible(el):
                    continue

                fields.append(FormField(
                    element=el,
                    field_type="textarea",
                    label=self._get_label(el),
                    name=el.get_attribute("name") or "",
                    field_id=el.get_attribute("id") or "",
                    required=self._is_required(el),
                    current_value=el.get_attribute("value") or el.text or "",
                    max_length=self._get_max_length(el),
                    placeholder=el.get_attribute("placeholder") or "",
                    aria_label=el.get_attribute("aria-label") or "",
                    is_visible=True,
                ))
        except Exception:
            pass
        return fields

    def _detect_selects(self):
        """Detect select/dropdown fields."""
        fields = []
        try:
            elements = self.driver.find_elements(By.TAG_NAME, "select")
            for el in elements:
                if not self._is_visible(el):
                    continue

                options = []
                try:
                    option_elements = el.find_elements(By.TAG_NAME, "option")
                    options = [opt.text.strip() for opt in option_elements if opt.text.strip()]
                except Exception:
                    pass

                current = ""
                try:
                    from selenium.webdriver.support.ui import Select
                    sel = Select(el)
                    current = sel.first_selected_option.text.strip()
                except Exception:
                    pass

                fields.append(FormField(
                    element=el,
                    field_type="select",
                    label=self._get_label(el),
                    name=el.get_attribute("name") or "",
                    field_id=el.get_attribute("id") or "",
                    required=self._is_required(el),
                    options=options,
                    current_value=current,
                    aria_label=el.get_attribute("aria-label") or "",
                    is_visible=True,
                ))
        except Exception:
            pass
        return fields

    def _detect_radio_groups(self):
        """Detect radio button groups, grouped by name attribute."""
        fields = []
        seen_groups = set()
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            for el in elements:
                group_name = el.get_attribute("name") or ""
                if group_name in seen_groups:
                    continue
                seen_groups.add(group_name)

                # Get all radios in this group
                group_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, f"input[type='radio'][name='{group_name}']"
                ) if group_name else [el]

                options = []
                for radio in group_elements:
                    label_text = self._get_radio_checkbox_label(radio)
                    if label_text:
                        options.append(label_text)

                # Get the group question from fieldset/legend or parent context
                group_label = self._get_group_label(el)

                current = ""
                for radio in group_elements:
                    if radio.is_selected():
                        current = self._get_radio_checkbox_label(radio)
                        break

                fields.append(FormField(
                    element=group_elements[0] if group_elements else el,
                    field_type="radio",
                    label=group_label,
                    name=group_name,
                    field_id=el.get_attribute("id") or "",
                    required=self._is_required(el),
                    options=options,
                    current_value=current,
                    group_name=group_name,
                    is_visible=True,
                ))
        except Exception:
            pass
        return fields

    def _detect_checkbox_groups(self):
        """Detect checkbox fields/groups."""
        fields = []
        seen_groups = set()
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            for el in elements:
                group_name = el.get_attribute("name") or el.get_attribute("id") or ""

                # Group checkboxes by name prefix
                base_name = re.sub(r'\[\d*\]$', '', group_name)
                if base_name in seen_groups:
                    continue

                # Find all checkboxes with same base name
                if base_name:
                    group_elements = [
                        cb for cb in elements
                        if re.sub(r'\[\d*\]$', '', cb.get_attribute("name") or "") == base_name
                    ]
                else:
                    group_elements = [el]

                if len(group_elements) > 1:
                    seen_groups.add(base_name)

                options = []
                selected = []
                for cb in group_elements:
                    label_text = self._get_radio_checkbox_label(cb)
                    if label_text:
                        options.append(label_text)
                        if cb.is_selected():
                            selected.append(label_text)

                group_label = self._get_group_label(el)

                fields.append(FormField(
                    element=group_elements[0] if group_elements else el,
                    field_type="checkbox",
                    label=group_label or self._get_radio_checkbox_label(el),
                    name=base_name,
                    field_id=el.get_attribute("id") or "",
                    required=self._is_required(el),
                    options=options,
                    current_value=", ".join(selected),
                    group_name=base_name,
                    is_visible=True,
                ))
        except Exception:
            pass
        return fields

    def _detect_file_inputs(self):
        """Detect file upload inputs."""
        fields = []
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            for el in elements:
                fields.append(FormField(
                    element=el,
                    field_type="file",
                    label=self._get_label(el),
                    name=el.get_attribute("name") or "",
                    field_id=el.get_attribute("id") or "",
                    required=self._is_required(el),
                    aria_label=el.get_attribute("aria-label") or "",
                    # File inputs may be hidden but still functional
                    is_visible=True,
                ))
        except Exception:
            pass
        return fields

    def detect_submit_button(self):
        """Find the submit/apply button on the page."""
        submit_patterns = [
            "//button[@type='submit']",
            "//input[@type='submit']",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send application')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
        ]
        for xpath in submit_patterns:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if self._is_visible(el):
                        return el
            except Exception:
                continue
        return None

    def detect_next_button(self):
        """Find the next/continue button on the page."""
        next_patterns = [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save and continue')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'proceed')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
            "//input[@type='submit' and (contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next') or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue'))]",
        ]
        for xpath in next_patterns:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if self._is_visible(el):
                        return el
            except Exception:
                continue
        return None

    def detect_errors(self):
        """Detect form validation error messages on the page."""
        errors = []
        error_selectors = [
            "[class*='error']",
            "[class*='Error']",
            "[class*='invalid']",
            "[class*='validation']",
            "[role='alert']",
            ".field-error",
            ".form-error",
            ".error-message",
            ".validation-error",
        ]
        for selector in error_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    text = el.text.strip()
                    if text and len(text) < 500 and self._is_visible(el):
                        errors.append(text)
            except Exception:
                continue

        # Also check for aria-invalid fields
        try:
            invalid = self.driver.find_elements(By.CSS_SELECTOR, "[aria-invalid='true']")
            for el in invalid:
                label = self._get_label(el)
                if label:
                    errors.append(f"Field '{label}' is invalid")
        except Exception:
            pass

        return list(set(errors))  # deduplicate

    # --- Label extraction helpers ---

    def _get_label(self, element):
        """Extract the label/question text for a form element using multiple strategies."""
        label_text = ""

        # Strategy 1: <label for="id">
        field_id = element.get_attribute("id")
        if field_id:
            try:
                label_el = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                label_text = label_el.text.strip()
                if label_text:
                    return self._clean_label(label_text)
            except Exception:
                pass

        # Strategy 2: Parent <label> wrapping the input
        try:
            parent = element.find_element(By.XPATH, "./ancestor::label")
            label_text = parent.text.strip()
            if label_text:
                return self._clean_label(label_text)
        except Exception:
            pass

        # Strategy 3: aria-label attribute
        aria = element.get_attribute("aria-label")
        if aria:
            return self._clean_label(aria)

        # Strategy 4: aria-labelledby reference
        labelled_by = element.get_attribute("aria-labelledby")
        if labelled_by:
            try:
                ref_el = self.driver.find_element(By.ID, labelled_by)
                label_text = ref_el.text.strip()
                if label_text:
                    return self._clean_label(label_text)
            except Exception:
                pass

        # Strategy 5: Preceding sibling label or text
        try:
            preceding = element.find_element(By.XPATH, "./preceding-sibling::label[1]")
            label_text = preceding.text.strip()
            if label_text:
                return self._clean_label(label_text)
        except Exception:
            pass

        # Strategy 6: Parent div with label-like text
        try:
            parent = element.find_element(By.XPATH, "./..")
            children = parent.find_elements(By.XPATH, "./*")
            for child in children:
                if child == element:
                    break
                text = child.text.strip()
                if text and len(text) < 200:
                    label_text = text
                    break
            if label_text:
                return self._clean_label(label_text)
        except Exception:
            pass

        # Strategy 7: Placeholder as last resort
        placeholder = element.get_attribute("placeholder")
        if placeholder:
            return self._clean_label(placeholder)

        # Strategy 8: Name attribute cleaned up
        name = element.get_attribute("name")
        if name:
            return self._clean_label(name.replace("_", " ").replace("-", " ").replace("[", " ").replace("]", ""))

        return ""

    def _get_radio_checkbox_label(self, element):
        """Get the label for a specific radio button or checkbox option."""
        # Check for associated label
        field_id = element.get_attribute("id")
        if field_id:
            try:
                label_el = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                text = label_el.text.strip()
                if text:
                    return text
            except Exception:
                pass

        # Check parent label
        try:
            parent = element.find_element(By.XPATH, "./ancestor::label")
            text = parent.text.strip()
            if text:
                return text
        except Exception:
            pass

        # Check next sibling text
        try:
            sibling = element.find_element(By.XPATH, "./following-sibling::*[1]")
            text = sibling.text.strip()
            if text:
                return text
        except Exception:
            pass

        # Value attribute
        value = element.get_attribute("value")
        if value:
            return value

        return ""

    def _get_group_label(self, element):
        """Get the question/label for a radio/checkbox group (from fieldset/legend or parent context)."""
        # Strategy 1: fieldset > legend
        try:
            fieldset = element.find_element(By.XPATH, "./ancestor::fieldset")
            legend = fieldset.find_element(By.TAG_NAME, "legend")
            text = legend.text.strip()
            if text:
                return self._clean_label(text)
        except Exception:
            pass

        # Strategy 2: Parent with question-like text
        try:
            parent = element.find_element(By.XPATH, "./ancestor::div[.//input[@type='radio'] or .//input[@type='checkbox']]")
            # Find first text node that looks like a question
            children = parent.find_elements(By.XPATH, "./*")
            for child in children:
                tag = child.tag_name.lower()
                if tag in ("label", "legend", "h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "div"):
                    text = child.text.strip()
                    if text and len(text) > 5 and not any(
                        radio_text in text for radio_text in
                        [opt.text.strip() for opt in parent.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")]
                    ):
                        return self._clean_label(text)
        except Exception:
            pass

        # Strategy 3: aria-label on group container
        try:
            group = element.find_element(By.XPATH, "./ancestor::*[@role='radiogroup' or @role='group']")
            aria = group.get_attribute("aria-label")
            if aria:
                return self._clean_label(aria)
            labelled_by = group.get_attribute("aria-labelledby")
            if labelled_by:
                ref = self.driver.find_element(By.ID, labelled_by)
                return self._clean_label(ref.text.strip())
        except Exception:
            pass

        return ""

    # --- Utility helpers ---

    def _is_visible(self, element):
        """Check if element is visible on page."""
        try:
            if not element.is_displayed():
                return False
            size = element.size
            if size["width"] == 0 and size["height"] == 0:
                return False
            return True
        except Exception:
            return False

    def _is_hidden_or_honeypot(self, element):
        """Detect honeypot/hidden fields used for bot detection."""
        try:
            name = (element.get_attribute("name") or "").lower()
            field_id = (element.get_attribute("id") or "").lower()
            autocomplete = (element.get_attribute("autocomplete") or "").lower()

            honeypot_indicators = ["honeypot", "hp_", "trap", "bot", "website_url", "fax"]
            for indicator in honeypot_indicators:
                if indicator in name or indicator in field_id:
                    return True

            if autocomplete == "off" and element.get_attribute("tabindex") == "-1":
                return True

            # Check if hidden via style
            style = element.get_attribute("style") or ""
            if "display: none" in style or "visibility: hidden" in style or "opacity: 0" in style:
                return True

            return False
        except Exception:
            return False

    def _is_required(self, element):
        """Check if field is required."""
        try:
            if element.get_attribute("required") is not None:
                return True
            if element.get_attribute("aria-required") == "true":
                return True
            label = self._get_label(element)
            if label and "*" in label:
                return True
            return False
        except Exception:
            return False

    def _get_max_length(self, element):
        """Get max character length for a field."""
        try:
            ml = element.get_attribute("maxlength")
            if ml:
                return int(ml)
        except (ValueError, TypeError):
            pass
        return 0

    def _clean_label(self, text):
        """Clean up label text - remove asterisks, extra whitespace, etc."""
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.rstrip('*').strip()
        return text

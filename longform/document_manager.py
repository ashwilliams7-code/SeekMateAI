"""
Document selection and upload manager.

Manages a local document repository (resumes, cover letters, certificates)
and handles file upload inputs on ATS portals.
"""

import os
import re
from pathlib import Path


class DocumentManager:
    def __init__(self, driver, config):
        self.driver = driver
        self.config = config
        self.docs_dir = config.get("DOCUMENTS_DIR", "./documents")
        self.default_resume = config.get("DEFAULT_RESUME", "")
        self.resume_map = config.get("RESUME_MAP", {})

        # Ensure documents directory exists
        os.makedirs(os.path.join(self.docs_dir, "resumes"), exist_ok=True)
        os.makedirs(os.path.join(self.docs_dir, "cover_letters"), exist_ok=True)
        os.makedirs(os.path.join(self.docs_dir, "certificates"), exist_ok=True)

    def get_resume(self, job_title=None):
        """
        Get the best resume file path for a job.
        Checks resume_map for title-specific resumes, falls back to default.
        """
        # Check title-specific resume mapping
        if job_title and self.resume_map:
            title_lower = job_title.lower()
            for keyword, filename in self.resume_map.items():
                if keyword.lower() in title_lower:
                    path = self._resolve_path("resumes", filename)
                    if path:
                        return path

        # Default resume
        if self.default_resume:
            path = self._resolve_path("resumes", self.default_resume)
            if path:
                return path

        # Fallback: use CV_PATH from existing config
        cv_path = self.config.get("CV_PATH", "")
        if cv_path and os.path.exists(cv_path):
            return os.path.abspath(cv_path)

        # Last resort: find any PDF in resumes folder
        resumes_dir = os.path.join(self.docs_dir, "resumes")
        if os.path.exists(resumes_dir):
            for f in os.listdir(resumes_dir):
                if f.lower().endswith((".pdf", ".docx", ".doc")):
                    return os.path.abspath(os.path.join(resumes_dir, f))

        print("    [Docs] Warning: No resume found")
        return None

    def get_cover_letter(self, job_title=None):
        """Get a cover letter file path. For long-form, cover letters are usually typed into fields."""
        cl_dir = os.path.join(self.docs_dir, "cover_letters")
        if job_title:
            # Check for job-specific cover letter
            safe_name = re.sub(r'[^\w\s-]', '', job_title).strip().replace(' ', '_')
            for ext in [".pdf", ".docx", ".txt"]:
                path = os.path.join(cl_dir, f"cover_letter_{safe_name}{ext}")
                if os.path.exists(path):
                    return os.path.abspath(path)

        # Generic cover letter
        if os.path.exists(cl_dir):
            for f in os.listdir(cl_dir):
                if f.lower().startswith("cover") and f.lower().endswith((".pdf", ".docx", ".txt")):
                    return os.path.abspath(os.path.join(cl_dir, f))

        return None

    def get_document(self, doc_type):
        """
        Get a document by type keyword.
        Searches certificates folder for matching files.

        Args:
            doc_type: keyword like "license", "passport", "certification", "working with children"
        """
        cert_dir = os.path.join(self.docs_dir, "certificates")
        if not os.path.exists(cert_dir):
            return None

        doc_type_lower = doc_type.lower()
        for f in os.listdir(cert_dir):
            if doc_type_lower.replace(" ", "_") in f.lower().replace(" ", "_"):
                return os.path.abspath(os.path.join(cert_dir, f))
            if doc_type_lower.replace(" ", "") in f.lower().replace(" ", "").replace("_", ""):
                return os.path.abspath(os.path.join(cert_dir, f))

        return None

    def upload_to_field(self, file_input, file_path):
        """
        Upload a file to a file input element.

        Args:
            file_input: Selenium WebElement of type file input
            file_path: Absolute path to the file to upload

        Returns:
            True if upload succeeded
        """
        if not file_path or not os.path.exists(file_path):
            print(f"    [Docs] File not found: {file_path}")
            return False

        abs_path = os.path.abspath(file_path)
        print(f"    [Docs] Uploading: {os.path.basename(abs_path)}")

        try:
            file_input.send_keys(abs_path)
            return True
        except Exception as e:
            print(f"    [Docs] Upload failed: {e}")
            # Try making the element visible first (some file inputs are hidden)
            try:
                self.driver.execute_script("""
                    arguments[0].style.display = 'block';
                    arguments[0].style.visibility = 'visible';
                    arguments[0].style.opacity = '1';
                    arguments[0].style.height = 'auto';
                    arguments[0].style.width = 'auto';
                    arguments[0].style.position = 'relative';
                """, file_input)
                file_input.send_keys(abs_path)
                return True
            except Exception as e2:
                print(f"    [Docs] Upload retry failed: {e2}")
                return False

    def detect_upload_type(self, label):
        """
        Determine what type of document an upload field is asking for based on its label.

        Returns: "resume", "cover_letter", "certificate", or "unknown"
        """
        label_lower = (label or "").lower()

        resume_keywords = ["resume", "cv", "curriculum vitae"]
        cover_letter_keywords = ["cover letter", "covering letter", "letter of application"]
        cert_keywords = [
            "certificate", "certification", "license", "licence",
            "qualification", "credential", "passport", "identification",
            "drivers license", "working with children", "police check",
            "first aid", "diploma", "transcript",
        ]

        if any(kw in label_lower for kw in resume_keywords):
            return "resume"
        if any(kw in label_lower for kw in cover_letter_keywords):
            return "cover_letter"
        if any(kw in label_lower for kw in cert_keywords):
            return "certificate"

        return "unknown"

    def handle_file_upload(self, field):
        """
        Handle a file upload field by detecting what it wants and uploading the right document.

        Args:
            field: FormField instance with field_type="file"

        Returns:
            str: filename uploaded, or None if failed
        """
        label = field.label or field.aria_label or field.name
        upload_type = self.detect_upload_type(label)

        file_path = None
        if upload_type == "resume":
            file_path = self.get_resume()
        elif upload_type == "cover_letter":
            file_path = self.get_cover_letter()
        elif upload_type == "certificate":
            # Try to match specific certificate from label
            file_path = self.get_document(label)
        else:
            # Unknown type - try resume as default
            file_path = self.get_resume()

        if file_path:
            success = self.upload_to_field(field.element, file_path)
            if success:
                return os.path.basename(file_path)

        return None

    def list_available_documents(self):
        """List all available documents in the repository."""
        docs = {"resumes": [], "cover_letters": [], "certificates": []}

        for category in docs.keys():
            dir_path = os.path.join(self.docs_dir, category)
            if os.path.exists(dir_path):
                docs[category] = [
                    f for f in os.listdir(dir_path)
                    if not f.startswith(".") and os.path.isfile(os.path.join(dir_path, f))
                ]

        return docs

    # --- Internal helpers ---

    def _resolve_path(self, subfolder, filename):
        """Resolve a filename to an absolute path within the documents directory."""
        path = os.path.join(self.docs_dir, subfolder, filename)
        if os.path.exists(path):
            return os.path.abspath(path)
        # Try without subfolder
        path = os.path.join(self.docs_dir, filename)
        if os.path.exists(path):
            return os.path.abspath(path)
        return None

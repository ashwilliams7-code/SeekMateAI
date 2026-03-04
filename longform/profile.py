"""
Master user profile loader.

Loads structured user data from master_profile.json and provides it
as formatted context for GPT prompts and direct form filling.
"""

import json
import os


class MasterProfile:
    def __init__(self, profile_path="master_profile.json"):
        self.profile_path = profile_path
        self.data = {}
        self.load()

    def load(self):
        """Load profile from JSON file."""
        if not os.path.exists(self.profile_path):
            print(f"    [Profile] Warning: {self.profile_path} not found, using empty profile")
            self.data = self._default_profile()
            return self.data

        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        return self.data

    def _default_profile(self):
        return {
            "personal": {"full_name": "", "first_name": "", "last_name": "",
                         "email": "", "phone": "", "location": "",
                         "street": "", "city": "", "suburb": "", "state": "",
                         "postcode": "", "country": "Australia",
                         "linkedin_url": "", "website": "", "summary": ""},
            "work_rights": {"citizenship": "", "visa_status": "", "right_to_work": ""},
            "work_history": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "licenses": [],
            "salary_expectations": {"minimum": 0, "preferred": 0, "currency": "AUD"},
            "preferences": {"work_type": "Full Time", "notice_period": "",
                            "willing_to_relocate": False, "preferred_locations": []},
        }

    def get_field(self, field_path):
        """Get a nested field value using dot notation (e.g., 'personal.full_name')."""
        keys = field_path.split(".")
        val = self.data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key, "")
            else:
                return ""
        return val if val else ""

    def get_personal(self):
        return self.data.get("personal", {})

    def get_work_history(self):
        return self.data.get("work_history", [])

    def get_education(self):
        return self.data.get("education", [])

    def get_skills(self):
        return self.data.get("skills", [])

    def get_certifications(self):
        return self.data.get("certifications", [])

    def get_salary_expectations(self):
        return self.data.get("salary_expectations", {})

    def get_work_rights(self):
        return self.data.get("work_rights", {})

    def get_preferences(self):
        return self.data.get("preferences", {})

    def to_prompt_context(self):
        """Format entire profile as a text block for GPT system prompts."""
        p = self.data.get("personal", {})
        wr = self.data.get("work_rights", {})
        sal = self.data.get("salary_expectations", {})
        prefs = self.data.get("preferences", {})

        lines = []
        lines.append("=== CANDIDATE PROFILE ===")

        if p.get("full_name"):
            lines.append(f"Name: {p['full_name']}")
        if p.get("location"):
            lines.append(f"Location: {p['location']}")
        if p.get("phone"):
            lines.append(f"Phone: {p['phone']}")
        if p.get("email"):
            lines.append(f"Email: {p['email']}")
        if p.get("summary"):
            lines.append(f"\nProfessional Summary: {p['summary']}")

        if wr.get("citizenship"):
            lines.append(f"Citizenship: {wr['citizenship']}")
        if wr.get("right_to_work"):
            lines.append(f"Right to Work: {wr['right_to_work']}")

        work_history = self.data.get("work_history", [])
        if work_history:
            lines.append("\nWork History:")
            for job in work_history[:5]:
                period = f"{job.get('start_date', '')} - {job.get('end_date', 'Present')}"
                lines.append(f"  - {job.get('title', '')} at {job.get('company', '')} ({period})")
                if job.get("description"):
                    lines.append(f"    {job['description'][:200]}")

        education = self.data.get("education", [])
        if education:
            lines.append("\nEducation:")
            for edu in education:
                lines.append(f"  - {edu.get('degree', '')} in {edu.get('field', '')} "
                             f"from {edu.get('institution', '')} ({edu.get('year', '')})")

        skills = self.data.get("skills", [])
        if skills:
            lines.append(f"\nSkills: {', '.join(skills[:20])}")

        certs = self.data.get("certifications", [])
        if certs:
            lines.append(f"Certifications: {', '.join(certs)}")

        licenses = self.data.get("licenses", [])
        if licenses:
            lines.append(f"Licenses: {', '.join(licenses)}")

        if sal.get("preferred"):
            lines.append(f"\nSalary Expectation: ${sal['preferred']:,} {sal.get('currency', 'AUD')}")

        if prefs.get("work_type"):
            lines.append(f"Work Type: {prefs['work_type']}")
        if prefs.get("notice_period"):
            lines.append(f"Notice Period: {prefs['notice_period']}")

        return "\n".join(lines)

    def fill_from_config(self, config):
        """Backfill profile fields from existing config.json values if profile is sparse."""
        personal = self.data.setdefault("personal", {})
        sal = self.data.setdefault("salary_expectations", {})

        if not personal.get("full_name") and config.get("FULL_NAME"):
            personal["full_name"] = config["FULL_NAME"]
        if not personal.get("location") and config.get("LOCATION"):
            personal["location"] = config["LOCATION"]
        if not personal.get("email") and config.get("SEEK_EMAIL"):
            personal["email"] = config["SEEK_EMAIL"]
        if not sal.get("preferred") and config.get("EXPECTED_SALARY"):
            try:
                sal["preferred"] = int(config["EXPECTED_SALARY"])
            except (ValueError, TypeError):
                pass

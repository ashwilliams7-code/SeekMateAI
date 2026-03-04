"""
AI-powered answer generation for long-form job applications.

Uses the existing OpenAI GPT wrapper to generate tailored, professional answers.
Includes rule-based shortcuts for common questions (salary, location, work rights)
to minimize API calls and maximize consistency.
"""

import re
import json


# Keywords for classifying questions by category
PERSONAL_KEYWORDS = {
    "first_name": ["first name", "given name"],
    "last_name": ["last name", "surname", "family name"],
    "full_name": ["full name", "your name", "name of applicant", "applicant name"],
    "email": ["email", "e-mail"],
    "phone": ["phone", "mobile", "telephone", "contact number", "cell"],
    "street": ["street", "address line 1", "address line1", "street address"],
    "street2": ["street cont", "address line 2", "address line2", "unit", "apartment", "apt"],
    "city": ["city", "town", "suburb"],
    "postcode": ["postcode", "zip", "postal code", "zip code", "zipcode"],
    "state": ["state", "region", "province"],
    "country": ["country"],
    "linkedin": ["linkedin"],
    "website": ["website", "portfolio", "personal url", "personal site"],
}

WORK_RIGHTS_KEYWORDS = [
    "right to work", "work rights", "visa", "citizen", "residency",
    "authorized to work", "authorised to work", "eligible to work",
    "sponsorship", "work permit", "legal right",
]

SALARY_KEYWORDS = [
    "salary", "expected salary", "salary expectation", "remuneration",
    "pay", "compensation", "desired salary", "annual salary", "rate",
]

START_DATE_KEYWORDS = [
    "start date", "available to start", "availability", "earliest start",
    "when can you start", "notice period", "commencement",
]

EXPERIENCE_KEYWORDS = [
    "years of experience", "how many years", "experience in",
    "how long have you", "total experience",
]

YES_NO_KEYWORDS = [
    "do you have", "are you", "have you", "can you", "will you",
    "would you", "did you", "is your",
]


class AIResponder:
    def __init__(self, gpt_func, profile, job_context):
        """
        Args:
            gpt_func: The existing gpt(system_prompt, user_prompt) function from SeekBot
            profile: MasterProfile instance
            job_context: dict with keys: title, company, description, job_url
        """
        self.gpt = gpt_func
        self.profile = profile
        self.job_context = job_context
        self._cache = {}  # Cache answers by question label

        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        """Build the system prompt with profile and job context."""
        profile_ctx = self.profile.to_prompt_context()
        job_title = self.job_context.get("title", "")
        company = self.job_context.get("company", "")
        description = self.job_context.get("description", "")

        # Truncate description to avoid token limits
        if len(description) > 3000:
            description = description[:3000] + "..."

        return f"""You are {self.profile.get_field('personal.full_name') or 'a senior professional'}, \
writing your own job application answers. You are applying for {job_title} at {company}.

{profile_ctx}

=== JOB DETAILS ===
Title: {job_title}
Company: {company}
Description: {description}

RULES:
- Write in first person as the candidate
- Be concise, confident, and professional
- Use specific examples from work history when relevant
- Never fabricate qualifications not in the profile
- Match the tone to a senior-level applicant
- Respect any character limits mentioned
- Do NOT include greetings, sign-offs, or the candidate's name unless asked
- Answer the actual question directly"""

    def answer_text_question(self, label, max_length=None):
        """Generate a text answer for a free-form question."""
        if not label or len(label.strip()) < 3:
            return ""

        # Check cache
        cache_key = label.strip().lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try rule-based answer first
        rule_answer = self._try_rule_based(label)
        if rule_answer:
            self._cache[cache_key] = rule_answer
            return rule_answer

        # Build GPT prompt
        length_hint = ""
        if max_length and max_length > 0:
            if max_length <= 100:
                length_hint = f"Keep your answer under {max_length} characters. Be very brief (1-2 sentences)."
            elif max_length <= 500:
                length_hint = f"Keep your answer under {max_length} characters. Be concise (2-4 sentences)."
            else:
                length_hint = f"Keep your answer under {max_length} characters."

        user_prompt = f"Answer this job application question:\n\n\"{label}\"\n\n{length_hint}"

        try:
            answer = self.gpt(self._system_prompt, user_prompt)
            if answer:
                answer = answer.strip().strip('"').strip("'")
                # Enforce character limit
                if max_length and max_length > 0 and len(answer) > max_length:
                    answer = self._truncate_to_limit(answer, max_length)
                self._cache[cache_key] = answer
                return answer
        except Exception as e:
            print(f"    [AI] Error generating answer: {e}")

        return ""

    def select_radio_option(self, label, options):
        """Select the best radio button option for a question."""
        if not options:
            return ""

        label_lower = (label or "").lower()

        # Rule-based selection for common patterns
        rule_pick = self._rule_based_radio(label_lower, options)
        if rule_pick:
            return rule_pick

        # GPT selection
        options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(options)])
        user_prompt = (
            f"Question: \"{label}\"\n\n"
            f"Options:\n{options_text}\n\n"
            f"Reply with ONLY the exact text of the best option. "
            f"Choose the option that best represents the candidate. "
            f"Do not explain your choice."
        )

        try:
            answer = self.gpt(self._system_prompt, user_prompt)
            if answer:
                answer = answer.strip().strip('"').strip("'")
                # Find closest match in options
                match = self._find_closest_option(answer, options)
                return match if match else options[-1]
        except Exception as e:
            print(f"    [AI] Error selecting radio: {e}")

        # Default: pick last option (often the most senior/affirmative)
        return options[-1] if options else ""

    def select_dropdown_option(self, label, options):
        """Select the best dropdown option for a question."""
        if not options:
            return ""

        label_lower = (label or "").lower()

        # Filter out placeholder options
        real_options = [o for o in options if o.lower() not in
                        ("select", "select...", "please select", "choose...",
                         "-- select --", "--select--", "- select -", "")]

        if not real_options:
            return options[0] if options else ""

        # Rule-based for common dropdowns
        rule_pick = self._rule_based_dropdown(label_lower, real_options)
        if rule_pick:
            return rule_pick

        # GPT selection
        options_text = "\n".join([f"  - {opt}" for opt in real_options])
        user_prompt = (
            f"Dropdown question: \"{label}\"\n\n"
            f"Options:\n{options_text}\n\n"
            f"Reply with ONLY the exact text of the best option."
        )

        try:
            answer = self.gpt(self._system_prompt, user_prompt)
            if answer:
                answer = answer.strip().strip('"').strip("'")
                match = self._find_closest_option(answer, real_options)
                return match if match else real_options[-1]
        except Exception as e:
            print(f"    [AI] Error selecting dropdown: {e}")

        return real_options[-1] if real_options else ""

    def select_checkbox_options(self, label, options):
        """Select which checkboxes to check."""
        if not options:
            return []

        # GPT selection for checkboxes
        options_text = "\n".join([f"  - {opt}" for opt in options])
        user_prompt = (
            f"Question: \"{label}\"\n\n"
            f"Checkbox options (select all that apply):\n{options_text}\n\n"
            f"Reply with a JSON array of the exact option texts to select. "
            f"Only select options that truthfully apply to the candidate. "
            f"Example: [\"Option A\", \"Option B\"]"
        )

        try:
            answer = self.gpt(self._system_prompt, user_prompt)
            if answer:
                answer = answer.strip()
                # Parse JSON array
                try:
                    selected = json.loads(answer)
                    if isinstance(selected, list):
                        return [s for s in selected if s in options]
                except json.JSONDecodeError:
                    pass
                # Fallback: check if answer mentions options
                return [opt for opt in options if opt.lower() in answer.lower()]
        except Exception as e:
            print(f"    [AI] Error selecting checkboxes: {e}")

        return []

    def generate_cover_letter(self):
        """Generate a tailored cover letter."""
        title = self.job_context.get("title", "")
        company = self.job_context.get("company", "")

        user_prompt = (
            f"Write a cover letter for the {title} position at {company}. "
            f"Keep it 350-450 words. Use a professional but natural tone. "
            f"Reference specific skills and experience from the profile that match the job requirements. "
            f"Do NOT include date, address header, or 'Dear Hiring Manager' greeting. "
            f"Start directly with engaging content."
        )

        try:
            letter = self.gpt(self._system_prompt, user_prompt)
            return letter.strip() if letter else ""
        except Exception as e:
            print(f"    [AI] Error generating cover letter: {e}")
            return ""

    def answer_batch(self, questions):
        """Answer multiple form questions in a single AI call.

        Reduces API costs and improves answer consistency by providing all
        questions at once so the AI can give coherent, non-repetitive answers.

        Args:
            questions: List of dicts with keys:
                - index: field index (int)
                - label: question/field label (str)
                - type: field type (str)
                - max_length: char limit (int, 0=unlimited)
                - options: list of options for select/radio (optional)

        Returns:
            Dict mapping str(index) → answer string.
            Empty dict if batch call fails.
        """
        if not questions:
            return {}

        # Build a numbered prompt with all questions
        lines = ["Answer each of the following job application form questions.",
                 "Return your answers as a JSON object mapping question numbers to answers.",
                 "For select/radio questions, return the EXACT option text.",
                 "Be concise and professional.\n"]

        for q in questions:
            idx = q["index"]
            label = q["label"]
            field_type = q.get("type", "text")
            max_len = q.get("max_length", 0)
            options = q.get("options", [])

            line = f"Question {idx}: \"{label}\""
            if options:
                line += f" (Choose from: {', '.join(options)})"
            if max_len and max_len > 0:
                line += f" [Max {max_len} characters]"
            if field_type == "textarea":
                line += " [Provide a detailed answer, 2-4 sentences]"
            lines.append(line)

        lines.append("\nRespond ONLY with a JSON object like: "
                     "{\"0\": \"answer\", \"1\": \"answer\", ...}")

        user_prompt = "\n".join(lines)

        try:
            response = self.gpt(self._system_prompt, user_prompt)
            if not response:
                return {}

            # Extract JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if "```" in json_str:
                # Extract from markdown code block
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', json_str, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()

            # Try to find JSON object in response
            brace_start = json_str.find('{')
            brace_end = json_str.rfind('}')
            if brace_start >= 0 and brace_end > brace_start:
                json_str = json_str[brace_start:brace_end + 1]

            answers = json.loads(json_str)

            # Normalize keys to strings
            result = {}
            for k, v in answers.items():
                result[str(k)] = str(v).strip()

            print(f"    [AI] Batch answered {len(result)}/{len(questions)} questions")
            return result

        except (json.JSONDecodeError, Exception) as e:
            print(f"    [AI] Batch answer failed: {e}")
            return {}

    def answer_salary_question(self, label):
        """Answer salary-related questions."""
        sal = self.profile.get_salary_expectations()
        preferred = sal.get("preferred", 0)
        if preferred:
            return str(preferred)
        return ""

    def answer_date_question(self, label):
        """Answer date-related questions (start date, availability)."""
        label_lower = label.lower()
        prefs = self.profile.get_preferences()

        if any(kw in label_lower for kw in START_DATE_KEYWORDS):
            notice = prefs.get("notice_period", "2 weeks")
            if notice:
                return notice
            return "Immediately"

        return ""

    # --- Rule-based shortcuts ---

    def _try_rule_based(self, label):
        """Try to answer with rule-based logic before calling GPT."""
        label_lower = label.lower()
        personal = self.profile.get_personal()
        prefs = self.profile.get_preferences()

        # Personal info fields — match label to profile data
        for field_name, keywords in PERSONAL_KEYWORDS.items():
            if any(kw in label_lower for kw in keywords):
                if field_name == "first_name":
                    return personal.get("first_name", personal.get("full_name", "").split()[0] if personal.get("full_name") else "")
                elif field_name == "last_name":
                    return personal.get("last_name", personal.get("full_name", "").split()[-1] if personal.get("full_name") else "")
                elif field_name == "full_name":
                    return personal.get("full_name", "")
                elif field_name == "email":
                    return personal.get("email", "")
                elif field_name == "phone":
                    return personal.get("phone", "")
                elif field_name == "street":
                    return personal.get("street", "")
                elif field_name == "street2":
                    return personal.get("street2", "")
                elif field_name == "city":
                    return personal.get("city", personal.get("suburb", ""))
                elif field_name == "postcode":
                    return personal.get("postcode", "")
                elif field_name == "state":
                    return personal.get("state", "")
                elif field_name == "country":
                    return personal.get("country", "Australia")
                elif field_name == "linkedin":
                    return personal.get("linkedin_url", "")
                elif field_name == "website":
                    return personal.get("website", "")

        # Salary
        if any(kw in label_lower for kw in SALARY_KEYWORDS):
            return self.answer_salary_question(label)

        # Start date / availability
        if any(kw in label_lower for kw in START_DATE_KEYWORDS):
            return self.answer_date_question(label)

        return None  # No rule matched, use GPT

    def _rule_based_radio(self, label_lower, options):
        """Rule-based radio button selection for common patterns."""
        options_lower = [o.lower() for o in options]

        # Yes/No questions - default to Yes for eligibility/ability questions
        if any(kw in label_lower for kw in YES_NO_KEYWORDS):
            for i, opt in enumerate(options_lower):
                if opt in ("yes", "true"):
                    return options[i]

        # Work rights
        if any(kw in label_lower for kw in WORK_RIGHTS_KEYWORDS):
            wr = self.profile.get_work_rights()
            citizenship = (wr.get("citizenship", "") or "").lower()

            priority = ["australian citizen", "permanent resident", "citizen",
                        "unrestricted", "full work rights", "yes"]
            for prio in priority:
                for i, opt in enumerate(options_lower):
                    if prio in opt:
                        return options[i]

            # If citizen, look for yes
            if "citizen" in citizenship:
                for i, opt in enumerate(options_lower):
                    if "yes" in opt or "citizen" in opt:
                        return options[i]

        # Experience level - pick highest
        if any(kw in label_lower for kw in EXPERIENCE_KEYWORDS):
            # Pick the option with the largest number
            best_idx = len(options) - 1
            best_num = 0
            for i, opt in enumerate(options_lower):
                nums = re.findall(r'\d+', opt)
                if nums:
                    num = max(int(n) for n in nums)
                    if num >= best_num:
                        best_num = num
                        best_idx = i
            return options[best_idx]

        # Relocation
        if "relocat" in label_lower or "willing to move" in label_lower:
            prefs = self.profile.get_preferences()
            if prefs.get("willing_to_relocate"):
                for i, opt in enumerate(options_lower):
                    if "yes" in opt:
                        return options[i]

        return None

    def _rule_based_dropdown(self, label_lower, options):
        """Rule-based dropdown selection for common patterns."""
        options_lower = [o.lower() for o in options]

        # Country dropdown — match from profile
        if "country" in label_lower:
            country = (self.profile.get_personal().get("country", "") or "").lower()
            if country:
                for i, opt in enumerate(options_lower):
                    if country in opt or opt in country:
                        return options[i]
                # Try "australia" specifically
                for i, opt in enumerate(options_lower):
                    if "australia" in opt:
                        return options[i]

        # State/province dropdown — match from profile
        if any(kw in label_lower for kw in ["state", "province", "region", "territory"]):
            state = (self.profile.get_personal().get("state", "") or "").lower()
            if state:
                for i, opt in enumerate(options_lower):
                    if state in opt or opt in state:
                        return options[i]
                # Try full name mapping
                state_map = {"qld": "queensland", "nsw": "new south wales",
                             "vic": "victoria", "sa": "south australia",
                             "wa": "western australia", "tas": "tasmania",
                             "nt": "northern territory", "act": "australian capital territory"}
                full_name = state_map.get(state, "")
                if full_name:
                    for i, opt in enumerate(options_lower):
                        if full_name in opt or opt in full_name:
                            return options[i]

        # Work rights dropdown
        if any(kw in label_lower for kw in WORK_RIGHTS_KEYWORDS):
            priority = ["australian citizen", "citizen", "permanent resident",
                        "unrestricted", "full work rights"]
            for prio in priority:
                for i, opt in enumerate(options_lower):
                    if prio in opt:
                        return options[i]

        # Salary range dropdown
        if any(kw in label_lower for kw in SALARY_KEYWORDS):
            sal = self.profile.get_salary_expectations()
            preferred = sal.get("preferred", 0)
            if preferred:
                # Find the range that contains our salary
                for i, opt in enumerate(options):
                    nums = re.findall(r'[\d,]+', opt.replace(",", ""))
                    if len(nums) >= 2:
                        low, high = int(nums[0]), int(nums[1])
                        if low <= preferred <= high:
                            return options[i]
                # If no range match, pick closest
                closest_idx = len(options) - 1
                closest_diff = float("inf")
                for i, opt in enumerate(options):
                    nums = re.findall(r'[\d,]+', opt.replace(",", ""))
                    if nums:
                        num = int(nums[0])
                        diff = abs(num - preferred)
                        if diff < closest_diff:
                            closest_diff = diff
                            closest_idx = i
                return options[closest_idx]

        # Notice period
        if "notice" in label_lower:
            prefs = self.profile.get_preferences()
            notice = (prefs.get("notice_period", "") or "").lower()
            if notice:
                for i, opt in enumerate(options_lower):
                    if notice in opt or opt in notice:
                        return options[i]

        # Work type
        if "work type" in label_lower or "employment type" in label_lower:
            prefs = self.profile.get_preferences()
            work_type = (prefs.get("work_type", "") or "").lower()
            for i, opt in enumerate(options_lower):
                if work_type in opt or opt in work_type:
                    return options[i]

        return None

    # --- Utility helpers ---

    def _find_closest_option(self, answer, options):
        """Find the option that best matches the GPT answer."""
        answer_lower = answer.lower().strip()

        # Exact match
        for opt in options:
            if opt.lower().strip() == answer_lower:
                return opt

        # Substring match
        for opt in options:
            if answer_lower in opt.lower() or opt.lower() in answer_lower:
                return opt

        # Word overlap scoring
        answer_words = set(answer_lower.split())
        best_score = 0
        best_opt = None
        for opt in options:
            opt_words = set(opt.lower().split())
            overlap = len(answer_words & opt_words)
            if overlap > best_score:
                best_score = overlap
                best_opt = opt

        return best_opt

    def _truncate_to_limit(self, text, max_length):
        """Truncate text to character limit at sentence boundary."""
        if len(text) <= max_length:
            return text

        # Try to cut at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind(".")
        last_excl = truncated.rfind("!")
        last_question = truncated.rfind("?")
        best_cut = max(last_period, last_excl, last_question)

        if best_cut > max_length * 0.5:
            return truncated[:best_cut + 1]

        # Fall back to word boundary
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.7:
            return truncated[:last_space] + "."

        return truncated

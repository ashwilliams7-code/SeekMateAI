"""
Label normalization for form field detection.

Maps common field label variations to canonical keys so rule-based matching
works consistently across different ATS portals (applynow.net.au, Workday,
Greenhouse, SmartRecruiters, etc.).

Usage:
    from longform.label_normalizer import normalize_label, get_canonical_key

    normalize_label("Postcode or Zipcode")   # → "postcode"
    normalize_label("E-mail*")               # → "email"
    normalize_label("City, Town or Suburb")   # → "city"
    get_canonical_key("First name")           # → "first_name"
"""

import re


# ============================================
# SYNONYM DICTIONARY
# Keys are canonical form names. Values are lists of known variations.
# ============================================
LABEL_SYNONYMS = {
    # Personal info
    "first name": [
        "given name", "forename", "first", "fname",
    ],
    "last name": [
        "surname", "family name", "last", "lname",
    ],
    "full name": [
        "your name", "name of applicant", "applicant name",
        "candidate name", "legal name",
    ],
    "email": [
        "e-mail", "email address", "e-mail address", "electronic mail",
        "your email", "contact email", "email*",
    ],
    "phone": [
        "telephone", "phone number", "mobile number", "mobile phone",
        "cell phone", "cell number", "contact number", "tel", "mobile",
        "daytime phone", "evening phone", "home phone", "work phone",
    ],

    # Address fields
    "street": [
        "address line 1", "address line1", "street address",
        "residential address", "home address", "address",
        "street name", "street number",
    ],
    "street cont": [
        "address line 2", "address line2", "unit", "apartment",
        "apt", "suite", "unit/apartment", "apt/suite",
        "street cont.", "street continued",
    ],
    "city": [
        "town", "suburb", "city/town", "city or town",
        "city town or suburb", "city, town or suburb",
        "municipality", "locality",
    ],
    "postcode": [
        "zip code", "zip", "zipcode", "postal code",
        "postcode or zipcode", "postcode or zip code",
        "post code", "zip/postal code",
    ],
    "state": [
        "province", "region", "state/province",
        "state or territory", "state region or province",
        "state, region or province",
    ],
    "country": [
        "nation", "country of residence", "country/region",
    ],

    # Professional links
    "linkedin": [
        "linkedin url", "linkedin profile", "linkedin link",
        "linkedin page",
    ],
    "website": [
        "portfolio", "personal url", "personal site",
        "portfolio url", "personal website",
    ],

    # Employment questions
    "salary": [
        "salary expectation", "expected salary", "desired salary",
        "salary expectations", "remuneration", "compensation",
        "pay expectation", "annual salary", "salary requirement",
        "expected remuneration",
    ],
    "start date": [
        "availability", "available from", "earliest start",
        "when can you start", "commencement date",
        "availability date", "earliest start date",
        "start date availability",
    ],
    "notice period": [
        "notice required", "current notice period",
        "how much notice", "notice",
    ],

    # Documents
    "resume": [
        "cv", "curriculum vitae", "resume/cv", "upload resume",
        "upload cv", "attach resume", "attach cv",
    ],
    "cover letter": [
        "covering letter", "motivation letter",
        "letter of application", "upload cover letter",
    ],
}

# Build reverse lookup: synonym → canonical key
_SYNONYM_LOOKUP = {}
for canonical, synonyms in LABEL_SYNONYMS.items():
    _SYNONYM_LOOKUP[canonical.lower()] = canonical
    for syn in synonyms:
        _SYNONYM_LOOKUP[syn.lower()] = canonical


def _clean_for_matching(text):
    """Prepare text for synonym matching.

    - Lowercase
    - Strip trailing asterisks (required indicators)
    - Remove punctuation except hyphens and slashes
    - Collapse whitespace
    """
    text = text.lower().strip()
    text = text.rstrip("*").strip()
    # Remove common punctuation but keep hyphens, slashes, commas for matching
    text = re.sub(r'[()[\]{}]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_label(raw_label):
    """Normalize a form field label to its canonical form.

    If the label matches a known synonym, returns the canonical key.
    Otherwise returns the cleaned (lowercased, stripped) label unchanged.

    Args:
        raw_label: Raw label text from the form field

    Returns:
        Normalized label string
    """
    if not raw_label:
        return ""

    cleaned = _clean_for_matching(raw_label)

    # 1) Exact match in synonym lookup
    if cleaned in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[cleaned]

    # 2) Try without trailing punctuation (period, colon, etc.)
    stripped = cleaned.rstrip(".:,;").strip()
    if stripped in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[stripped]

    # 3) Try matching by removing commas and "or" connectors
    #    e.g., "City, Town or Suburb" → "city town or suburb" → match
    simplified = re.sub(r'\s*,\s*', ' ', cleaned)
    simplified = re.sub(r'\s+or\s+', ' or ', simplified)
    if simplified in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[simplified]

    # 4) Try each synonym as a substring of the label
    #    (handles labels with extra context like "Your email address *")
    for synonym, canonical in _SYNONYM_LOOKUP.items():
        if len(synonym) >= 4 and synonym in cleaned:
            return canonical

    # No match — return the cleaned label
    return cleaned


def get_canonical_key(label):
    """Return the canonical key for a label, or None if no match.

    Unlike normalize_label(), this returns None instead of the original
    label when no synonym match is found. Useful for explicit key lookups.

    Args:
        label: Label text to look up

    Returns:
        Canonical key string or None
    """
    if not label:
        return None

    normalized = normalize_label(label)

    # Check if the normalized result is actually a canonical key
    if normalized in LABEL_SYNONYMS:
        return normalized

    return None

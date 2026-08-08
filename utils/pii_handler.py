"""
utils/pii_handler.py

PII (Personally Identifiable Information) Handler module.
Implements anonymization of sensitive personal data in resume texts
according to PRD Section 8.
"""

import re
from typing import Dict, List, Any

# Section headers / keywords that should NOT be detected as candidate names
NAME_EXCLUDE_KEYWORDS = {
    # English
    "resume", "curriculum", "vitae", "cv", "experience", "work", "education",
    "skills", "summary", "profile", "contact", "objective", "projects", "certifications",
    "developer", "engineer", "manager", "designer", "specialist", "analyst", "coordinator",
    "administrator", "consultant", "lead", "senior", "junior", "intern", "associate",
    # Thai
    "เรซูเม่", "ประวัติ", "ประวัติการทำงาน", "ประสบการณ์", "การศึกษา", "ทักษะ",
    "ความสามารถ", "สรุป", "ข้อมูลติดต่อ", "วัตถุประสงค์", "โครงการ", "ใบรับรอง",
    "นักพัฒนา", "วิศวกร", "ผู้จัดการ", "นักออกแบบ", "ผู้เชี่ยวชาญ", "นักวิเคราะห์"
}

# Regex for Email
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    re.IGNORECASE
)

# Regex for Phone numbers (Thai & International)
# Matches:
# 08X-XXX-XXXX, 08X XXX XXXX, 08XXXXXXXX, 02-XXX-XXXX
# +66 81 234 5678, +66-81-234-5678, +66812345678, (+66) 81 234 5678
# +1 (555) 123-4567, 555-123-4567, +44 20 7946 0958
PHONE_REGEX = re.compile(
    r'(?:\+\d{1,3}[-.\s]?)?'
    r'(?:\(?\d{2,4}\)?[-.\s]?)'
    r'\d{3,4}[-.\s]?\d{3,4}'
    r'(?:[-.\s]?\d{3,4})?',
    re.IGNORECASE
)


# Labelled Name Patterns: Name: Somchai, ชื่อ - นามสกุล: สมชาย
LABELLED_NAME_REGEX = re.compile(
    r'(?:name|candidate name|full name|ชื่อ|ชื่อ-นามสกุล|ชื่อ\s*-\s*นามสกุล|ผู้สมัคร)\s*[:\-]\s*([^\n,;|]+)',
    re.IGNORECASE
)


def _detect_names(text: str) -> List[str]:
    """
    Detect names using explicit label regex and first non-empty lines heuristics.
    """
    detected_names = []

    # 1. Labelled names (e.g. "Name: Somchai Jaidee", "ชื่อ: สมชาย ใจดี")
    for match in LABELLED_NAME_REGEX.finditer(text):
        name_candidate = match.group(1).strip()
        # Clean up any trailing contact info or bullet points
        name_candidate = re.split(r'[|,\n\t]', name_candidate)[0].strip()
        if name_candidate and len(name_candidate) >= 2:
            if not any(kw in name_candidate.lower() for kw in NAME_EXCLUDE_KEYWORDS):
                detected_names.append(name_candidate)

    # 2. Heuristic: Check first 3 non-empty lines for candidate name
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:3]:
        # Skip if line contains email or phone or common header keywords
        if EMAIL_REGEX.search(line) or PHONE_REGEX.search(line):
            continue

        line_clean = re.sub(
            r'^(นาย|นาง|นางสาว|ดร\.|คุณ|mr\.|mrs\.|ms\.|dr\.)\s*',
            '',
            line,
            flags=re.IGNORECASE
        ).strip()

        # Check if line consists of 2 to 4 words, no digits, no section keywords
        words = line_clean.split()
        if 2 <= len(words) <= 4 and not re.search(r'\d', line_clean):
            # Ensure words are not standard section keywords
            lower_words = [w.lower() for w in words]
            if not any(w in NAME_EXCLUDE_KEYWORDS for w in lower_words):
                # Ensure line doesn't have long sentences or punctuation like colons
                if not re.search(r'[:;,./\\]', line_clean) and len(line_clean) <= 50:
                    if line not in detected_names:
                        detected_names.append(line)
                        break

    return list(dict.fromkeys(detected_names))  # Deduplicate preserving order


def anonymize_pii(text: str) -> Dict[str, Any]:
    """
    Scans input resume text for PII (names, emails, phones) and masks them.

    Returns:
        {
            "anonymized_text": str,
            "detected_pii": {
                "names": list[str],
                "emails": list[str],
                "phones": list[str],
            }
        }
    """
    if not text or not isinstance(text, str):
        return {
            "anonymized_text": text,
            "detected_pii": {"names": [], "emails": [], "phones": []}
        }

    # 1. Detect emails
    emails = list(dict.fromkeys(EMAIL_REGEX.findall(text)))

    # 2. Detect phones
    # Extract phone candidates and filter out false positives (e.g. year ranges like 2020-2024)
    raw_phones = PHONE_REGEX.findall(text)
    phones = []
    for p in raw_phones:
        clean_p = p.strip()
        digits_only = re.sub(r'\D', '', clean_p)
        # Year ranges like 20202024 or 25652567 are 8 digits starting with 20 or 25
        if len(digits_only) == 8 and (digits_only.startswith("20") or digits_only.startswith("25")):
            continue
        # Phone numbers should have at least 9 digits
        if len(digits_only) >= 9:
            phones.append(clean_p)
    phones = list(dict.fromkeys(phones))

    # 3. Detect names
    names = _detect_names(text)

    # 4. Perform replacements in text
    anonymized_text = text

    # Mask emails first
    for email in emails:
        anonymized_text = anonymized_text.replace(email, "[EMAIL]")

    # Mask phones
    for phone in phones:
        anonymized_text = anonymized_text.replace(phone, "[PHONE]")

    # Mask names
    for name in names:
        anonymized_text = anonymized_text.replace(name, "[NAME]")

    return {
        "anonymized_text": anonymized_text,
        "detected_pii": {
            "names": names,
            "emails": emails,
            "phones": phones,
        }
    }

"""
tests/test_pii_handler.py

Unit tests for utils/pii_handler.py.
Validates PII detection and anonymization for Thai, English, and mixed resumes.
"""

import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pii_handler import anonymize_pii


def test_pii_english_resume():
    english_resume = """John Doe
Software Engineer
Email: john.doe@example.com | Phone: +1 (555) 123-4567 | Location: New York

SUMMARY
Experienced software engineer specializing in Python and Cloud Architecture.

EXPERIENCE
Software Engineer at Tech Corp (2020-2024)
- Developed REST APIs using FastAPI and PostgreSQL.
"""
    result = anonymize_pii(english_resume)

    assert "john.doe@example.com" not in result["anonymized_text"]
    assert "+1 (555) 123-4567" not in result["anonymized_text"]
    assert "John Doe" not in result["anonymized_text"]

    assert "[EMAIL]" in result["anonymized_text"]
    assert "[PHONE]" in result["anonymized_text"]
    assert "[NAME]" in result["anonymized_text"]

    assert result["detected_pii"]["emails"] == ["john.doe@example.com"]
    assert result["detected_pii"]["phones"] == ["+1 (555) 123-4567"]
    assert "John Doe" in result["detected_pii"]["names"]

    # Ensure year range 2020-2024 is preserved
    assert "2020-2024" in result["anonymized_text"]


def test_pii_thai_resume():
    thai_resume = """สมชาย ใจดี
นักพัฒนาซอฟต์แวร์

ข้อมูลติดต่อ:
- อีเมล: somchai.j@email.co.th
- เบอร์โทร: 081-234-5678
- ที่อยู่: กรุงเทพมหานคร

ประสบการณ์ทำงาน:
2565-2567 Backend Developer ที่บริษัท เทคไทย จำกัด
- พัฒนาระบบ Microservices ด้วย Python และ Docker
"""
    result = anonymize_pii(thai_resume)

    assert "somchai.j@email.co.th" not in result["anonymized_text"]
    assert "081-234-5678" not in result["anonymized_text"]
    assert "สมชาย ใจดี" not in result["anonymized_text"]

    assert "[EMAIL]" in result["anonymized_text"]
    assert "[PHONE]" in result["anonymized_text"]
    assert "[NAME]" in result["anonymized_text"]

    assert result["detected_pii"]["emails"] == ["somchai.j@email.co.th"]
    assert result["detected_pii"]["phones"] == ["081-234-5678"]
    assert "สมชาย ใจดี" in result["detected_pii"]["names"]

    # Ensure Thai year range 2565-2567 is preserved
    assert "2565-2567" in result["anonymized_text"]


def test_pii_labelled_mixed_resume():
    labelled_resume = """CURRICULUM VITAE

Candidate Name: Somying Rakdee
Email: somying.r@test.com
Phone: 02-345-6789, +66 89 999 8888

Skills: Python, SQL, Financial Analysis
"""
    result = anonymize_pii(labelled_resume)

    assert "somying.r@test.com" not in result["anonymized_text"]
    assert "02-345-6789" not in result["anonymized_text"]
    assert "+66 89 999 8888" not in result["anonymized_text"]
    assert "Somying Rakdee" not in result["anonymized_text"]

    assert result["detected_pii"]["emails"] == ["somying.r@test.com"]
    assert "02-345-6789" in result["detected_pii"]["phones"]
    assert "+66 89 999 8888" in result["detected_pii"]["phones"]
    assert "Somying Rakdee" in result["detected_pii"]["names"]


def test_pii_empty_or_no_pii():
    empty_res = anonymize_pii("")
    assert empty_res["anonymized_text"] == ""
    assert empty_res["detected_pii"]["names"] == []

    clean_text = "Experienced Senior Developer with 5 years experience in Python and FastAPI."
    result = anonymize_pii(clean_text)
    assert result["anonymized_text"] == clean_text
    assert result["detected_pii"]["emails"] == []
    assert result["detected_pii"]["phones"] == []

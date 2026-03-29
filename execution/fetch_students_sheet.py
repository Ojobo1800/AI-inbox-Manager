"""
Fetch student data from the Colaberry students Google Sheet.

Reads the public Google Sheet as CSV and provides lookup by student name
or email. Used to resolve which student an interview email is for and
find their assigned assistant contact details.

Design principles:
- Fetches sheet as CSV (no API keys required — sheet is public)
- Caches results to avoid repeated HTTP requests per run
- Deterministic matching logic (no AI)
"""

import logging
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Load students from config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.students import STUDENTS, CC_EMAILS


def get_all_students(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Return all students from the config file."""
    return STUDENTS


def _normalize_name(name: str) -> str:
    """Lowercase, strip, remove extra spaces."""
    return re.sub(r"\s+", " ", name.lower().strip())


def find_student_by_name(name_hint: str) -> Optional[Dict[str, Any]]:
    """
    Find a student by approximate name match.

    Tries exact match first, then partial match (first name or last name).

    Args:
        name_hint: Name extracted from email body

    Returns:
        Matching student dict or None
    """
    if not name_hint:
        return None

    students = get_all_students()
    normalized_hint = _normalize_name(name_hint)

    # 1. Exact full name match
    for s in students:
        if _normalize_name(s["name"]) == normalized_hint:
            logger.info(f"Exact name match: {s['name']}")
            return s

    # 2. Partial match — hint is contained in student name or vice versa
    hint_parts = set(normalized_hint.split())
    for s in students:
        student_parts = set(_normalize_name(s["name"]).split())
        # If all hint words appear in the student name
        if hint_parts and hint_parts.issubset(student_parts):
            logger.info(f"Partial name match: {s['name']} (hint: {name_hint})")
            return s

    # 3. First name only match
    hint_first = normalized_hint.split()[0] if normalized_hint else ""
    if hint_first:
        for s in students:
            student_first = _normalize_name(s["name"]).split()[0]
            if student_first == hint_first:
                logger.info(f"First-name match: {s['name']} (hint: {name_hint})")
                return s

    logger.warning(f"No student match found for name hint: '{name_hint}'")
    return None


def find_student_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Find a student by their personal email address.

    Args:
        email: Email address to look up

    Returns:
        Matching student dict or None
    """
    if not email:
        return None

    students = get_all_students()
    email_lower = email.lower().strip()

    for s in students:
        if s["personal_email"].lower().strip() == email_lower:
            logger.info(f"Email match: {s['name']} ({email})")
            return s

    logger.warning(f"No student found for email: {email}")
    return None

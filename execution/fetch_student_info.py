"""
Student information retrieval execution script.

Orchestrates student data retrieval by combining student resolution
(from email headers) with config/students.py lookup. Returns structured
student information needed for notification drafting.

Design principles:
- Orchestrates resolve_student.py and config/students.py
- Returns a standardized student info dictionary
- Handles missing data gracefully
- No AI — purely deterministic
"""

import logging
from typing import Dict, Any, Optional

from execution.resolve_student import resolve_student

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Standard field mapping from spreadsheet keys to our standard keys.
# The spreadsheet may use different names; this maps common variants.
FIELD_ALIASES = {
    "full_name": ["full_name", "name", "student_name", "full name"],
    "personal_email": [
        "personal_email",
        "personal email",
        "email",
        "personal_email_address",
    ],
    "assigned_gmail": [
        "assigned_gmail",
        "gmail",
        "assigned_email",
        "colaberry_email",
        "assigned gmail",
    ],
    "phone_number": [
        "phone_number",
        "phone",
        "mobile",
        "cell",
        "phone number",
        "contact_number",
    ],
}


def normalize_student_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw spreadsheet data into standard student fields.

    Handles different column naming conventions by checking aliases.

    Args:
        raw_data: Raw key-value data from student spreadsheet

    Returns:
        Standardized student info dictionary
    """
    result = {}

    for standard_key, aliases in FIELD_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in raw_data and raw_data[alias]:
                value = raw_data[alias]
                break
        result[standard_key] = value

    # Copy any additional fields from the spreadsheet that aren't in our aliases
    known_aliases = set()
    for aliases in FIELD_ALIASES.values():
        known_aliases.update(aliases)

    for key, value in raw_data.items():
        if key not in known_aliases and not key.startswith("_"):
            result[key] = value

    # Copy metadata fields
    for key in ["_folder_id", "_folder_name", "_username", "_spreadsheet_id"]:
        if key in raw_data:
            result[key] = raw_data[key]

    return result


def fetch_student_info(
    email_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Fetch student information for an interview email.

    Steps:
    1. Resolve which student the email is about (via headers)
    2. Return standardized student info (contact details come from config/students.py
       in the live pipeline via notify_student.py)

    Args:
        email_data: Dictionary with email data including:
            - headers: Dict of email headers
            - to_addresses: List of To/CC addresses
            - body_content: Email body text
            - sender_email: Sender's email

    Returns:
        Dictionary with:
            - student_gmail: str | None
            - student_username: str | None
            - resolution: dict (from resolve_student)
            - full_name: str | None
            - personal_email: str | None (WHERE TO SEND NOTIFICATIONS)
            - phone_number: str | None
            - status: "resolved" | "partial" | "not_found"
            - error: str | None
    """
    result = {
        "student_gmail": None,
        "student_username": None,
        "resolution": None,
        "full_name": None,
        "personal_email": None,
        "assigned_gmail": None,
        "phone_number": None,
        "status": "not_found",
        "error": None,
    }

    # Step 1: Resolve student from email
    try:
        resolution = resolve_student(email_data)
        result["resolution"] = resolution
        result["student_gmail"] = resolution.get("student_gmail")
        result["student_username"] = resolution.get("student_username")
    except Exception as e:
        logger.error(f"Student resolution failed: {e}")
        result["error"] = f"Resolution failed: {str(e)}"
        return result

    # If we couldn't identify the student, return early
    if not result["student_username"]:
        result["error"] = "Could not identify student from email"
        if resolution.get("student_name_hint"):
            result["full_name"] = resolution["student_name_hint"]
            result["status"] = "partial"
        return result

    # Student gmail resolved — contact details are looked up at runtime
    # via notify_student.py → config/students.py in the live pipeline.
    result["assigned_gmail"] = result["student_gmail"]
    result["status"] = "partial"
    logger.info(f"Student username resolved: {result['student_username']}")

    return result

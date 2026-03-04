"""
Student information retrieval execution script.

Orchestrates student data retrieval by combining student resolution
(from email headers) with Google Drive data lookup. Returns structured
student information needed for notification drafting.

Design principles:
- Orchestrates resolve_student.py and google_drive_client.py
- Returns a standardized student info dictionary
- Handles missing data gracefully
- No AI — purely deterministic
"""

import logging
from typing import Dict, Any, Optional

from execution.resolve_student import resolve_student
from execution.google_drive_client import GoogleDriveClient

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
    drive_client: Optional[GoogleDriveClient] = None,
) -> Dict[str, Any]:
    """
    Fetch student information for an interview email.

    Steps:
    1. Resolve which student the email is about (via headers)
    2. Look up student data from Google Drive
    3. Return standardized student info

    Args:
        email_data: Dictionary with email data including:
            - headers: Dict of email headers
            - to_addresses: List of To/CC addresses
            - body_content: Email body text
            - sender_email: Sender's email
        drive_client: Optional pre-configured GoogleDriveClient.
            A new one is created if not provided.

    Returns:
        Dictionary with:
            - student_gmail: str | None
            - student_username: str | None
            - resolution: dict (from resolve_student)
            - full_name: str | None
            - personal_email: str | None (WHERE TO SEND NOTIFICATIONS)
            - phone_number: str | None
            - drive_data: dict | None (full Drive spreadsheet data)
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
        "drive_data": None,
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
        # If we found a name hint, include it
        if resolution.get("student_name_hint"):
            result["full_name"] = resolution["student_name_hint"]
            result["status"] = "partial"
        return result

    # Step 2: Look up student data from Google Drive
    try:
        if drive_client is None:
            drive_client = GoogleDriveClient()

        raw_data = drive_client.get_student_info(result["student_username"])

        if raw_data:
            normalized = normalize_student_data(raw_data)
            result["drive_data"] = normalized
            result["full_name"] = normalized.get("full_name")
            result["personal_email"] = normalized.get("personal_email")
            result["assigned_gmail"] = (
                normalized.get("assigned_gmail") or result["student_gmail"]
            )
            result["phone_number"] = normalized.get("phone_number")
            result["status"] = "resolved"
            logger.info(
                f"Student info resolved: {result['full_name']} "
                f"(personal email: {result['personal_email']})"
            )
        else:
            result["assigned_gmail"] = result["student_gmail"]
            result["status"] = "partial"
            result["error"] = (
                f"Student folder/spreadsheet not found in Drive "
                f"for username: {result['student_username']}"
            )
            logger.warning(result["error"])

    except Exception as e:
        logger.error(f"Google Drive lookup failed: {e}")
        result["assigned_gmail"] = result["student_gmail"]
        result["status"] = "partial"
        result["error"] = f"Drive lookup failed: {str(e)}"

    return result

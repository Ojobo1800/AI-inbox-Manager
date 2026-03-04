"""
Google Sheets email classification logger + tracker.

Appends every classified email as a row in a Google Spreadsheet via the
Google Sheets API v4 (service-account credentials — no user sign-in required).

Integration is OPTIONAL and non-blocking:
  - If the required env vars / key file are absent, every call is a no-op.
  - If the API call fails, an error is logged but the main pipeline continues.

─────────────────────────────────────────────────────────────────────────────
COLUMN LAYOUT  (Row 1 = header)
─────────────────────────────────────────────────────────────────────────────
  AUTO-POPULATED (written by InboxGenius on each run)
  A  Title (Email UID)
  B  Email UID
  C  Subject
  D  From Address
  E  Received Date
  F  Processed Date
  G  Category
  H  Confidence Score
  I  Company Name
  J  Position Title
  K  Contact Name
  L  Contact Email
  M  Interview Date
  N  Interview Time
  O  Interview Timezone
  P  Interview Format
  Q  Action Required
  R  Current Folder
  S  Requires Manual Review
  T  Is Edge Case
  U  Edge Case Type
  V  GPT Model

  TRACKER COLUMNS (filled in manually by your team)
  W  Status           — New / In Progress / Responded / Scheduled / Completed / Cancelled
  X  Priority         — High / Medium / Low
  Y  Notes            — free-text
  Z  Follow-up Date   — date
  AA Assigned To      — team member name
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Column definitions ────────────────────────────────────────────────────────
# Auto-populated columns (A–V)
_AUTO_HEADERS: List[str] = [
    "Title",
    "Email UID",
    "Subject",
    "From Address",
    "Received Date",
    "Processed Date",
    "Category",
    "Confidence Score",
    "Company Name",
    "Position Title",
    "Contact Name",
    "Contact Email",
    "Interview Date",
    "Interview Time",
    "Interview Timezone",
    "Interview Format",
    "Action Required",
    "Current Folder",
    "Requires Manual Review",
    "Is Edge Case",
    "Edge Case Type",
    "GPT Model",
]

# Tracker columns (W–AA) — written once as empty strings so team can fill them
_TRACKER_HEADERS: List[str] = [
    "Status",        # W — New / In Progress / Responded / Scheduled / Completed / Cancelled
    "Priority",      # X — High / Medium / Low
    "Notes",         # Y — free-text
    "Follow-up Date",# Z — date
    "Assigned To",   # AA — team member name
]

# Full header row
SHEET_HEADERS: List[str] = _AUTO_HEADERS + _TRACKER_HEADERS

# Sheet range covering all columns (A through AA = 27 columns)
_SHEET_RANGE = "Sheet1!A:AA"
_HEADER_RANGE = "Sheet1!A1:AA1"

# ── Filtering — categories and folders to exclude from the sheet ─────────────
# Job alerts and deleted/spam emails are not useful for tracking.
_SKIP_CATEGORIES: set = {
    # job alert variants (space and underscore forms)
    "job alert",
    "job alerts",
    "job_alert",
    "job_alerts",
    # spam / deleted
    "spam",
    "deleted",
}

_SKIP_FOLDERS: set = {
    "job alerts",
    "job alert",
    "deleted",
    "deleted items",
    "trash",
    "[gmail]/trash",
    "spam",
    "[gmail]/spam",
    "junk",
}


def _should_skip(classification: dict, current_folder: str) -> bool:
    """Return True if this email should be excluded from the sheet."""
    category = (classification.get("category") or "").lower().strip()
    folder = (current_folder or "").lower().strip()
    return category in _SKIP_CATEGORIES or folder in _SKIP_FOLDERS


# Module-level cached Sheets service
_sheets_service: Optional[Any] = None


def is_configured() -> bool:
    """Return True if both required env vars are set and the key file exists."""
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "").strip()
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not key_path or not sheet_id:
        return False
    if not os.path.isabs(key_path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(root, key_path)
    return os.path.isfile(key_path)


def _get_service() -> Optional[Any]:
    """Build (and cache) the Google Sheets API service object."""
    global _sheets_service
    if _sheets_service is not None:
        return _sheets_service

    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "").strip()
    if not os.path.isabs(key_path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(root, key_path)

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        _sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        logger.debug("Google Sheets service initialised")
        return _sheets_service
    except Exception as exc:
        logger.error("Failed to build Google Sheets service: %s", exc)
        return None


def _build_row(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    current_folder: str,
) -> List[str]:
    """Map email data + classification to a flat list of cell values (27 columns)."""
    extracted = classification.get("extracted_data") or {}
    edge_case = classification.get("edge_case") or {}

    subject = (email_data.get("subject") or "No Subject")[:255]
    email_uid = str(email_data.get("email_id", ""))

    raw_date = email_data.get("date") or email_data.get("received_date")
    if isinstance(raw_date, datetime):
        received_str = raw_date.isoformat()
    elif isinstance(raw_date, str) and raw_date:
        received_str = raw_date[:50]
    else:
        received_str = ""

    processed_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    confidence = classification.get("confidence")
    confidence_str = str(round(float(confidence), 4)) if confidence is not None else ""

    # Auto-populated columns A–V
    auto_cols = [
        email_uid or subject[:255],                               # A Title
        email_uid,                                                 # B Email UID
        subject,                                                   # C Subject
        (email_data.get("from") or "")[:255],                     # D From Address
        received_str,                                              # E Received Date
        processed_str,                                             # F Processed Date
        (classification.get("category") or "")[:255],             # G Category
        confidence_str,                                            # H Confidence Score
        (extracted.get("company_name") or "")[:255],              # I Company Name
        (extracted.get("position_title") or "")[:255],            # J Position Title
        (extracted.get("contact_name") or "")[:255],              # K Contact Name
        (extracted.get("contact_email") or "")[:255],             # L Contact Email
        (extracted.get("interview_date") or "")[:50],             # M Interview Date
        (extracted.get("interview_time") or "")[:50],             # N Interview Time
        (extracted.get("interview_timezone") or "")[:50],         # O Interview Timezone
        (extracted.get("interview_type") or "")[:100],            # P Interview Format
        (extracted.get("action_required") or "")[:500],           # Q Action Required
        (current_folder or "")[:255],                             # R Current Folder
        "Yes" if classification.get("requires_manual_review") else "No",  # S Requires Review
        "Yes" if edge_case.get("is_edge_case") else "No",         # T Is Edge Case
        (edge_case.get("type") or "")[:100],                      # U Edge Case Type
        "gpt-4o",                                                  # V GPT Model
    ]

    # Tracker columns W–AA (empty — filled manually by team)
    # Status defaults to "New" so team knows it needs attention
    tracker_cols = [
        "New",  # W Status
        "",     # X Priority
        "",     # Y Notes
        "",     # Z Follow-up Date
        "",     # AA Assigned To
    ]

    return auto_cols + tracker_cols


def _ensure_header_row(service: Any, sheet_id: str) -> None:
    """Write/update the header row if missing or incomplete."""
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=_HEADER_RANGE)
            .execute()
        )
        existing = result.get("values", [])
        # If header already has all columns, skip
        if existing and len(existing[0]) >= len(SHEET_HEADERS):
            return

        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [SHEET_HEADERS]},
        ).execute()
        logger.info("Google Sheets: header row written (%d columns)", len(SHEET_HEADERS))
    except Exception as exc:
        logger.warning("Could not write header row: %s", exc)


def log_email_to_sheets(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    current_folder: str = "INBOX",
) -> bool:
    """
    Append a single classified email as a row in the Google Sheet.

    Fully non-blocking — all exceptions are caught so the main pipeline
    is never interrupted.

    Returns:
        True if the row was appended, False otherwise.
    """
    if not is_configured():
        return False

    if _should_skip(classification, current_folder):
        logger.debug(
            "Google Sheets: skipping %s email (category=%s, folder=%s)",
            classification.get("category", "unknown"),
            classification.get("category", ""),
            current_folder,
        )
        return False

    try:
        service = _get_service()
        if service is None:
            return False

        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        _ensure_header_row(service, sheet_id)

        row = _build_row(email_data, classification, current_folder)

        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=_SHEET_RANGE,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        logger.debug(
            "Google Sheets: appended row for email '%s'",
            (email_data.get("subject") or "")[:50],
        )
        return True

    except Exception as exc:
        logger.warning("Google Sheets logging failed (non-fatal): %s", exc)
        return False


def log_batch_to_sheets(
    classified_emails: list,
    folder_map: Dict[str, str],
) -> Dict[str, int]:
    """
    Append an entire batch of classified emails to the Google Sheet in one
    API call (much more efficient than one call per email).

    Args:
        classified_emails: List of (idx, email_data, classification, usage) tuples
        folder_map:        Dict mapping email_id -> destination folder

    Returns:
        Dict with "logged" and "failed" counts.
    """
    if not is_configured():
        return {"logged": 0, "failed": 0, "skipped_not_configured": True}

    try:
        service = _get_service()
        if service is None:
            return {"logged": 0, "failed": 0}

        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        _ensure_header_row(service, sheet_id)

        rows: List[List[str]] = []
        skipped = 0
        filtered = 0

        for item in classified_emails:
            if len(item) < 3:
                skipped += 1
                continue
            _, email_data, classification = item[0], item[1], item[2]
            if classification is None:
                skipped += 1
                continue

            email_id = str(email_data.get("email_id", ""))
            folder = folder_map.get(email_id, "INBOX")

            if _should_skip(classification, folder):
                filtered += 1
                continue

            rows.append(_build_row(email_data, classification, folder))

        if not rows:
            logger.info(
                "Google Sheets: no rows to append (skipped=%d, filtered=%d)",
                skipped, filtered,
            )
            return {"logged": 0, "failed": 0, "filtered": filtered}

        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=_SHEET_RANGE,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

        logger.info(
            "Google Sheets: %d rows appended (%d filtered out, %d skipped)",
            len(rows), filtered, skipped,
        )
        return {"logged": len(rows), "failed": 0, "filtered": filtered}

    except Exception as exc:
        logger.warning("Google Sheets batch logging failed (non-fatal): %s", exc)
        return {"logged": 0, "failed": len(classified_emails)}

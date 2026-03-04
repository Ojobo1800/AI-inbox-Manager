"""
SharePoint email classification logger.

Logs every classified email to a SharePoint List via Microsoft Graph API
(OAuth2 client-credentials flow — no user sign-in required).

Integration is OPTIONAL and non-blocking:
  - If the required .env variables are absent, every call is a no-op.
  - If the API call fails, an error is logged but the main pipeline continues.

─────────────────────────────────────────────────────────────────────────────
SETUP (one-time, done by admin)
─────────────────────────────────────────────────────────────────────────────
1. Azure Portal → App Registrations → New Registration
      Name: "InboxGenius-SharePoint"
      Supported account types: Accounts in this org only

2. Certificates & Secrets → New client secret → copy value

3. API Permissions → Add → Microsoft Graph → Application permissions:
      Sites.ReadWrite.All  (or Sites.Selected for tighter scope)
   → Grant admin consent

4. Get the Site ID:
      GET https://graph.microsoft.com/v1.0/sites/{tenant}.sharepoint.com:/sites/{site-name}
      Copy the "id" field.

5. Create a SharePoint List (see column schema below) and get the List ID:
      GET https://graph.microsoft.com/v1.0/sites/{site_id}/lists
      Find your list and copy the "id" field.

6. Add to your root .env file:
      SHAREPOINT_TENANT_ID=<your-tenant-id>
      SHAREPOINT_CLIENT_ID=<app-client-id>
      SHAREPOINT_CLIENT_SECRET=<client-secret>
      SHAREPOINT_SITE_ID=<site-id>
      SHAREPOINT_LIST_ID=<list-id>

─────────────────────────────────────────────────────────────────────────────
SHAREPOINT LIST COLUMN SCHEMA
─────────────────────────────────────────────────────────────────────────────
Create these columns in your SharePoint list (internal name → display name → type):

  Title              → Title                    → Single line of text (built-in)
  EmailUID           → Email UID                → Single line of text
  Subject            → Subject                  → Single line of text
  FromAddress        → From Address             → Single line of text
  ReceivedDate       → Received Date            → Date and Time
  ProcessedDate      → Processed Date           → Date and Time
  Category           → Category                 → Single line of text
  Confidence         → Confidence Score         → Number (0–1)
  CompanyName        → Company Name             → Single line of text
  PositionTitle      → Position Title           → Single line of text
  ContactName        → Contact Name             → Single line of text
  ContactEmail       → Contact Email            → Single line of text
  InterviewDate      → Interview Date           → Single line of text (ISO date)
  InterviewTime      → Interview Time           → Single line of text
  InterviewTimezone  → Interview Timezone       → Single line of text
  InterviewFormat    → Interview Format         → Single line of text
  ActionRequired     → Action Required          → Multiple lines of text
  CurrentFolder      → Current Folder           → Single line of text
  RequiresReview     → Requires Manual Review   → Yes/No
  IsEdgeCase         → Is Edge Case             → Yes/No
  EdgeCaseType       → Edge Case Type           → Single line of text
  GptModel           → GPT Model                → Single line of text
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Module-level token cache (avoids fetching a new token on every call) ─────
_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}

# Graph API base URL
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def is_configured() -> bool:
    """
    Return True if all required SharePoint env vars are present.

    Call this before any logging attempt — if False, skip silently.
    """
    required = [
        "SHAREPOINT_TENANT_ID",
        "SHAREPOINT_CLIENT_ID",
        "SHAREPOINT_CLIENT_SECRET",
        "SHAREPOINT_SITE_ID",
        "SHAREPOINT_LIST_ID",
    ]
    return all(os.getenv(k) for k in required)


def _get_access_token() -> Optional[str]:
    """
    Return a valid Graph API access token, fetching a new one if expired.

    Uses client-credentials OAuth2 flow.  Tokens are valid for ~3600 seconds
    and are cached at module level so multiple emails in the same run reuse
    the same token.

    Returns:
        Access token string, or None on failure.
    """
    now = time.monotonic()
    # Refresh 60 seconds before actual expiry
    if _token_cache["access_token"] and _token_cache["expires_at"] - now > 60:
        return _token_cache["access_token"]

    tenant_id = os.getenv("SHAREPOINT_TENANT_ID", "")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID", "")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET", "")

    if not all([tenant_id, client_id, client_secret]):
        logger.warning("SharePoint credentials not set — cannot obtain token")
        return None

    try:
        import requests  # already in requirements.txt

        url = _TOKEN_URL_TEMPLATE.format(tenant_id=tenant_id)
        resp = requests.post(
            url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        _token_cache["access_token"] = access_token
        _token_cache["expires_at"] = now + expires_in

        logger.debug("SharePoint access token obtained (expires in %ds)", expires_in)
        return access_token

    except Exception as exc:
        logger.error("Failed to obtain SharePoint access token: %s", exc)
        return None


def _build_fields(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    current_folder: str,
) -> Dict[str, Any]:
    """
    Map email data + classification result to SharePoint list field values.

    Column internal names must match exactly what was created in the list.
    Null values from classification are written as empty strings so the cell
    exists in SharePoint (makes filtering/sorting cleaner).

    Args:
        email_data:      Raw email dict from IMAP fetch
        classification:  Classification result from classify_email()
        current_folder:  Destination folder ("INBOX", "Job Alerts", etc.)

    Returns:
        Dict ready to POST as {"fields": ...} to Graph API
    """
    extracted = classification.get("extracted_data") or {}
    edge_case = classification.get("edge_case") or {}

    subject = (email_data.get("subject") or "No Subject")[:255]
    email_uid = str(email_data.get("email_id", ""))

    # Parse received date to ISO format for SharePoint DateTime column
    raw_date = email_data.get("date") or email_data.get("received_date")
    if isinstance(raw_date, datetime):
        received_iso = raw_date.isoformat()
    elif isinstance(raw_date, str) and raw_date:
        received_iso = raw_date[:50]
    else:
        received_iso = None

    processed_iso = datetime.utcnow().isoformat() + "Z"

    confidence = classification.get("confidence")
    confidence_val = round(float(confidence), 4) if confidence is not None else None

    return {
        # SharePoint requires Title (the built-in column) — use email UID
        "Title": email_uid or subject[:255],
        "EmailUID": email_uid[:255] if email_uid else "",
        "Subject": subject,
        "FromAddress": (email_data.get("from") or "")[:255],
        "ReceivedDate": received_iso,
        "ProcessedDate": processed_iso,
        "Category": (classification.get("category") or "")[:255],
        "Confidence": confidence_val,
        "CompanyName": (extracted.get("company_name") or "")[:255],
        "PositionTitle": (extracted.get("position_title") or "")[:255],
        "ContactName": (extracted.get("contact_name") or "")[:255],
        "ContactEmail": (extracted.get("contact_email") or "")[:255],
        "InterviewDate": (extracted.get("interview_date") or "")[:50],
        "InterviewTime": (extracted.get("interview_time") or "")[:50],
        "InterviewTimezone": (extracted.get("interview_timezone") or "")[:50],
        "InterviewFormat": (extracted.get("interview_type") or "")[:100],
        "ActionRequired": (extracted.get("action_required") or "")[:500],
        "CurrentFolder": (current_folder or "")[:255],
        "RequiresReview": bool(classification.get("requires_manual_review", False)),
        "IsEdgeCase": bool(edge_case.get("is_edge_case", False)),
        "EdgeCaseType": (edge_case.get("type") or "")[:100],
        "GptModel": "gpt-4o",
    }


def log_email_to_sharepoint(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    current_folder: str = "INBOX",
) -> bool:
    """
    Log a single classified email to the SharePoint list.

    This function is fully non-blocking — all exceptions are caught and logged
    so the main pipeline is never interrupted by a SharePoint failure.

    Args:
        email_data:      Raw email dict from IMAP fetch
        classification:  Classification result from classify_email()
        current_folder:  Destination folder label

    Returns:
        True if the item was successfully created, False otherwise.
    """
    if not is_configured():
        # Silent no-op — env vars not set, SharePoint integration disabled
        return False

    try:
        import requests

        token = _get_access_token()
        if not token:
            return False

        site_id = os.getenv("SHAREPOINT_SITE_ID", "")
        list_id = os.getenv("SHAREPOINT_LIST_ID", "")
        url = f"{_GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items"

        fields = _build_fields(email_data, classification, current_folder)

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"fields": fields},
            timeout=20,
        )

        if resp.status_code in (200, 201):
            item_id = resp.json().get("id", "?")
            logger.debug(
                "SharePoint: logged email '%s' as item id=%s",
                fields.get("Subject", "")[:50],
                item_id,
            )
            return True
        else:
            logger.warning(
                "SharePoint: unexpected status %d for email '%s': %s",
                resp.status_code,
                fields.get("Subject", "")[:50],
                resp.text[:200],
            )
            return False

    except Exception as exc:
        logger.warning("SharePoint logging failed (non-fatal): %s", exc)
        return False


def log_batch_to_sharepoint(
    classified_emails: list,
    folder_map: Dict[str, str],
) -> Dict[str, int]:
    """
    Log an entire batch of classified emails to SharePoint.

    Convenience wrapper used after the full classification run, rather than
    calling log_email_to_sharepoint() inline for each email.

    Args:
        classified_emails: List of (idx, email_data, classification, usage) tuples
                           (same format as process_inbox_auto.py's classified list)
        folder_map:        Dict mapping email_id → destination folder

    Returns:
        Dict with "logged" and "failed" counts
    """
    if not is_configured():
        return {"logged": 0, "failed": 0, "skipped_not_configured": True}

    logged = 0
    failed = 0

    for item in classified_emails:
        # Support both 3-tuple (old) and 4-tuple (new with usage)
        if len(item) >= 3:
            _, email_data, classification = item[0], item[1], item[2]
        else:
            continue

        if classification is None:
            continue  # classification failed — nothing to log

        email_id = str(email_data.get("email_id", ""))
        folder = folder_map.get(email_id, "INBOX")

        if log_email_to_sharepoint(email_data, classification, folder):
            logged += 1
        else:
            failed += 1

    logger.info("SharePoint batch: %d logged, %d failed", logged, failed)
    return {"logged": logged, "failed": failed}

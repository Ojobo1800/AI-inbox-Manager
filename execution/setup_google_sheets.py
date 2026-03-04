"""
Google Sheets Setup Helper -- run once to create the audit spreadsheet.

This script:
  1. Validates your service-account credentials
  2. Creates a new Google Spreadsheet named "InboxGenius Email Audit"
     (or uses an existing one if GOOGLE_SHEET_ID is already in .env)
  3. Writes the 22-column header row
  4. Applies basic formatting (bold header, freeze row 1)
  5. Prints the Spreadsheet ID and public URL to add to your .env

Usage:
  cd <project-root>
  python execution/setup_google_sheets.py

Required env vars (add to root .env before running):
  GOOGLE_SERVICE_ACCOUNT_KEY_PATH=config/service-account-key.json
  (Get the key file from Google Cloud Console -> IAM -> Service Accounts -> Keys)

Optional:
  GOOGLE_SHEET_ID=   -- if already created, skip creation and just write headers
"""

import os
import sys

from dotenv import load_dotenv

# -- Load root .env ----------------------------------------------------------
_script_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_script_dir)
load_dotenv(os.path.join(_root_dir, ".env"))

# Import header list from the logger module
sys.path.insert(0, _script_dir)
from log_to_google_sheets import SHEET_HEADERS  # noqa: E402


def _resolve_key_path() -> str:
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "").strip()
    if not key_path:
        return ""
    if not os.path.isabs(key_path):
        key_path = os.path.join(_root_dir, key_path)
    return key_path


def _get_credentials(key_path: str):
    try:
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            key_path,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
    except Exception as exc:
        print(f"\nERROR: Failed to load service account credentials: {exc}")
        sys.exit(1)


def _build_services(creds):
    try:
        from googleapiclient.discovery import build

        sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        return sheets, drive
    except Exception as exc:
        print(f"\nERROR: Failed to build API services: {exc}")
        print("   Make sure google-api-python-client is installed:")
        print("   pip install google-api-python-client google-auth")
        sys.exit(1)


def _create_spreadsheet(sheets_svc) -> str:
    """Create a new spreadsheet and return its ID."""
    body = {
        "properties": {"title": "InboxGenius Email Audit"},
        "sheets": [{"properties": {"title": "Sheet1"}}],
    }
    result = sheets_svc.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sheet_id = result["spreadsheetId"]
    print("  [OK] Spreadsheet created")
    print(f"       ID: {sheet_id}")
    print(f"       URL: https://docs.google.com/spreadsheets/d/{sheet_id}")
    return sheet_id


def _write_headers(sheets_svc, sheet_id: str) -> None:
    """Write or update the header row (always writes to ensure tracker columns exist)."""
    result = (
        sheets_svc.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range="Sheet1!A1:AA1")
        .execute()
    )
    existing = result.get("values", [])
    existing_count = len(existing[0]) if existing and existing[0] else 0

    if existing_count >= len(SHEET_HEADERS):
        print(f"  [OK] Header row already complete ({existing_count} columns)")
        return

    sheets_svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]},
    ).execute()
    if existing_count > 0:
        print(f"  [OK] Header row updated: {existing_count} -> {len(SHEET_HEADERS)} columns")
    else:
        print(f"  [OK] Header row written ({len(SHEET_HEADERS)} columns)")


def _apply_formatting(sheets_svc, sheet_id: str) -> None:
    """Bold header, freeze row 1, highlight tracker columns, conditional Status colours."""
    try:
        meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
        numeric_sheet_id = meta["sheets"][0]["properties"]["sheetId"]

        # Column W = index 22 (0-based); AA = index 26
        reqs = [
            # Bold + blue header row
            {
                "repeatCell": {
                    "range": {"sheetId": numeric_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.98},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            # Freeze row 1
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": numeric_sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Light yellow tint on tracker columns (W–AA) header
            {
                "repeatCell": {
                    "range": {
                        "sheetId": numeric_sheet_id,
                        "startRowIndex": 0, "endRowIndex": 1,
                        "startColumnIndex": 22, "endColumnIndex": 27,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
        ]

        # Conditional formatting for Status column (W = col index 22)
        status_rules = [
            ("New",         {"red": 1.0,  "green": 0.95, "blue": 0.6}),   # yellow
            ("In Progress", {"red": 0.7,  "green": 0.85, "blue": 1.0}),   # blue
            ("Responded",   {"red": 0.8,  "green": 1.0,  "blue": 0.8}),   # green
            ("Scheduled",   {"red": 0.85, "green": 1.0,  "blue": 0.85}),  # light green
            ("Completed",   {"red": 0.88, "green": 0.88, "blue": 0.88}),  # grey
            ("Cancelled",   {"red": 1.0,  "green": 0.8,  "blue": 0.8}),   # red
        ]
        for status_val, bg_color in status_rules:
            reqs.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": numeric_sheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": 22, "endColumnIndex": 23,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": status_val}],
                            },
                            "format": {"backgroundColor": bg_color},
                        },
                    },
                    "index": 0,
                }
            })

        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body={"requests": reqs}
        ).execute()
        print("  [OK] Formatting applied (bold header, frozen row 1, Status colour-coding)")
    except Exception as exc:
        print(f"  [WARN] Formatting step skipped: {exc}")


def _purge_excluded_rows(sheets_svc, sheet_id: str) -> int:
    """
    Delete rows whose Category (col G = index 6) or Current Folder (col R = index 17)
    match the skip lists defined in log_to_google_sheets.py.
    Returns count of rows deleted.
    """
    # Reload skip sets directly to stay in sync
    skip_categories = {
        "job alert", "job alerts", "job_alert", "job_alerts", "spam", "deleted",
    }
    skip_folders = {
        "job alerts", "job alert", "deleted", "deleted items",
        "trash", "[gmail]/trash", "spam", "[gmail]/spam", "junk",
    }

    try:
        result = (
            sheets_svc.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range="Sheet1!A:AA")
            .execute()
        )
        all_rows = result.get("values", [])
        if len(all_rows) <= 1:
            print("  [OK] No data rows to purge")
            return 0

        # Collect 0-based row indices to delete (skip header row 0)
        rows_to_delete = []
        for i, row in enumerate(all_rows[1:], start=1):
            category = row[6].lower().strip() if len(row) > 6 else ""
            folder   = row[17].lower().strip() if len(row) > 17 else ""
            if category in skip_categories or folder in skip_folders:
                rows_to_delete.append(i)

        if not rows_to_delete:
            print("  [OK] No excluded rows found in sheet")
            return 0

        # Delete in reverse order so row indices stay valid
        meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
        numeric_sheet_id = meta["sheets"][0]["properties"]["sheetId"]

        requests = []
        for row_idx in sorted(rows_to_delete, reverse=True):
            requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId": numeric_sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row_idx,
                        "endIndex": row_idx + 1,
                    }
                }
            })

        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body={"requests": requests}
        ).execute()

        print(f"  [OK] Purged {len(rows_to_delete)} excluded rows (Job Alert / Deleted)")
        return len(rows_to_delete)

    except Exception as exc:
        print(f"  [WARN] Purge step skipped: {exc}")
        return 0


def _print_env_snippet(sheet_id: str) -> None:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    print("\n" + "=" * 60)
    print("Add these lines to your root .env file:")
    print("=" * 60)
    print(f"GOOGLE_SHEET_ID={sheet_id}")
    print()
    print("Add this line to services/dashboard/frontend/.env:")
    print("=" * 60)
    print(f"VITE_GOOGLE_SHEET_URL={url}")
    print("=" * 60)
    print()
    print(f"Open the sheet: {url}")


def main() -> None:
    print("=" * 60)
    print("  InboxGenius -- Google Sheets Setup Helper")
    print("=" * 60)

    # 1. Check credentials
    key_path = _resolve_key_path()
    if not key_path:
        print("\nERROR: GOOGLE_SERVICE_ACCOUNT_KEY_PATH not set in .env")
        print("\nQuick guide:")
        print("  1. Google Cloud Console -> select/create a project")
        print("  2. APIs & Services -> Enable 'Google Sheets API' + 'Google Drive API'")
        print("  3. IAM & Admin -> Service Accounts -> Create Service Account")
        print("     Name: inboxgenius-sheets   Role: Editor")
        print("  4. Click the service account -> Keys -> Add Key -> JSON -> download")
        print("     Save as: config/service-account-key.json")
        print("  5. Add to .env:")
        print("     GOOGLE_SERVICE_ACCOUNT_KEY_PATH=config/service-account-key.json")
        print("  6. Re-run: python execution/setup_google_sheets.py")
        sys.exit(1)

    if not os.path.isfile(key_path):
        print(f"\nERROR: Service account key file not found: {key_path}")
        print("   Download it from Google Cloud Console -> IAM -> Service Accounts -> Keys")
        sys.exit(1)

    print(f"\n  Key file: {key_path}")

    # 2. Load credentials + build services
    print("  Loading credentials...")
    creds = _get_credentials(key_path)
    sheets_svc, drive_svc = _build_services(creds)

    # Print service account email for reference
    try:
        import json
        with open(key_path) as f:
            key_data = json.load(f)
        sa_email = key_data.get("client_email", "unknown")
        print(f"  [OK] Service account: {sa_email}")
    except Exception:
        sa_email = "unknown"

    # 3. Find or create spreadsheet
    existing_id = os.getenv("GOOGLE_SHEET_ID", "").strip()

    if existing_id:
        print(f"\n  [OK] Using existing sheet ID: {existing_id}")
        sheet_id = existing_id
        try:
            meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
            print(f"       Title: {meta['properties']['title']}")
        except Exception as exc:
            print(f"\nERROR: Cannot access sheet '{sheet_id}': {exc}")
            print("   Make sure the sheet is shared with the service account email above.")
            sys.exit(1)
    else:
        # Try auto-create; if it fails, guide the user to create manually
        print("\n  Attempting to create spreadsheet automatically...")
        try:
            sheet_id = _create_spreadsheet(sheets_svc)
        except Exception as exc:
            print(f"\n  Auto-create failed ({exc})")
            print("\n  --> Manual setup (takes 30 seconds):")
            print(f"      1. Go to https://sheets.google.com and create a blank spreadsheet")
            print(f"         Name it: InboxGenius Email Audit")
            print(f"      2. Share it with Editor access to:")
            print(f"         {sa_email}")
            print(f"      3. Copy the sheet ID from the URL:")
            print(f"         https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit")
            print(f"      4. Add to .env:  GOOGLE_SHEET_ID=<SHEET_ID>")
            print(f"      5. Re-run: python execution/setup_google_sheets.py")
            sys.exit(1)

    # 4. Write headers
    print("\n  Writing header row...")
    _write_headers(sheets_svc, sheet_id)

    # 5. Apply formatting
    print("  Applying formatting...")
    _apply_formatting(sheets_svc, sheet_id)

    # 5b. Purge any excluded rows already in the sheet
    print("  Purging excluded rows (Job Alert / Deleted)...")
    _purge_excluded_rows(sheets_svc, sheet_id)

    # 6. Send test row
    print("\n  Sending test row to verify write access...")
    try:
        test_row = ["SETUP_TEST"] + [""] * (len(SHEET_HEADERS) - 2) + ["setup-script"]
        sheets_svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A:AA",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [test_row]},
        ).execute()
        print("  [OK] Test row appended -- you can delete row 2 from the sheet.")
    except Exception as exc:
        print(f"  [WARN] Test row failed: {exc}")
        print("   Check that the service account has Editor access to the sheet.")

    # 7. Output .env snippets
    _print_env_snippet(sheet_id)

    print("\n[DONE] Google Sheets setup complete!")
    print("  Re-run this script any time to re-validate your setup.\n")


if __name__ == "__main__":
    main()

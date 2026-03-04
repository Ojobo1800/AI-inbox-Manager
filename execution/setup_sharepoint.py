"""
SharePoint Setup Helper — run once to configure the audit list.

This script:
  1. Validates your Azure credentials
  2. Finds your SharePoint site and outputs its Site ID
  3. Creates (or validates) the InboxGenius Email Audit list with all 22 columns
  4. Outputs the List ID to copy into your .env

Usage:
  cd execution
  python setup_sharepoint.py

Required env vars (add to root .env before running):
  SHAREPOINT_TENANT_ID   — Azure Portal → Azure AD → Overview → Tenant ID
  SHAREPOINT_CLIENT_ID   — Azure Portal → App Registrations → your app → Application (client) ID
  SHAREPOINT_CLIENT_SECRET — Azure Portal → App Registrations → your app → Certificates & Secrets
  SHAREPOINT_SITE_HOSTNAME — your tenant hostname, e.g. colaberry.sharepoint.com
  SHAREPOINT_SITE_NAME   — the site path name, e.g. InboxGenius (or just the root site)

Optional (if you already know them):
  SHAREPOINT_SITE_ID     — skip site lookup if already known
  SHAREPOINT_LIST_ID     — skip list creation if already known
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

# ── Load root .env ──────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_script_dir)
load_dotenv(os.path.join(_root_dir, ".env"))

_GRAPH = "https://graph.microsoft.com/v1.0"

# ── Column schema matching log_to_sharepoint.py ──────────────────────────────
# (internal name, display name, type, extra)
_COLUMNS = [
    ("EmailUID",          "Email UID",              "text",     {}),
    ("Subject",           "Subject",                "text",     {}),
    ("FromAddress",       "From Address",           "text",     {}),
    ("ReceivedDate",      "Received Date",          "dateTime", {"dateTime": {"displayAs": "dateTime", "format": "dateTimeStDateTime"}}),
    ("ProcessedDate",     "Processed Date",         "dateTime", {"dateTime": {"displayAs": "dateTime", "format": "dateTimeStDateTime"}}),
    ("Category",          "Category",               "text",     {}),
    ("Confidence",        "Confidence Score",       "number",   {"number": {"decimalPlaces": "four", "displayAs": "number"}}),
    ("CompanyName",       "Company Name",           "text",     {}),
    ("PositionTitle",     "Position Title",         "text",     {}),
    ("ContactName",       "Contact Name",           "text",     {}),
    ("ContactEmail",      "Contact Email",          "text",     {}),
    ("InterviewDate",     "Interview Date",         "text",     {}),
    ("InterviewTime",     "Interview Time",         "text",     {}),
    ("InterviewTimezone", "Interview Timezone",     "text",     {}),
    ("InterviewFormat",   "Interview Format",       "text",     {}),
    ("ActionRequired",    "Action Required",        "note",     {}),
    ("CurrentFolder",     "Current Folder",         "text",     {}),
    ("RequiresReview",    "Requires Manual Review", "boolean",  {}),
    ("IsEdgeCase",        "Is Edge Case",           "boolean",  {}),
    ("EdgeCaseType",      "Edge Case Type",         "text",     {}),
    ("GptModel",          "GPT Model",              "text",     {}),
]


def _get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
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
    if resp.status_code != 200:
        print(f"\n❌ Token request failed ({resp.status_code}):")
        print(resp.text[:500])
        sys.exit(1)
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_site_id(token: str, hostname: str, site_name: str) -> str:
    """Look up site ID from hostname + site path name."""
    if site_name.lower() in ("root", "", "/"):
        url = f"{_GRAPH}/sites/{hostname}"
    else:
        url = f"{_GRAPH}/sites/{hostname}:/sites/{site_name}"

    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code != 200:
        print(f"\n❌ Could not find site '{site_name}' on '{hostname}' ({resp.status_code}):")
        print(resp.text[:500])
        print("\nAvailable sites (listing root):")
        r2 = requests.get(f"{_GRAPH}/sites/{hostname}", headers=_headers(token), timeout=15)
        print(r2.text[:500])
        sys.exit(1)

    data = resp.json()
    site_id = data["id"]
    print(f"✅ Site found: {data.get('displayName', 'Unknown')}")
    print(f"   Site ID: {site_id}")
    return site_id


def _find_or_create_list(token: str, site_id: str, list_name: str = "InboxGenius Email Audit") -> str:
    """Find existing list by name, or create it. Returns list ID."""
    url = f"{_GRAPH}/sites/{site_id}/lists"
    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code != 200:
        print(f"\n❌ Could not fetch lists ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    lists = resp.json().get("value", [])
    for lst in lists:
        if lst.get("displayName") == list_name:
            list_id = lst["id"]
            print(f"✅ Existing list found: '{list_name}'")
            print(f"   List ID: {list_id}")
            return list_id

    # Create new list
    print(f"\n📋 Creating list '{list_name}'...")
    payload = {
        "displayName": list_name,
        "list": {"template": "genericList"},
        "columns": [],  # We'll add columns after creation
    }
    resp = requests.post(url, headers=_headers(token), json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        print(f"\n❌ List creation failed ({resp.status_code}): {resp.text[:500]}")
        sys.exit(1)

    list_id = resp.json()["id"]
    print(f"✅ List created: '{list_name}'")
    print(f"   List ID: {list_id}")
    return list_id


def _get_existing_columns(token: str, site_id: str, list_id: str) -> set:
    """Return set of existing column internal names (to skip re-creating)."""
    url = f"{_GRAPH}/sites/{site_id}/lists/{list_id}/columns"
    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code != 200:
        return set()
    cols = resp.json().get("value", [])
    return {c.get("name", "") for c in cols}


def _add_column(token: str, site_id: str, list_id: str, col_def: tuple) -> bool:
    """Add a single column to the list. Returns True on success."""
    internal_name, display_name, col_type, extra = col_def

    body: dict = {"name": internal_name, "displayName": display_name}

    if col_type == "text":
        body["text"] = {}
    elif col_type == "note":
        body["text"] = {"allowMultipleLines": True}
    elif col_type == "number":
        body["number"] = extra.get("number", {})
    elif col_type == "boolean":
        body["boolean"] = {}
    elif col_type == "dateTime":
        body["dateTime"] = extra.get("dateTime", {"displayAs": "dateTime", "format": "dateTimeStDateTime"})

    url = f"{_GRAPH}/sites/{site_id}/lists/{list_id}/columns"
    resp = requests.post(url, headers=_headers(token), json=body, timeout=15)

    if resp.status_code in (200, 201):
        return True
    elif resp.status_code == 422 or "already exists" in resp.text.lower():
        return True  # Already exists — that's fine
    else:
        print(f"   ⚠️  Column '{display_name}' ({resp.status_code}): {resp.text[:200]}")
        return False


def _ensure_columns(token: str, site_id: str, list_id: str) -> int:
    """Add all required columns that don't already exist. Returns count added."""
    existing = _get_existing_columns(token, site_id, list_id)
    added = 0
    skipped = 0

    print(f"\n📐 Configuring columns ({len(_COLUMNS)} required)...")
    for col_def in _COLUMNS:
        internal_name = col_def[0]
        if internal_name in existing:
            skipped += 1
            continue
        success = _add_column(token, site_id, list_id, col_def)
        if success:
            added += 1
            print(f"   ✅ Added: {col_def[1]}")
        time.sleep(0.3)  # Avoid throttling

    print(f"\n   Columns added: {added}  |  Already existed: {skipped}")
    return added


def _send_test_item(token: str, site_id: str, list_id: str) -> bool:
    """POST a test item to verify write permissions work."""
    url = f"{_GRAPH}/sites/{site_id}/lists/{list_id}/items"
    fields = {
        "Title": "SETUP_TEST — safe to delete",
        "Subject": "Setup validation item",
        "Category": "Test",
        "GptModel": "setup-script",
    }
    resp = requests.post(url, headers=_headers(token), json={"fields": fields}, timeout=15)
    if resp.status_code in (200, 201):
        item_id = resp.json().get("id", "?")
        print(f"\n✅ Test item created (id={item_id}) — you can delete it from SharePoint.")
        return True
    else:
        print(f"\n⚠️  Test item failed ({resp.status_code}): {resp.text[:300]}")
        return False


def _write_env_snippet(site_id: str, list_id: str, hostname: str, site_name: str) -> None:
    """Print the .env lines to add."""
    # Build the SharePoint list URL for the frontend
    sp_url = f"https://{hostname}/sites/{site_name}/Lists/InboxGenius%20Email%20Audit/AllItems.aspx"
    if site_name.lower() in ("root", "", "/"):
        sp_url = f"https://{hostname}/Lists/InboxGenius%20Email%20Audit/AllItems.aspx"

    print("\n" + "═" * 60)
    print("📋 Add these lines to your root .env file:")
    print("═" * 60)
    print(f"SHAREPOINT_SITE_ID={site_id}")
    print(f"SHAREPOINT_LIST_ID={list_id}")
    print()
    print("📋 Add this line to services/dashboard/frontend/.env:")
    print("═" * 60)
    print(f"VITE_SHAREPOINT_LIST_URL={sp_url}")
    print("═" * 60)


def main() -> None:
    print("=" * 60)
    print("  InboxGenius — SharePoint Setup Helper")
    print("=" * 60)

    # ── 1. Collect credentials ──────────────────────────────────────────────
    tenant_id     = os.getenv("SHAREPOINT_TENANT_ID", "").strip()
    client_id     = os.getenv("SHAREPOINT_CLIENT_ID", "").strip()
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET", "").strip()
    hostname      = os.getenv("SHAREPOINT_SITE_HOSTNAME", "").strip()
    site_name     = os.getenv("SHAREPOINT_SITE_NAME", "root").strip()

    # Allow override if full Site ID already known
    known_site_id = os.getenv("SHAREPOINT_SITE_ID", "").strip()
    known_list_id = os.getenv("SHAREPOINT_LIST_ID", "").strip()

    missing = []
    if not tenant_id:     missing.append("SHAREPOINT_TENANT_ID")
    if not client_id:     missing.append("SHAREPOINT_CLIENT_ID")
    if not client_secret: missing.append("SHAREPOINT_CLIENT_SECRET")
    if not hostname and not known_site_id:
        missing.append("SHAREPOINT_SITE_HOSTNAME  (e.g. colaberry.sharepoint.com)")

    if missing:
        print("\n❌ Missing required environment variables in root .env:\n")
        for m in missing:
            print(f"   {m}")
        print("\nSee .env.example for setup instructions.")
        print("\nQuick guide:")
        print("  1. Go to https://portal.azure.com")
        print("  2. Azure Active Directory → Overview → copy 'Tenant ID'")
        print("  3. App Registrations → New Registration → name: InboxGenius-SharePoint")
        print("  4. After creating: copy 'Application (client) ID'")
        print("  5. Certificates & Secrets → New client secret → copy the VALUE")
        print("  6. API Permissions → Add → Microsoft Graph → Application permissions:")
        print("     → Sites.ReadWrite.All → Grant admin consent")
        print("  7. Add to .env:")
        print("     SHAREPOINT_TENANT_ID=<tenant-id>")
        print("     SHAREPOINT_CLIENT_ID=<client-id>")
        print("     SHAREPOINT_CLIENT_SECRET=<secret-value>")
        print("     SHAREPOINT_SITE_HOSTNAME=colaberry.sharepoint.com")
        print("     SHAREPOINT_SITE_NAME=root  (or your site path name)")
        print("\nThen re-run: python execution/setup_sharepoint.py")
        sys.exit(1)

    print(f"\n🔑 Tenant: {tenant_id}")
    print(f"   Client: {client_id[:8]}...")
    print(f"   Host:   {hostname}")
    print(f"   Site:   {site_name}")

    # ── 2. Get access token ─────────────────────────────────────────────────
    print("\n🔐 Obtaining access token...")
    token = _get_token(tenant_id, client_id, client_secret)
    print("✅ Token obtained")

    # ── 3. Resolve Site ID ──────────────────────────────────────────────────
    if known_site_id:
        site_id = known_site_id
        print(f"\n✅ Using existing Site ID: {site_id}")
    else:
        print(f"\n🔍 Looking up site '{site_name}' on '{hostname}'...")
        site_id = _get_site_id(token, hostname, site_name)

    # ── 4. Find or create the list ──────────────────────────────────────────
    if known_list_id:
        list_id = known_list_id
        print(f"\n✅ Using existing List ID: {list_id}")
    else:
        list_id = _find_or_create_list(token, site_id)

    # ── 5. Ensure all columns exist ─────────────────────────────────────────
    _ensure_columns(token, site_id, list_id)

    # ── 6. Send test item ───────────────────────────────────────────────────
    print("\n🧪 Sending test item to verify write permissions...")
    _send_test_item(token, site_id, list_id)

    # ── 7. Output .env snippets ─────────────────────────────────────────────
    _write_env_snippet(site_id, list_id, hostname, site_name)

    print("\n✅ SharePoint setup complete!")
    print("   Copy the values above into your .env files,")
    print("   then restart the backend + frontend servers.")


if __name__ == "__main__":
    main()

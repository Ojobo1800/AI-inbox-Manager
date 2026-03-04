"""
Gmail OAuth2 token manager.

Handles loading, refreshing, and storing OAuth2 credentials for Gmail IMAP access.
Token is stored at config/gmail_token.json and auto-refreshed when expired.

Usage:
    from gmail_auth import get_access_token
    token = get_access_token()  # Returns a fresh access token string
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

# Scopes required for full Gmail IMAP access
SCOPES = ["https://mail.google.com/"]

# Paths (relative to project root)
_PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = _PROJECT_ROOT / "config" / "gmail_credentials.json"
TOKEN_PATH = _PROJECT_ROOT / "config" / "gmail_token.json"


def get_credentials() -> Credentials:
    """
    Load and return valid Google OAuth2 credentials.

    - If token.json exists and is valid, returns it as-is.
    - If token.json is expired but has a refresh token, refreshes automatically.
    - If no token exists, raises RuntimeError telling user to run authorize_gmail.py.

    Returns:
        Valid google.oauth2.credentials.Credentials object

    Raises:
        RuntimeError: If no token exists (need to run one-time auth)
        FileNotFoundError: If credentials.json is missing
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Gmail credentials not found at {CREDENTIALS_PATH}. "
            "Download OAuth2 credentials from Google Cloud Console."
        )

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "No Gmail token found. Run the one-time authorization:\n"
            "  python scripts/authorize_gmail.py\n"
            f"Token will be saved to: {TOKEN_PATH}"
        )

    # Load saved token
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        logger.info("Gmail token expired — refreshing automatically...")
        creds.refresh(Request())
        _save_token(creds)
        logger.info("Gmail token refreshed and saved.")
    elif not creds.valid:
        raise RuntimeError(
            "Gmail token is invalid and cannot be refreshed. "
            "Re-run: python scripts/authorize_gmail.py"
        )

    return creds


def get_access_token() -> str:
    """
    Get a fresh OAuth2 access token string for IMAP XOAUTH2.

    Returns:
        Access token string
    """
    creds = get_credentials()
    # Force refresh if close to expiry (within 60 seconds)
    if creds.expiry and (creds.expiry - datetime.utcnow()).total_seconds() < 60:
        creds.refresh(Request())
        _save_token(creds)
    return creds.token


def _save_token(creds: Credentials) -> None:
    """Save credentials to token.json."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

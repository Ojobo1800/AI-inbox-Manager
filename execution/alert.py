"""
Failure alerting for InboxGenius — eliminates silent failures.

Sends an email alert when the processing pipeline encounters a critical error.
Uses the existing Gmail OAuth2 credentials (no new setup required).

Configuration (.env):
    ALERT_EMAIL_TO=admin@example.com   # who receives the alert
    EMAIL_ADDRESS=...                   # already set — used as the sender

Alert triggers (called from process_inbox_auto.py):
    - Unhandled fatal exception in main()
    - Pre-run cost guardrail abort (run never started)
    - Post-classification cost guardrail (emails classified but NOT moved)
    - High classification failure rate (>50% of emails failed GPT)

Fallback:
    If the Gmail send fails for any reason, the alert is written to
    logs/alerts.log so nothing is lost silently.
"""

import base64
import logging
import os
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent
_ALERTS_LOG = _PROJECT_ROOT / "logs" / "alerts.log"


def is_configured() -> bool:
    """Return True if ALERT_EMAIL_TO is set in the environment."""
    return bool(os.getenv("ALERT_EMAIL_TO", "").strip())


def send_failure_alert(
    subject: str,
    body: str,
    exc: Optional[BaseException] = None,
) -> bool:
    """
    Send a failure alert email using the existing Gmail OAuth2 credentials.

    Falls back to writing to logs/alerts.log if the email send fails.
    Never raises — all exceptions are caught internally.

    Args:
        subject:  Email subject line (prefix "[InboxGenius]" is added automatically)
        body:     Plain-text body
        exc:      Optional exception to append traceback from

    Returns:
        True if the email was sent, False if only the fallback log was written.
    """
    if not is_configured():
        logger.debug("Alert not configured (ALERT_EMAIL_TO not set) — skipping")
        return False

    full_subject = subject if subject.startswith("[InboxGenius]") else f"[InboxGenius] {subject}"

    # Append traceback if an exception was provided
    full_body = body
    if exc is not None:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        full_body = f"{body}\n\n--- Traceback ---\n{tb}"

    # Always write to the alert log first (so it's never lost)
    _write_alert_log(full_subject, full_body)

    # Try to send via Gmail
    try:
        _send_via_gmail_oauth(full_subject, full_body)
        logger.info("Alert sent: %s", full_subject)
        return True
    except Exception as send_exc:
        logger.warning(
            "Alert email failed (alert written to logs/alerts.log): %s", send_exc
        )
        return False


def _send_via_gmail_oauth(subject: str, body: str) -> None:
    """
    Send an email via Gmail SMTP using the existing OAuth2 access token.

    The https://mail.google.com/ scope (already in gmail_token.json) covers
    both IMAP reading and SMTP sending via XOAUTH2.
    """
    from_email = os.getenv("EMAIL_ADDRESS", "").strip()
    to_email = os.getenv("ALERT_EMAIL_TO", "").strip()

    if not from_email:
        raise ValueError("EMAIL_ADDRESS not set — cannot send alert")
    if not to_email:
        raise ValueError("ALERT_EMAIL_TO not set — cannot send alert")

    # Get a fresh access token from the existing Gmail OAuth flow
    from gmail_auth import get_access_token
    access_token = get_access_token()

    # Build XOAUTH2 auth string
    auth_string = f"user={from_email}\x01auth=Bearer {access_token}\x01\x01"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()

    # Build the email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"InboxGenius <{from_email}>"
    msg["To"] = to_email
    msg["X-Priority"] = "1"  # Mark as high priority

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    footer = f"\n\n---\nSent by InboxGenius at {timestamp}\nHost: {os.getenv('COMPUTERNAME', 'unknown')}"
    msg.attach(MIMEText(body + footer, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        # Authenticate with XOAUTH2
        code, resp = smtp.docmd("AUTH", f"XOAUTH2 {auth_b64}")
        if code not in (235, 334):
            raise smtplib.SMTPAuthenticationError(code, resp)
        smtp.sendmail(from_email, [to_email], msg.as_string())


def _write_alert_log(subject: str, body: str) -> None:
    """Append alert to logs/alerts.log as a permanent record."""
    try:
        _ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        separator = "=" * 70
        entry = (
            f"\n{separator}\n"
            f"ALERT  {timestamp}\n"
            f"SUBJECT: {subject}\n"
            f"{separator}\n"
            f"{body}\n"
        )
        with open(_ALERTS_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as exc:
        logger.error("Could not write to alerts.log: %s", exc)

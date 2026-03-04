import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any


def _extract_company_from_sender(sender: str) -> str:
    if not sender:
        return ""

    match = re.search(r"@([A-Za-z0-9.-]+)", sender)
    if not match:
        return ""

    domain = match.group(1).lower()
    parts = [p for p in domain.split(".") if p and p not in {"com", "org", "net", "io", "co"}]
    return parts[0].capitalize() if parts else ""


def _extract_position_from_subject(subject: str) -> str:
    if not subject:
        return ""

    patterns = [
        r"interview\s*(?:for|with|regarding)?\s*[:-]\s*(.+)$",
        r"(?:position|role)\s*[:-]\s*(.+)$",
    ]
    lower_subject = subject.lower()
    for pattern in patterns:
        match = re.search(pattern, lower_subject, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().title()

    cleaned = re.sub(r"(?i)interview|request|schedule|availability|screening", "", subject)
    cleaned = re.sub(r"[-_:]+", " ", cleaned).strip()
    return cleaned[:120]


def _normalize_sent_at(sent_at: str) -> str:
    if not sent_at:
        return ""
    try:
        dt = parsedate_to_datetime(sent_at)
        if dt.tzinfo:
            return dt.astimezone().isoformat()
        return dt.isoformat()
    except Exception:
        return sent_at


def map_message_to_interview_record(email_address: str, message: dict[str, Any]) -> dict[str, Any]:
    subject = message.get("subject", "")
    sender = message.get("sender", "")
    snippet = message.get("snippet", "")

    company_name = _extract_company_from_sender(sender)
    position_title = _extract_position_from_subject(subject)
    sent_at_iso = _normalize_sent_at(message.get("sent_at", ""))

    return {
        "record_key": message.get("message_id", ""),
        "email_address": email_address,
        "company_name": company_name,
        "position_title": position_title,
        "interview_type": "unknown",
        "interview_datetime": "",
        "status": "pending",
        "source": "gmail",
        "source_message_id": message.get("message_id", ""),
        "subject": subject,
        "sender": sender,
        "snippet": snippet,
        "received_at": sent_at_iso or datetime.utcnow().isoformat(),
    }

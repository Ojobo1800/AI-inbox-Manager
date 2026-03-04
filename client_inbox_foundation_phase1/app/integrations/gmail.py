import base64
import json
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from app.core.config import settings


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
INTERVIEW_KEYWORDS = [
    "interview",
    "screening",
    "recruiter",
    "hiring",
    "availability",
    "schedule",
    "assessment",
]


def _load_service_account_credentials():
    if not settings.google_service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is required")

    creds = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json,
        scopes=GMAIL_SCOPES,
    )
    if settings.google_workspace_user:
        creds = creds.with_subject(settings.google_workspace_user)
    return creds


def build_gmail_service() -> Resource:
    creds = _load_service_account_credentials()
    return build("gmail", "v1", credentials=creds)


def parse_label_ids(value: str) -> list[str]:
    return [label.strip() for label in value.split(",") if label.strip()]


def start_gmail_watch() -> dict[str, Any]:
    if not settings.google_cloud_project or not settings.google_pubsub_topic:
        raise ValueError("GOOGLE_CLOUD_PROJECT and GOOGLE_PUBSUB_TOPIC are required")

    service = build_gmail_service()
    topic_name = f"projects/{settings.google_cloud_project}/topics/{settings.google_pubsub_topic}"

    body: dict[str, Any] = {
        "topicName": topic_name,
        "labelFilterBehavior": settings.gmail_watch_label_filter_action,
    }

    label_ids = parse_label_ids(settings.gmail_watch_label_ids)
    if label_ids:
        body["labelIds"] = label_ids

    response = service.users().watch(userId=settings.gmail_user_id, body=body).execute()
    return response


def decode_pubsub_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Invalid Pub/Sub payload: missing message object")

    encoded_data = message.get("data")
    if not encoded_data:
        raise ValueError("Invalid Pub/Sub payload: message.data is required")

    pad_length = (-len(encoded_data)) % 4
    encoded_data += "=" * pad_length

    try:
        decoded_bytes = base64.urlsafe_b64decode(encoded_data.encode("utf-8"))
        decoded_json = json.loads(decoded_bytes.decode("utf-8"))
    except Exception as exc:  # pragma: no cover
        raise ValueError("Failed to decode Pub/Sub message data") from exc

    email_address = decoded_json.get("emailAddress")
    history_id = decoded_json.get("historyId")
    if not email_address or not history_id:
        raise ValueError("Decoded Gmail push payload missing emailAddress/historyId")

    return {
        "emailAddress": email_address,
        "historyId": str(history_id),
        "pubsubMessageId": message.get("messageId"),
        "publishTime": message.get("publishTime"),
        "subscription": payload.get("subscription"),
    }


def _header_value(headers: list[dict[str, str]], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _decode_body_data(data: str) -> str:
    if not data:
        return ""
    pad_length = (-len(data)) % 4
    data += "=" * pad_length
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")


def _extract_text_from_payload(payload: dict[str, Any]) -> str:
    if not payload:
        return ""

    body = payload.get("body", {})
    text = _decode_body_data(body.get("data", "")) if isinstance(body, dict) else ""

    parts = payload.get("parts", [])
    if isinstance(parts, list):
        for part in parts:
            text += "\n" + _extract_text_from_payload(part)
    return text.strip()


def _is_interview_related(subject: str, snippet: str, body_text: str) -> bool:
    haystack = f"{subject} {snippet} {body_text}".lower()
    return any(keyword in haystack for keyword in INTERVIEW_KEYWORDS)


def collect_incremental_unread_interview_messages(start_history_id: str) -> dict[str, Any]:
    service = build_gmail_service()
    message_ids: set[str] = set()
    latest_history_id = start_history_id
    page_token: str | None = None

    try:
        while True:
            response = (
                service.users()
                .history()
                .list(
                    userId=settings.gmail_user_id,
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                    maxResults=100,
                    pageToken=page_token,
                )
                .execute()
            )

            latest_history_id = str(response.get("historyId", latest_history_id))
            for record in response.get("history", []):
                for added in record.get("messagesAdded", []):
                    message = added.get("message", {})
                    message_id = message.get("id")
                    if message_id:
                        message_ids.add(message_id)

            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:
        if getattr(exc, "status_code", None) == 404:
            raise ValueError("Gmail historyId expired. Reinitialize watch/checkpoint.") from exc
        raise

    processed: list[dict[str, Any]] = []
    interview_unread: list[dict[str, Any]] = []

    for message_id in message_ids:
        raw = (
            service.users()
            .messages()
            .get(userId=settings.gmail_user_id, id=message_id, format="full")
            .execute()
        )

        payload = raw.get("payload", {})
        headers = payload.get("headers", []) if isinstance(payload, dict) else []

        subject = _header_value(headers, "Subject")
        sender = _header_value(headers, "From")
        sent_at = _header_value(headers, "Date")
        snippet = raw.get("snippet", "")
        body_text = _extract_text_from_payload(payload)

        label_ids = raw.get("labelIds", [])
        is_unread = "UNREAD" in label_ids
        is_related = _is_interview_related(subject, snippet, body_text)

        normalized = {
            "message_id": raw.get("id"),
            "thread_id": raw.get("threadId"),
            "history_id": str(raw.get("historyId", "")),
            "subject": subject,
            "sender": sender,
            "sent_at": sent_at,
            "snippet": snippet,
            "body_excerpt": body_text[:1200],
            "is_unread": is_unread,
            "is_interview_related": is_related,
            "raw": raw,
        }
        processed.append(normalized)

        if is_unread and is_related:
            interview_unread.append(normalized)

    return {
        "start_history_id": start_history_id,
        "latest_history_id": latest_history_id,
        "processed_count": len(processed),
        "interview_unread_count": len(interview_unread),
        "messages": interview_unread,
    }

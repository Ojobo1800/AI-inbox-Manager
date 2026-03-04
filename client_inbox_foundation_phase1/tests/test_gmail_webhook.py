import base64
import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _build_pubsub_payload(email: str, history_id: str) -> dict:
    raw = json.dumps({"emailAddress": email, "historyId": history_id}).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return {
        "message": {
            "data": encoded,
            "messageId": "123",
            "publishTime": "2026-02-16T00:00:00Z",
        },
        "subscription": "projects/test/subscriptions/gmail-sub",
    }


def test_gmail_webhook_decodes_payload(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.webhooks.settings.google_pubsub_verification_token", "abc123")

    captured: dict = {}

    def fake_upsert(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("app.api.routes.webhooks.upsert_gmail_checkpoint", fake_upsert)

    payload = _build_pubsub_payload("student@example.com", "987654")
    response = client.post(
        "/webhooks/gmail",
        headers={"x-google-verification-token": "abc123"},
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is True
    assert data["email_address"] == "student@example.com"
    assert data["history_id"] == "987654"

    assert captured["email_address"] == "student@example.com"
    assert captured["history_id"] == "987654"
    assert captured["pubsub_message_id"] == "123"


def test_gmail_webhook_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.webhooks.settings.google_pubsub_verification_token", "abc123")

    payload = _build_pubsub_payload("student@example.com", "987654")
    response = client.post(
        "/webhooks/gmail",
        headers={"x-google-verification-token": "wrong"},
        json=payload,
    )

    assert response.status_code == 401


def test_gmail_webhook_rejects_bad_payload(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.webhooks.settings.google_pubsub_verification_token", "")

    response = client.post("/webhooks/gmail", json={"message": {}})
    assert response.status_code == 400


def test_gmail_webhook_returns_500_when_checkpoint_persist_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.webhooks.settings.google_pubsub_verification_token", "")

    def failing_upsert(**_kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("app.api.routes.webhooks.upsert_gmail_checkpoint", failing_upsert)

    payload = _build_pubsub_payload("student@example.com", "987654")
    response = client.post("/webhooks/gmail", json=payload)

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to persist Gmail checkpoint"

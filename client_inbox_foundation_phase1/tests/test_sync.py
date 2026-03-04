from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_sync_incremental_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.sync.get_gmail_checkpoint",
        lambda email: {"email_address": email, "history_id": "1001"},
    )

    monkeypatch.setattr(
        "app.api.routes.sync.collect_incremental_unread_interview_messages",
        lambda _start_history_id: {
            "latest_history_id": "1010",
            "processed_count": 3,
            "interview_unread_count": 1,
            "messages": [
                {
                    "message_id": "m-1",
                    "thread_id": "t-1",
                    "history_id": "1010",
                    "subject": "Interview Availability",
                    "sender": "recruiter@example.com",
                    "sent_at": "Tue, 17 Feb 2026 10:00:00 -0500",
                    "snippet": "Can you share availability",
                    "body_excerpt": "Please pick a slot",
                    "is_unread": True,
                    "is_interview_related": True,
                    "raw": {"id": "m-1"},
                }
            ],
        },
    )

    monkeypatch.setattr(
        "app.api.routes.sync.map_message_to_interview_record",
        lambda email, message: {
            "record_key": message["message_id"],
            "email_address": email,
            "company_name": "Example",
            "position_title": "Data Analyst",
            "interview_type": "unknown",
            "interview_datetime": "",
            "status": "pending",
            "source": "gmail",
            "source_message_id": message["message_id"],
            "subject": message["subject"],
            "sender": message["sender"],
            "snippet": message["snippet"],
            "received_at": "2026-02-17T10:00:00-05:00",
        },
    )

    captured: dict = {"stored": [], "checkpoint": None, "tracker": [], "sheet": []}

    def fake_store(email, message):
        captured["stored"].append((email, message["message_id"]))

    def fake_checkpoint(**kwargs):
        captured["checkpoint"] = kwargs

    def fake_tracker(record):
        captured["tracker"].append(record["record_key"])

    def fake_sheet(record):
        captured["sheet"].append(record["record_key"])

    monkeypatch.setattr("app.api.routes.sync.upsert_unread_intake_email", fake_store)
    monkeypatch.setattr("app.api.routes.sync.upsert_gmail_checkpoint", fake_checkpoint)
    monkeypatch.setattr("app.api.routes.sync.upsert_interview_tracker_record", fake_tracker)
    monkeypatch.setattr("app.api.routes.sync.append_interview_record", fake_sheet)

    response = client.post("/sync/gmail/incremental", json={"email_address": "student@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["processed_count"] == 3
    assert data["interview_unread_count"] == 1
    assert data["stored_message_ids"] == ["m-1"]
    assert data["tracker_record_keys"] == ["m-1"]
    assert captured["stored"] == [("student@example.com", "m-1")]
    assert captured["tracker"] == ["m-1"]
    assert captured["sheet"] == ["m-1"]
    assert captured["checkpoint"]["history_id"] == "1010"


def test_sync_incremental_missing_checkpoint(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.sync.get_gmail_checkpoint", lambda _email: None)

    response = client.post("/sync/gmail/incremental", json={"email_address": "missing@example.com"})

    assert response.status_code == 404


def test_sync_incremental_handles_expired_history(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.sync.get_gmail_checkpoint",
        lambda email: {"email_address": email, "history_id": "1"},
    )

    def fail_fetch(_start_history_id):
        raise ValueError("Gmail historyId expired. Reinitialize watch/checkpoint.")

    monkeypatch.setattr(
        "app.api.routes.sync.collect_incremental_unread_interview_messages",
        fail_fetch,
    )

    response = client.post("/sync/gmail/incremental", json={"email_address": "student@example.com"})

    assert response.status_code == 400
    assert "historyId expired" in response.json()["detail"]

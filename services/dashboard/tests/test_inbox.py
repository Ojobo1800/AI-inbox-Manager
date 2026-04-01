"""Tests for /api/inbox/* endpoints."""

from unittest.mock import patch, MagicMock

from conftest import make_email, make_classification

_INBOX_STATE = "routers.inbox.get_current_inbox_state"
_UNREAD = "routers.inbox.get_unread_emails"


class TestInboxCount:
    def test_count_from_db_empty(self, client, db, auth_cookies):
        resp = client.get("/api/inbox/count", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["synced"] is False

    def test_count_from_db_with_emails(self, client, db, auth_cookies):
        make_email(db, email_id="msg001", folder="INBOX")
        make_email(db, email_id="msg002", folder="INBOX")
        make_email(db, email_id="msg003", folder="Job Alerts")  # excluded

        resp = client.get("/api/inbox/count", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_count_refresh_calls_imap(self, client, db, auth_cookies):
        mock_emails = [MagicMock(), MagicMock(), MagicMock()]
        with patch(_INBOX_STATE, return_value=mock_emails) as mock_fn:
            resp = client.get("/api/inbox/count?refresh=true", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        assert data["synced"] is True
        mock_fn.assert_called_once()

    def test_requires_auth(self, client, db):
        resp = client.get("/api/inbox/count")
        assert resp.status_code == 401


class TestCurrentInbox:
    def test_empty_inbox(self, client, db, auth_cookies):
        resp = client.get("/api/inbox/current", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_inbox_emails(self, client, db, auth_cookies):
        email = make_email(db, subject="Job Opportunity", folder="INBOX")
        make_classification(db, email, category="Job Alert", confidence=0.90)

        resp = client.get("/api/inbox/current", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["subject"] == "Job Opportunity"
        assert data[0]["latest_category"] == "Job Alert"
        assert data[0]["latest_confidence"] == 0.90

    def test_excludes_non_inbox_emails(self, client, db, auth_cookies):
        make_email(db, folder="Job Alerts")

        resp = client.get("/api/inbox/current", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_classification_returns_none_fields(self, client, db, auth_cookies):
        make_email(db, folder="INBOX")

        resp = client.get("/api/inbox/current", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["latest_category"] is None
        assert data[0]["latest_confidence"] is None

    def test_refresh_calls_imap(self, client, db, auth_cookies):
        with patch(_INBOX_STATE, return_value=[]) as mock_fn:
            resp = client.get("/api/inbox/current?refresh=true", cookies=auth_cookies)
        assert resp.status_code == 200
        mock_fn.assert_called_once()

    def test_requires_auth(self, client, db):
        resp = client.get("/api/inbox/current")
        assert resp.status_code == 401


class TestUnreadEmails:
    def test_no_unread(self, client, db, auth_cookies):
        make_email(db, folder="INBOX")  # is_read defaults to False
        # Mark it as read manually
        from models import Email
        email = db.query(Email).first()
        email.is_read = True
        db.commit()

        resp = client.get("/api/inbox/unread", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_unread_only(self, client, db, auth_cookies):
        make_email(db, email_id="msg001", folder="INBOX")  # unread

        from models import Email
        read_email_obj = make_email(db, email_id="msg002", folder="INBOX")
        read_email_obj.is_read = True
        db.commit()

        resp = client.get("/api/inbox/unread", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_read"] is False

    def test_refresh_calls_imap(self, client, db, auth_cookies):
        with patch(_UNREAD, return_value=[]) as mock_fn:
            resp = client.get("/api/inbox/unread?refresh=true", cookies=auth_cookies)
        assert resp.status_code == 200
        mock_fn.assert_called_once()

    def test_requires_auth(self, client, db):
        resp = client.get("/api/inbox/unread")
        assert resp.status_code == 401


class TestInboxHistory:
    def test_history_empty(self, client, db, auth_cookies):
        resp = client.get("/api/inbox/history", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_emails(self, client, db, auth_cookies):
        make_email(db, email_id="msg001", folder="INBOX")
        make_email(db, email_id="msg002", folder="Job Alerts")

        resp = client.get("/api/inbox/history", cookies=auth_cookies)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_folder(self, client, db, auth_cookies):
        make_email(db, email_id="msg001", folder="INBOX")
        make_email(db, email_id="msg002", folder="Job Alerts")

        resp = client.get("/api/inbox/history?folder=Job+Alerts", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["current_folder"] == "Job Alerts"

    def test_pagination(self, client, db, auth_cookies):
        for i in range(5):
            make_email(db, email_id=f"msg{i:03d}", folder="INBOX")

        resp = client.get("/api/inbox/history?limit=2&offset=1", cookies=auth_cookies)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_requires_auth(self, client, db):
        resp = client.get("/api/inbox/history")
        assert resp.status_code == 401


class TestEmailDetail:
    def test_get_detail_success(self, client, db, auth_cookies):
        email = make_email(db, subject="Detailed Email", folder="INBOX")
        make_classification(db, email, category="Interview Request", confidence=0.88)

        resp = client.get(f"/api/inbox/{email.id}", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"]["subject"] == "Detailed Email"
        assert len(data["classifications"]) == 1
        assert data["classifications"][0]["category"] == "Interview Request"
        assert data["actions"] == []

    def test_get_detail_not_found(self, client, db, auth_cookies):
        resp = client.get("/api/inbox/99999", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.get("/api/inbox/1")
        assert resp.status_code == 401

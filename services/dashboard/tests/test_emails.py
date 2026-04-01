"""Tests for /api/emails/* endpoints."""

from unittest.mock import MagicMock, patch

from conftest import make_email, make_classification

_RECLASSIFY = "routers.emails.reclassify_email"
_MOVE = "routers.emails.move_email"
_DELETE = "routers.emails.delete_email"
_MARK_READ = "routers.emails.mark_email_read"


def _mock_action(from_folder="INBOX", to_folder="Job Alerts"):
    """Return a mock EmailAction object."""
    action = MagicMock()
    action.id = 1
    action.from_folder = from_folder
    action.to_folder = to_folder
    return action


def _mock_classification(category="Job Alert", confidence=0.92):
    """Return a mock Classification object."""
    clf = MagicMock()
    clf.category = category
    clf.confidence = confidence
    clf.company_name = "Acme Corp"
    clf.position = "Data Analyst"
    return clf


class TestClassifyEmail:
    def test_classify_success(self, client, db, auth_cookies):
        email = make_email(db)
        mock_clf = _mock_classification("Interview Request", 0.95)

        with patch(_RECLASSIFY, return_value=mock_clf):
            resp = client.post(f"/api/emails/{email.id}/classify", cookies=auth_cookies)

        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "Interview Request"
        assert data["confidence"] == 0.95

    def test_classify_email_not_found(self, client, db, auth_cookies):
        resp = client.post("/api/emails/99999/classify", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_classify_ai_error_returns_500(self, client, db, auth_cookies):
        email = make_email(db)

        with patch(_RECLASSIFY, side_effect=Exception("OpenAI timeout")):
            resp = client.post(f"/api/emails/{email.id}/classify", cookies=auth_cookies)

        assert resp.status_code == 500

    def test_requires_auth(self, client, db):
        resp = client.post("/api/emails/1/classify")
        assert resp.status_code == 401


class TestMoveEmail:
    def test_move_success(self, client, db, auth_cookies):
        email = make_email(db, folder="INBOX")
        mock_action = _mock_action(from_folder="INBOX", to_folder="Job Alerts")

        with patch(_MOVE, return_value=mock_action):
            resp = client.post(
                f"/api/emails/{email.id}/move",
                json={"target_folder": "Job Alerts"},
                cookies=auth_cookies,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Email moved successfully"
        assert data["from_folder"] == "INBOX"
        assert data["to_folder"] == "Job Alerts"

    def test_move_email_not_found(self, client, db, auth_cookies):
        resp = client.post(
            "/api/emails/99999/move",
            json={"target_folder": "Job Alerts"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404

    def test_move_integration_error_returns_500(self, client, db, auth_cookies):
        email = make_email(db)

        with patch(_MOVE, side_effect=Exception("IMAP connection failed")):
            resp = client.post(
                f"/api/emails/{email.id}/move",
                json={"target_folder": "Job Alerts"},
                cookies=auth_cookies,
            )

        assert resp.status_code == 500

    def test_move_missing_target_folder(self, client, db, auth_cookies):
        email = make_email(db)
        resp = client.post(
            f"/api/emails/{email.id}/move",
            json={},  # missing target_folder
            cookies=auth_cookies,
        )
        assert resp.status_code == 422  # Pydantic validation

    def test_requires_auth(self, client, db):
        resp = client.post("/api/emails/1/move", json={"target_folder": "Inbox"})
        assert resp.status_code == 401


class TestDeleteEmail:
    def test_delete_success(self, client, db, auth_cookies):
        email = make_email(db)
        mock_action = _mock_action()
        mock_action.id = 42

        with patch(_DELETE, return_value=mock_action):
            resp = client.post(f"/api/emails/{email.id}/delete", cookies=auth_cookies)

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Email deleted successfully"
        assert data["email_id"] == email.id

    def test_delete_with_reason(self, client, db, auth_cookies):
        email = make_email(db)
        mock_action = _mock_action()

        with patch(_DELETE, return_value=mock_action) as mock_fn:
            resp = client.post(
                f"/api/emails/{email.id}/delete",
                params={"reason": "Confirmed spam"},
                cookies=auth_cookies,
            )

        assert resp.status_code == 200
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["reason"] == "Confirmed spam"

    def test_delete_email_not_found(self, client, db, auth_cookies):
        resp = client.post("/api/emails/99999/delete", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_delete_integration_error_returns_500(self, client, db, auth_cookies):
        email = make_email(db)

        with patch(_DELETE, side_effect=Exception("IMAP error")):
            resp = client.post(f"/api/emails/{email.id}/delete", cookies=auth_cookies)

        assert resp.status_code == 500

    def test_requires_auth(self, client, db):
        resp = client.post("/api/emails/1/delete")
        assert resp.status_code == 401


class TestMarkEmailRead:
    def test_mark_as_read(self, client, db, auth_cookies):
        email = make_email(db)
        mock_action = _mock_action()

        with patch(_MARK_READ, return_value=mock_action):
            resp = client.post(
                f"/api/emails/{email.id}/mark-read",
                json={"mark_as_read": True},
                cookies=auth_cookies,
            )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Email marked as read"

    def test_mark_as_unread(self, client, db, auth_cookies):
        email = make_email(db)
        mock_action = _mock_action()

        with patch(_MARK_READ, return_value=mock_action):
            resp = client.post(
                f"/api/emails/{email.id}/mark-read",
                json={"mark_as_read": False},
                cookies=auth_cookies,
            )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Email marked as unread"

    def test_mark_read_email_not_found(self, client, db, auth_cookies):
        resp = client.post(
            "/api/emails/99999/mark-read",
            json={"mark_as_read": True},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404

    def test_mark_read_missing_body(self, client, db, auth_cookies):
        email = make_email(db)
        resp = client.post(
            f"/api/emails/{email.id}/mark-read",
            json={},
            cookies=auth_cookies,
        )
        assert resp.status_code == 422

    def test_requires_auth(self, client, db):
        resp = client.post("/api/emails/1/mark-read", json={"mark_as_read": True})
        assert resp.status_code == 401

"""Tests for /api/notifications/* endpoints."""

from unittest.mock import patch

from conftest import (
    make_email,
    make_interview_event,
    make_notification_draft,
    make_student,
)

_SEND_EMAIL = "execution.send_notification.send_email"


class TestGetPendingNotifications:
    def test_empty(self, client, db, auth_cookies):
        resp = client.get("/api/notifications/pending", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_draft_and_approved(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        make_notification_draft(db, event, email_status="draft")
        make_notification_draft(db, event, email_status="approved")

        resp = client.get("/api/notifications/pending", cookies=auth_cookies)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_excludes_sent_and_rejected(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        make_notification_draft(db, event, email_status="sent")
        make_notification_draft(db, event, email_status="rejected")

        resp = client.get("/api/notifications/pending", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_includes_student_and_event_info(self, client, db, auth_cookies):
        student = make_student(db, full_name="Jane Doe")
        email = make_email(db)
        event = make_interview_event(db, email, student=student, company="TechCorp")
        make_notification_draft(db, event)

        resp = client.get("/api/notifications/pending", cookies=auth_cookies)
        data = resp.json()
        assert data[0]["student_name"] == "Jane Doe"
        assert data[0]["company_name"] == "TechCorp"

    def test_requires_auth(self, client, db):
        resp = client.get("/api/notifications/pending")
        assert resp.status_code == 401


class TestGetSentNotifications:
    def test_empty(self, client, db, auth_cookies):
        resp = client.get("/api/notifications/sent", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_sent_only(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        make_notification_draft(db, event, email_status="sent")
        make_notification_draft(db, event, email_status="draft")  # excluded

        resp = client.get("/api/notifications/sent", cookies=auth_cookies)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["email_status"] == "sent"

    def test_requires_auth(self, client, db):
        resp = client.get("/api/notifications/sent")
        assert resp.status_code == 401


class TestGetNotificationDetail:
    def test_get_detail_success(self, client, db, auth_cookies):
        student = make_student(db)
        email = make_email(db, subject="Phone Screen at Acme")
        event = make_interview_event(db, email, student=student)
        draft = make_notification_draft(db, event, subject="Interview Alert")

        resp = client.get(f"/api/notifications/{draft.id}", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == draft.id
        assert data["email_subject"] == "Interview Alert"
        assert data["student_name"] == "John Doe"
        assert data["email_subject_original"] == "Phone Screen at Acme"

    def test_get_detail_not_found(self, client, db, auth_cookies):
        resp = client.get("/api/notifications/99999", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.get("/api/notifications/1")
        assert resp.status_code == 401


class TestApproveNotification:
    def test_approve_sends_email(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event, email_status="draft")

        with patch(_SEND_EMAIL, return_value={"status": "sent"}):
            resp = client.post(f"/api/notifications/{draft.id}/approve", cookies=auth_cookies)

        assert resp.status_code == 200
        data = resp.json()
        assert data["email_status"] == "sent"
        db.refresh(draft)
        assert draft.email_status == "sent"
        assert draft.sent_at is not None

    def test_approve_handles_send_failure(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event)

        with patch(_SEND_EMAIL, return_value={"status": "failed", "error": "SMTP error"}):
            resp = client.post(f"/api/notifications/{draft.id}/approve", cookies=auth_cookies)

        assert resp.status_code == 200
        data = resp.json()
        assert data["email_status"] == "failed"
        assert data["send_error"] == "SMTP error"

    def test_approve_already_sent_rejected(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event, email_status="sent")

        resp = client.post(f"/api/notifications/{draft.id}/approve", cookies=auth_cookies)
        assert resp.status_code == 400

    def test_approve_not_found(self, client, db, auth_cookies):
        resp = client.post("/api/notifications/99999/approve", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.post("/api/notifications/1/approve")
        assert resp.status_code == 401


class TestEditNotification:
    def test_edit_subject(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event, subject="Old Subject")

        resp = client.post(
            f"/api/notifications/{draft.id}/edit",
            json={"email_subject": "New Subject"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["email_subject"] == "New Subject"
        db.refresh(draft)
        assert draft.email_subject == "New Subject"

    def test_edit_and_send(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event)

        with patch(_SEND_EMAIL, return_value={"status": "sent"}):
            resp = client.post(
                f"/api/notifications/{draft.id}/edit",
                json={"email_subject": "Updated", "send_after_edit": True},
                cookies=auth_cookies,
            )

        assert resp.status_code == 200
        assert resp.json()["email_status"] == "sent"

    def test_edit_sent_notification_rejected(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event, email_status="sent")

        resp = client.post(
            f"/api/notifications/{draft.id}/edit",
            json={"email_subject": "Too Late"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 400

    def test_edit_not_found(self, client, db, auth_cookies):
        resp = client.post(
            "/api/notifications/99999/edit",
            json={"email_subject": "X"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.post("/api/notifications/1/edit", json={"email_subject": "X"})
        assert resp.status_code == 401


class TestRejectNotification:
    def test_reject_success(self, client, db, auth_cookies):
        email = make_email(db)
        event = make_interview_event(db, email)
        draft = make_notification_draft(db, event)

        resp = client.post(
            f"/api/notifications/{draft.id}/reject",
            json={"reason": "Wrong student"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_status"] == "rejected"
        assert data["reviewed_by"] == "testadmin"

        db.refresh(draft)
        assert draft.email_status == "rejected"

    def test_reject_not_found(self, client, db, auth_cookies):
        resp = client.post(
            "/api/notifications/99999/reject",
            json={"reason": "N/A"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.post("/api/notifications/1/reject", json={"reason": "X"})
        assert resp.status_code == 401


class TestStudentEndpoints:
    def test_list_students_empty(self, client, db, auth_cookies):
        resp = client.get("/api/notifications/students/list", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_students_active_only(self, client, db, auth_cookies):
        make_student(db, username="active1", full_name="Active Student")
        inactive = make_student(db, username="inactive1", full_name="Inactive Student")
        inactive.is_active = False
        db.commit()

        resp = client.get("/api/notifications/students/list?active_only=true", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "Active Student"

    def test_list_students_all(self, client, db, auth_cookies):
        make_student(db, username="active1")
        inactive = make_student(db, username="inactive1")
        inactive.is_active = False
        db.commit()

        resp = client.get("/api/notifications/students/list?active_only=false", cookies=auth_cookies)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_student_by_id(self, client, db, auth_cookies):
        student = make_student(db, full_name="Test Student", personal_email="test@example.com")

        resp = client.get(f"/api/notifications/students/{student.id}", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Test Student"
        assert data["personal_email"] == "test@example.com"

    def test_get_student_not_found(self, client, db, auth_cookies):
        resp = client.get("/api/notifications/students/99999", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.get("/api/notifications/students/list")
        assert resp.status_code == 401


class TestGetNotificationByEmail:
    def test_returns_notification_for_email(self, client, db, auth_cookies):
        student = make_student(db)
        email = make_email(db)
        event = make_interview_event(db, email, student=student)
        draft = make_notification_draft(db, event, subject="Interview Tomorrow")

        resp = client.get(f"/api/notifications/by-email/{email.id}", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_subject"] == "Interview Tomorrow"

    def test_returns_null_when_no_notification(self, client, db, auth_cookies):
        resp = client.get("/api/notifications/by-email/99999", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_requires_auth(self, client, db):
        resp = client.get("/api/notifications/by-email/1")
        assert resp.status_code == 401

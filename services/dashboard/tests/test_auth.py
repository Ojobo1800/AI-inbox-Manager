"""Tests for /api/auth/* endpoints."""

import uuid
from datetime import datetime, timedelta

from conftest import _TEST_PASSWORD, _TEST_HASH
from models import UserSession


class TestLogin:
    def test_login_success(self, client, db):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": _TEST_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert "session_token" in resp.cookies

    def test_login_wrong_password(self, client, db):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_login_empty_password(self, client, db):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": ""})
        assert resp.status_code == 401

    def test_login_missing_body(self, client, db):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 422  # Pydantic validation error


class TestLogout:
    def test_logout_success(self, client, db, auth_cookies):
        resp = client.post("/api/auth/logout", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logout successful"

    def test_logout_unauthenticated(self, client, db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestGetMe:
    def test_get_me_authenticated(self, client, db, auth_cookies):
        resp = client.get("/api/auth/me", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"

    def test_get_me_unauthenticated(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_expired_session(self, client, db):
        token = str(uuid.uuid4())
        expired_session = UserSession(
            session_token=token,
            username="testadmin",
            role="admin",
            created_at=datetime.utcnow() - timedelta(hours=48),
            expires_at=datetime.utcnow() - timedelta(hours=24),  # already expired
            last_activity=datetime.utcnow() - timedelta(hours=24),
        )
        db.add(expired_session)
        db.commit()

        resp = client.get("/api/auth/me", cookies={"session_token": token})
        assert resp.status_code == 401


class TestHealthCheck:
    def test_health_check(self, client, db):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

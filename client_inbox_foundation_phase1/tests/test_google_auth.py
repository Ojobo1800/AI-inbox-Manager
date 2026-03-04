from fastapi.testclient import TestClient

from app.main import app


def test_google_login_redirect_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.integrations.oauth_google.settings.google_oauth_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.integrations.oauth_google.settings.google_oauth_redirect_uri",
        "http://localhost:5173/auth/callback",
    )
    monkeypatch.setattr(
        "app.integrations.oauth_google.settings.google_oauth_scopes",
        "openid,email,profile",
    )

    client = TestClient(app)
    response = client.get("/auth/google/login?state=abc123", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert "accounts.google.com/o/oauth2/v2/auth" in location
    assert "client_id=test-client-id" in location
    assert "state=abc123" in location


def test_google_exchange_returns_profile(monkeypatch) -> None:
    async def fake_exchange_auth_code(code: str) -> dict:
        assert code == "auth-code-1"
        return {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "scope": "openid email profile",
            "token_type": "Bearer",
            "id_token": "id-token",
            "profile": {"email": "manager@example.com"},
        }

    monkeypatch.setattr("app.api.routes.auth.exchange_auth_code", fake_exchange_auth_code)

    client = TestClient(app)
    response = client.post("/auth/google/exchange", json={"code": "auth-code-1"})

    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["email"] == "manager@example.com"


def test_google_exchange_handles_failure(monkeypatch) -> None:
    async def failing_exchange_auth_code(_code: str) -> dict:
        raise ValueError("Token exchange failed")

    monkeypatch.setattr("app.api.routes.auth.exchange_auth_code", failing_exchange_auth_code)

    client = TestClient(app)
    response = client.post("/auth/google/exchange", json={"code": "bad-code"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Token exchange failed"

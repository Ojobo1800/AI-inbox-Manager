from typing import Any
from urllib.parse import urlencode

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.core.config import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _scopes() -> list[str]:
    return [scope.strip() for scope in settings.google_oauth_scopes.split(",") if scope.strip()]


def build_google_oauth_login_url(state: str | None = None) -> str:
    if not settings.google_oauth_client_id:
        raise ValueError("GOOGLE_OAUTH_CLIENT_ID is required")

    query = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_scopes()),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    if state:
        query["state"] = state

    return f"{AUTH_URL}?{urlencode(query)}"


async def exchange_auth_code(code: str) -> dict[str, Any]:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise ValueError("GOOGLE OAuth client credentials are required")

    payload = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(TOKEN_URL, data=payload)

    if response.status_code != 200:
        raise ValueError(f"Token exchange failed: {response.text}")

    token_data = response.json()
    id_token_jwt = token_data.get("id_token")

    profile: dict[str, Any] = {}
    if id_token_jwt:
        profile = id_token.verify_oauth2_token(
            id_token_jwt,
            Request(),
            settings.google_oauth_client_id,
        )

    return {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "scope": token_data.get("scope"),
        "token_type": token_data.get("token_type"),
        "id_token": id_token_jwt,
        "profile": {
            "sub": profile.get("sub"),
            "email": profile.get("email"),
            "email_verified": profile.get("email_verified"),
            "name": profile.get("name"),
            "picture": profile.get("picture"),
        },
    }

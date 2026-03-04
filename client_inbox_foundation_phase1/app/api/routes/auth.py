from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.integrations.oauth_google import build_google_oauth_login_url, exchange_auth_code

router = APIRouter(prefix="/auth/google", tags=["auth"])


class ExchangeCodeRequest(BaseModel):
    code: str


@router.get("/login")
def google_login(state: str | None = None) -> RedirectResponse:
    try:
        login_url = build_google_oauth_login_url(state=state)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RedirectResponse(url=login_url, status_code=302)


@router.post("/exchange")
async def google_exchange(request: ExchangeCodeRequest) -> dict:
    try:
        return await exchange_auth_code(request.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

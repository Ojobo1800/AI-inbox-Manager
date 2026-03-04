from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "inbox-foundation-phase1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

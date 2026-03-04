import logging

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import settings
from app.integrations.gmail import decode_pubsub_envelope
from app.integrations.sqlserver import upsert_gmail_checkpoint

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/gmail")
async def gmail_webhook(
    payload: dict,
    x_google_verification_token: str | None = Header(default=None),
) -> dict:
    if settings.google_pubsub_verification_token:
        if x_google_verification_token != settings.google_pubsub_verification_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification token",
            )

    try:
        decoded = decode_pubsub_envelope(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        upsert_gmail_checkpoint(
            email_address=decoded["emailAddress"],
            history_id=decoded["historyId"],
            pubsub_message_id=decoded.get("pubsubMessageId"),
            pubsub_publish_time=decoded.get("publishTime"),
        )
    except Exception as exc:
        logger.exception("Failed to persist Gmail checkpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist Gmail checkpoint",
        ) from exc

    logger.info("Received Gmail webhook", extra={"gmail_push": decoded})
    return {
        "accepted": True,
        "email_address": decoded["emailAddress"],
        "history_id": decoded["historyId"],
        "pubsub_message_id": decoded.get("pubsubMessageId"),
    }

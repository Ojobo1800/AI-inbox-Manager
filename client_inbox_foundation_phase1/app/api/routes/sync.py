from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.gmail import collect_incremental_unread_interview_messages
from app.integrations.interview_mapper import map_message_to_interview_record
from app.integrations.sheets import append_interview_record
from app.integrations.sqlserver import (
    get_gmail_checkpoint,
    upsert_gmail_checkpoint,
    upsert_interview_tracker_record,
    upsert_unread_intake_email,
)

router = APIRouter(prefix="/sync/gmail", tags=["sync"])


class IncrementalSyncRequest(BaseModel):
    email_address: str


@router.post("/incremental")
def run_incremental_sync(request: IncrementalSyncRequest) -> dict:
    checkpoint = get_gmail_checkpoint(request.email_address)
    if not checkpoint:
        raise HTTPException(
            status_code=404,
            detail="No checkpoint found for email. Trigger Gmail webhook first.",
        )

    try:
        result = collect_incremental_unread_interview_messages(str(checkpoint["history_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tracker_records = []
    for message in result["messages"]:
        upsert_unread_intake_email(request.email_address, message)

        record = map_message_to_interview_record(request.email_address, message)
        upsert_interview_tracker_record(record)
        append_interview_record(record)
        tracker_records.append(record)

    latest_history_id = str(result.get("latest_history_id", checkpoint["history_id"]))
    if latest_history_id != str(checkpoint["history_id"]):
        upsert_gmail_checkpoint(
            email_address=request.email_address,
            history_id=latest_history_id,
            pubsub_message_id=None,
            pubsub_publish_time=None,
        )

    return {
        "email_address": request.email_address,
        "start_history_id": str(checkpoint["history_id"]),
        "latest_history_id": latest_history_id,
        "processed_count": result.get("processed_count", 0),
        "interview_unread_count": result.get("interview_unread_count", 0),
        "stored_message_ids": [m.get("message_id") for m in result["messages"]],
        "tracker_record_keys": [r.get("record_key") for r in tracker_records],
    }

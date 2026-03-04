"""
Interview processing pipeline orchestrator.

Processes interview-classified emails through the full notification pipeline:
1. Sub-classify the interview type
2. Resolve which student the email is about
3. Fetch student info from Google Drive
4. Draft the notification (email + WhatsApp)
5. Auto-send or queue for review based on confidence
6. Log the interview event to the dashboard database

This script runs after process_inbox_auto.py in the processing chain.

Design principles:
- Orchestrates existing execution scripts
- Each step is independently testable
- Handles partial failures gracefully (continues with other emails)
- Returns structured summary for logging
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from execution.subclassify_interview import subclassify_interview, is_interview_related
from execution.resolve_student import resolve_student
from execution.fetch_student_info import fetch_student_info
from execution.draft_notification import draft_notification
from execution.send_notification import send_notification
from execution.log_interview import (
    upsert_student,
    log_interview_event,
    log_notification_draft,
    update_notification_status,
)

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Confidence thresholds for auto-send decisions
AUTO_SEND_THRESHOLD = 0.95
AUDIT_FLAG_THRESHOLD = 0.80
REVIEW_REQUIRED_THRESHOLD = 0.70


def process_single_interview(
    email_data: Dict[str, Any],
    email_db_id: int,
    db: Session,
    api_key: Optional[str] = None,
    drive_client=None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Process a single interview email through the full pipeline.

    Args:
        email_data: Email data dictionary with subject, body, headers, etc.
        email_db_id: Database ID of the email in the emails table
        db: SQLAlchemy database session
        api_key: OpenAI API key (defaults to env var)
        drive_client: Optional pre-configured GoogleDriveClient
        dry_run: If True, skip sending email (draft only)

    Returns:
        Processing result dictionary with:
            - status: "sent" | "queued" | "failed" | "skipped"
            - interview_event_id: int (if logged)
            - notification_draft_id: int (if created)
            - template_id: str (if template selected)
            - student_name: str (if resolved)
            - error: str (if failed)
            - steps_completed: list of step names
    """
    result = {
        "status": "failed",
        "interview_event_id": None,
        "notification_draft_id": None,
        "template_id": None,
        "student_name": None,
        "error": None,
        "steps_completed": [],
    }

    # Step 1: Sub-classify the interview
    try:
        classification = subclassify_interview(email_data, api_key=api_key)
        if not classification or not classification.get("interview_sub_type"):
            result["status"] = "skipped"
            result["error"] = "Sub-classification returned no result"
            return result
        result["steps_completed"].append("subclassify")
    except Exception as e:
        result["error"] = f"Sub-classification failed: {e}"
        logger.error(result["error"])
        return result

    # Step 2: Resolve student from email headers
    try:
        student_resolution = resolve_student(email_data)
        result["steps_completed"].append("resolve_student")
    except Exception as e:
        result["error"] = f"Student resolution failed: {e}"
        logger.error(result["error"])
        # Continue - we can still log the event without student info
        student_resolution = {"student_username": None, "student_gmail": None}

    # Step 3: Fetch student info from Google Drive
    student_info = {}
    student_db_id = None
    if student_resolution.get("student_username"):
        try:
            student_info_result = fetch_student_info(
                email_data, drive_client=drive_client
            )
            if student_info_result.get("status") in ("resolved", "partial"):
                student_info = {
                    "full_name": student_info_result.get("full_name"),
                    "personal_email": student_info_result.get("personal_email"),
                    "assigned_gmail": student_info_result.get("assigned_gmail"),
                    "phone_number": student_info_result.get("phone_number"),
                    "student_gmail": student_info_result.get("student_gmail"),
                }
                result["student_name"] = student_info.get("full_name")

                # Upsert student in DB
                student_record = upsert_student(
                    db,
                    username=student_resolution["student_username"],
                    full_name=student_info.get("full_name"),
                    personal_email=student_info.get("personal_email"),
                    assigned_gmail=student_info.get("assigned_gmail"),
                    phone_number=student_info.get("phone_number"),
                )
                student_db_id = student_record["id"]

            result["steps_completed"].append("fetch_student_info")
        except Exception as e:
            logger.error(f"Student info fetch failed: {e}")
            # Continue with what we have

    # Step 4: Log interview event to DB
    try:
        event_result = log_interview_event(
            db,
            email_db_id=email_db_id,
            classification=classification,
            student_id=student_db_id,
        )
        result["interview_event_id"] = event_result["id"]
        result["steps_completed"].append("log_event")
    except Exception as e:
        result["error"] = f"Event logging failed: {e}"
        logger.error(result["error"])
        return result

    # Step 5: Draft notification
    try:
        draft = draft_notification(
            classification=classification,
            student_info=student_info,
        )
        result["template_id"] = draft.get("template_id")
        result["steps_completed"].append("draft_notification")
    except Exception as e:
        result["error"] = f"Notification drafting failed: {e}"
        logger.error(result["error"])
        return result

    # Step 6: Determine auto-send eligibility
    confidence = classification.get("confidence", 0.0)
    has_all_fields = len(draft.get("missing_fields", [])) == 0
    has_recipient = bool(draft.get("recipient_email"))
    draft_ready = draft.get("draft_status") == "ready"

    auto_send = (
        confidence >= AUTO_SEND_THRESHOLD
        and has_all_fields
        and has_recipient
        and draft_ready
        and not dry_run
    )

    # Step 7: Log notification draft to DB
    try:
        draft_result = log_notification_draft(
            db,
            interview_event_id=event_result["id"],
            draft=draft,
            auto_send_eligible=auto_send,
        )
        result["notification_draft_id"] = draft_result["id"]
        result["steps_completed"].append("log_draft")
    except Exception as e:
        result["error"] = f"Draft logging failed: {e}"
        logger.error(result["error"])
        return result

    # Step 8: Send or queue
    if auto_send:
        try:
            send_result = send_notification(draft)
            if send_result["status"] == "sent":
                update_notification_status(
                    db,
                    notification_id=draft_result["id"],
                    email_status="sent",
                )
                result["status"] = "sent"
                result["steps_completed"].append("send")
                logger.info(
                    f"Auto-sent notification to {draft.get('recipient_email')}"
                )
            else:
                update_notification_status(
                    db,
                    notification_id=draft_result["id"],
                    email_status="failed",
                    send_error=send_result.get("error"),
                )
                result["status"] = "failed"
                result["error"] = send_result.get("error")
                logger.error(f"Send failed: {send_result.get('error')}")
        except Exception as e:
            result["error"] = f"Send failed: {e}"
            result["status"] = "failed"
            logger.error(result["error"])
    else:
        result["status"] = "queued"
        if dry_run:
            logger.info("Dry run - notification drafted but not sent")
        elif not has_recipient:
            logger.info("No recipient email - queued for review")
        elif not draft_ready:
            logger.info("Draft needs review - queued")
        else:
            logger.info(
                f"Confidence {confidence:.2f} below auto-send threshold "
                f"({AUTO_SEND_THRESHOLD}) - queued for review"
            )

    return result


def process_interview_batch(
    emails: List[Dict[str, Any]],
    db: Session,
    api_key: Optional[str] = None,
    drive_client=None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Process a batch of interview emails.

    Args:
        emails: List of email data dicts, each with 'email_data' and 'email_db_id'
        db: SQLAlchemy database session
        api_key: OpenAI API key
        drive_client: Optional GoogleDriveClient
        dry_run: If True, skip sending

    Returns:
        Batch summary with counts and per-email results
    """
    summary = {
        "total": len(emails),
        "sent": 0,
        "queued": 0,
        "failed": 0,
        "skipped": 0,
        "results": [],
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }

    for item in emails:
        email_data = item.get("email_data", {})
        email_db_id = item.get("email_db_id", 0)

        logger.info(
            f"Processing interview email: {email_data.get('subject', 'Unknown')}"
        )

        result = process_single_interview(
            email_data=email_data,
            email_db_id=email_db_id,
            db=db,
            api_key=api_key,
            drive_client=drive_client,
            dry_run=dry_run,
        )

        summary["results"].append(result)
        status = result["status"]
        if status in summary:
            summary[status] += 1

    summary["completed_at"] = datetime.utcnow().isoformat()

    logger.info(
        f"Interview processing complete: "
        f"{summary['sent']} sent, {summary['queued']} queued, "
        f"{summary['failed']} failed, {summary['skipped']} skipped"
    )

    return summary

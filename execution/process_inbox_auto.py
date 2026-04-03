"""
Automated inbox processing - Production script for scheduled execution.

This script is designed to run on a schedule (hourly/daily) and will:
1. Process ONLY unread (UNSEEN) emails to prevent re-processing
2. Keep genuine interview requests in inbox (unread for visibility)
3. Move job alerts and other emails to category folders
4. Delete spam emails
5. Sub-classify interview emails and create InterviewEvent records

IMPORTANT: This script NEVER processes read emails, preventing accidental
deletion or movement of important emails like interview requests.

Usage:
    python process_inbox_auto.py

Configuration:
    Set in .env file:
    - EMAIL_SERVER
    - EMAIL_PORT
    - EMAIL_ADDRESS
    - EMAIL_PASSWORD
    - OPENAI_API_KEY
"""

import json
import logging
import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables FIRST (before any module imports that may read env)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Set up file + console logging BEFORE importing other modules.
# fetch_emails.py calls logging.basicConfig() at import time; using force=True
# ensures our file handler is not silently discarded.
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,   # override any handlers set by imported modules
    handlers=[
        logging.FileHandler(log_dir / f"inbox_auto_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ],
)

# Import our execution modules
from fetch_emails import fetch_emails, delete_emails, move_emails, EmailConnectionError, EmailFetchError
from classify_email import classify_email

# Add project root so execution.* package imports work (e.g. draft_notification → execution.email_templates)
sys.path.insert(0, str(project_root))
# Add services path for dashboard database access
sys.path.insert(0, str(project_root / "services" / "dashboard" / "api"))

# Database and interview processing imports (lazy loaded)
_db_session = None
_db_engine = None


def get_db_session():
    """Get or create database session for interview logging."""
    global _db_session, _db_engine
    if _db_session is None:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                db_path = project_root / "services" / "dashboard" / "api" / "email_dashboard.db"
                db_url = f"sqlite:///{db_path}"
            _db_engine = create_engine(db_url, echo=False)
            SessionLocal = sessionmaker(bind=_db_engine)
            _db_session = SessionLocal()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Could not initialize database: {e}")
            return None
    return _db_session


def close_db_session():
    """Close database session."""
    global _db_session
    if _db_session:
        _db_session.close()
        _db_session = None


def import_email_to_db(email_data: Dict[str, Any], classification: Dict[str, Any], folder: str = "INBOX") -> Optional[int]:
    """
    Import an email to the dashboard database.

    Args:
        email_data: Email data from IMAP
        classification: Classification result
        folder: Current folder

    Returns:
        Database ID of the email, or None if import failed
    """
    db = get_db_session()
    if not db:
        return None

    try:
        from models import Email, Classification

        email_uid = str(email_data.get("email_id", ""))
        if not email_uid:
            return None

        # Check if email already exists
        existing = db.query(Email).filter(Email.email_id == email_uid).first()
        if existing:
            existing.current_folder = folder
            db.commit()
            return existing.id

        # Parse received date safely
        raw_date = email_data.get("date")
        if isinstance(raw_date, datetime):
            received_date = raw_date
        elif isinstance(raw_date, str):
            try:
                received_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                received_date = datetime.utcnow()
        else:
            received_date = datetime.utcnow()

        body = email_data.get("body", "") or ""

        new_email = Email(
            email_id=email_uid,
            subject=(email_data.get("subject", "No Subject") or "")[:500],
            from_address=(email_data.get("from", "Unknown") or "")[:255],
            received_date=received_date,
            body_preview=body[:500],
            full_body=body,
            current_folder=folder,
            is_read=False,
            fetch_timestamp=datetime.utcnow(),
        )
        db.add(new_email)
        db.flush()  # get ID without committing
        email_db_id = new_email.id

        # Create classification record using correct model field names
        extracted = classification.get("extracted_data") or {}
        new_classification = Classification(
            email_id=email_db_id,
            category=(classification.get("category", "Unknown") or "")[:100],
            confidence=float(classification.get("confidence", 0.0)),
            company_name=(extracted.get("company_name") or "")[:255] or None,
            position=(extracted.get("position_title") or "")[:255] or None,
            classification_timestamp=datetime.utcnow(),
            classifier_version="gpt-4o",
            raw_response=classification,
        )
        db.add(new_classification)
        db.commit()

        return email_db_id

    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to import email to database: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def process_interview_email(email_data: Dict[str, Any], email_db_id: int, classification: Dict[str, Any]) -> bool:
    """
    Process an interview email through the sub-classification pipeline.

    Creates an InterviewEvent record, resolves the student from config,
    upserts them into the students table, and creates a NotificationDraft
    so the dashboard can track and display the notification lifecycle.

    Args:
        email_data: Email data from IMAP
        email_db_id: Database ID of the email
        classification: Primary classification result

    Returns:
        True if successfully processed, False otherwise
    """
    db = get_db_session()
    if not db:
        return False

    try:
        from log_interview import log_interview_event, upsert_student, log_notification_draft

        _logger = logging.getLogger(__name__)

        # Map classify_email fields → InterviewEvent-ready dict
        _CATEGORY_TO_SUB_TYPE = {
            "Interview Request":         "interview_request",
            "Interview Schedule":        "interview_schedule",
            "Interview Reschedule":      "reschedule",
            "Interview Confirmation":    "confirmed",
            "Interview Cancelled":       "cancelled",
            "Phone Screen":              "phone_screen",
            "Final Interview Scheduled": "final_round",
            "Assessment":                "assessment",
        }
        _FORMAT_MAP = {
            "phone":     "phone",
            "video":     "video",
            "in-person": "in_person",
            "in_person": "in_person",
            "technical": "technical",
            "panel":     "panel",
        }

        category  = classification.get("category", "")
        extracted = classification.get("extracted_data") or {}
        sub_type  = _CATEGORY_TO_SUB_TYPE.get(category, "other")

        raw_fmt = (extracted.get("interview_type") or "").lower().strip()
        fmt     = _FORMAT_MAP.get(raw_fmt, raw_fmt or None)

        location     = extracted.get("interview_location") or ""
        meeting_link = location if any(
            k in location.lower() for k in ["http", "zoom", "meet", "teams"]
        ) else None

        sub_classification = {
            "interview_sub_type":      sub_type,
            "company_name":            extracted.get("company_name"),
            "position_title":          extracted.get("position_title"),
            "contact_name":            extracted.get("contact_name"),
            "contact_email":           extracted.get("contact_email"),
            "contact_phone":           None,
            "interview_date":          extracted.get("interview_date"),
            "interview_time":          extracted.get("interview_time"),
            "interview_timezone":      extracted.get("interview_timezone"),
            "interview_format":        fmt,
            "meeting_link_or_dial_in": meeting_link,
            "num_interviewers":        None,
            "is_job_machine":          False,
            "is_next_round":           False,
            "confidence":              float(classification.get("confidence", 0.0)),
        }

        # ── Resolve student from config/students.py ──────────────────────────
        student_id = None
        student_config = None
        try:
            from notify_student import _get_student_info, _build_student_info_for_draft, _build_classification_for_draft

            student_config = _get_student_info(classification, email_data)
            if student_config:
                # Derive a stable username: "First Last" → "first.last"
                username = student_config["name"].lower().replace(" ", ".")
                student_db = upsert_student(
                    db=db,
                    username=username,
                    full_name=student_config["name"],
                    personal_email=student_config.get("personal_email"),
                    phone_number=student_config.get("phone"),
                )
                student_id = student_db["id"]
                _logger.info(
                    f"Resolved student: {student_config['name']} (DB id={student_id})"
                )
        except Exception as e:
            _logger.warning(f"Student resolution skipped: {e}")

        # ── Create InterviewEvent ─────────────────────────────────────────────
        event_result = log_interview_event(
            db=db,
            email_db_id=email_db_id,
            classification=sub_classification,
            student_id=student_id,
        )

        _logger.info(
            f"Created InterviewEvent {event_result['id']}: "
            f"{sub_type} at {extracted.get('company_name')}"
        )

        # ── Create NotificationDraft for dashboard visibility ─────────────────
        if student_id and student_config:
            try:
                from draft_notification import draft_notification
                from notify_student import _build_student_info_for_draft, _build_classification_for_draft

                student_info_for_draft = _build_student_info_for_draft(student_config)
                draft_cls = _build_classification_for_draft(classification, email_data)
                assistant_name = student_config.get("assigned_to")

                draft = draft_notification(
                    classification=draft_cls,
                    student_info=student_info_for_draft,
                    assistant_name=assistant_name,
                )

                auto_send = draft["draft_status"] == "ready"
                log_notification_draft(
                    db=db,
                    interview_event_id=event_result["id"],
                    draft=draft,
                    auto_send_eligible=auto_send,
                )
                _logger.info(
                    f"Created NotificationDraft for {student_config['name']} "
                    f"(auto_send={auto_send}, status={draft['draft_status']})"
                )
            except Exception as e:
                _logger.warning(f"NotificationDraft creation skipped: {e}")

        return True

    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to process interview email: {e}")
        return False

logger = logging.getLogger(__name__)

# ── Rate limit + Cost guardrails ─────────────────────────────────────────────
# All values are configurable via environment variables so they can be tightened
# without code changes.

# Hard ceiling on emails per run regardless of --limit flag.
# Prevents runaway cost if a backlog builds up.
_MAX_EMAILS_PER_RUN: int = int(os.getenv("MAX_EMAILS_PER_RUN", "100"))

# Maximum estimated USD cost for GPT calls in a single run.
# If the post-classification actual cost exceeds this, Gmail mutations are
# skipped (move/delete) to prevent compounding an already expensive run.
_MAX_COST_PER_RUN_USD: float = float(os.getenv("MAX_COST_PER_RUN_USD", "5.0"))

# gpt-4o pricing (USD per million tokens) — update if OpenAI changes pricing.
_GPT4O_INPUT_PRICE_PER_M: float = 2.50
_GPT4O_OUTPUT_PRICE_PER_M: float = 10.00

# Conservative per-email cost estimate used for the pre-run budget check.
# Based on: ~3500 input tokens (prompt + email) + ~650 output tokens per call.
_EST_COST_PER_EMAIL_USD: float = (
    (3500 / 1_000_000) * _GPT4O_INPUT_PRICE_PER_M
    + (650 / 1_000_000) * _GPT4O_OUTPUT_PRICE_PER_M
)  # ≈ $0.015 per email


def _compute_cost(input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost from actual token counts."""
    return (
        (input_tokens / 1_000_000) * _GPT4O_INPUT_PRICE_PER_M
        + (output_tokens / 1_000_000) * _GPT4O_OUTPUT_PRICE_PER_M
    )


# CRITICAL SAFETY FEATURE: Whitelist of companies that have sent genuine interview requests
# NEVER move or delete emails from these companies, regardless of AI classification
KNOWN_INTERVIEW_COMPANIES = {
    "ask consulting",
    "united global technologies",
    "excelon solutions",
    "wesco",
    "vdart",
    "refocus",
    "empiric"
}


def is_from_known_company(email_data: Dict[str, Any], classification: Dict[str, Any]) -> bool:
    """
    SAFETY CHECK: Check if email is from a known interview company.

    This prevents accidental deletion/moving of genuine interview requests
    even if the AI misclassifies them.

    Args:
        email_data: Email data dictionary
        classification: Classification result

    Returns:
        True if from a known interview company
    """
    # Check classification company name
    company = classification.get("extracted_data", {}).get("company_name", "")
    if company and any(known in company.lower() for known in KNOWN_INTERVIEW_COMPANIES):
        logger.info(f"SAFETY CHECK: Email from known company '{company}'")
        return True

    # Check email from address
    from_addr = email_data.get("from", "").lower()
    if any(known in from_addr for known in KNOWN_INTERVIEW_COMPANIES):
        logger.info(f"SAFETY CHECK: Email from known sender '{from_addr}'")
        return True

    # Check subject line
    subject = email_data.get("subject", "").lower()
    if any(known in subject for known in KNOWN_INTERVIEW_COMPANIES):
        logger.info(f"SAFETY CHECK: Email subject mentions known company")
        return True

    return False


def process_unread_emails(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Process only unread emails from inbox.

    Args:
        limit: Maximum number of emails to process (None for unlimited)

    Returns:
        Processing statistics
    """
    # Load configuration
    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([server, email_address, password]):
        raise ValueError("Missing email configuration in .env file")

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env file")

    # Track processing start time for duration_seconds
    start_time = datetime.now()

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"tmp/auto_process_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("AUTOMATED INBOX PROCESSING")
    logger.info("=" * 60)
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Account: {email_address}")
    logger.info(f"Processing: UNSEEN emails only")
    logger.info("")

    try:
        # Fetch ONLY unread emails
        logger.info("Fetching unread emails...")
        emails = fetch_emails(
            server=server,
            port=port,
            email_address=email_address,
            password=password,
            folder="INBOX",
            criteria="UNSEEN",  # CRITICAL: Only unread emails
            limit=limit or _MAX_EMAILS_PER_RUN,  # Fetch only what we'll process
            mark_as_read=False  # Never mark interview requests as read
        )

        if not emails:
            logger.info("No unread emails found")
            return {
                "timestamp": timestamp,
                "total_emails": 0,
                "interview_requests": 0,
                "organized": 0,
                "spam_deleted": 0
            }

        # Apply --limit flag first (from caller / Task Scheduler config)
        total_found = len(emails)
        if limit and len(emails) > limit:
            logger.info(f"Found {total_found} unread emails, limiting to {limit} (--limit flag)")
            emails = emails[:limit]
        else:
            logger.info(f"Found {len(emails)} unread emails")

        # Hard safety ceiling — enforced regardless of --limit
        if len(emails) > _MAX_EMAILS_PER_RUN:
            logger.warning(
                f"Email count ({len(emails)}) exceeds MAX_EMAILS_PER_RUN={_MAX_EMAILS_PER_RUN} "
                f"— truncating to prevent runaway GPT cost"
            )
            emails = emails[:_MAX_EMAILS_PER_RUN]

        # Pre-run budget estimate: abort BEFORE any API calls if projected cost
        # already exceeds the configured ceiling.
        estimated_cost = len(emails) * _EST_COST_PER_EMAIL_USD
        logger.info(
            f"Pre-run budget estimate: {len(emails)} emails × "
            f"~${_EST_COST_PER_EMAIL_USD:.4f}/email = ~${estimated_cost:.3f} "
            f"(limit: ${_MAX_COST_PER_RUN_USD:.2f})"
        )
        if estimated_cost > _MAX_COST_PER_RUN_USD:
            logger.error(
                f"COST GUARDRAIL: estimated ${estimated_cost:.2f} exceeds "
                f"MAX_COST_PER_RUN_USD=${_MAX_COST_PER_RUN_USD} — aborting run"
            )
            return {
                "timestamp": timestamp,
                "total_emails": 0,
                "interview_requests": 0,
                "organized": 0,
                "spam_deleted": 0,
                "aborted_reason": f"cost_guardrail: estimated ${estimated_cost:.2f} > limit ${_MAX_COST_PER_RUN_USD}",
            }

        # Process emails
        stats = {
            "timestamp": timestamp,
            "total_emails": len(emails),
            "interview_requests": 0,
            "organized": 0,
            "spam_deleted": 0,
            "categories": {}
        }

        interview_requests = []
        spam_email_ids = []
        email_moves = {}

        # Category to server folder mapping
        category_to_folder = {
            "Job Alert": "Job Alerts",  # Note: Plural on server
            "Application Notification": "Application Notification",
            "Interview Confirmation": "Interview Confirmation",
            "Interview Schedule": "Interview Scheduling",
            "Interview Reschedule": "Interview Rescheduled",
            "Interview Cancelled": "Interview Cancelled",
            "Final Interview Scheduled": "Final Interview Scheduled",
            "Rejection": "Rejection",
            "More Information Request": "More Information Request",
            "Offer": "Offer",
            "Background Check": "Background Check",
            "Assessment": "Assessment",
            "Phone Screen": "Phone Screen (HR or Recruiter)"
        }

        logger.info("")
        logger.info(f"Classifying {len(emails)} emails in parallel (8 workers)...")
        logger.info("")

        # ── Step 1: Classify all emails concurrently (OpenAI API calls) ──────
        def _classify_one(args: Tuple[int, Dict]) -> Tuple[int, Dict, Optional[Dict], Dict]:
            """Classify a single email.

            Returns (idx, email_data, classification|None, gpt_usage).
            gpt_usage = {"input_tokens": int, "output_tokens": int}
            """
            idx, email_data = args
            _zero_usage: Dict = {"input_tokens": 0, "output_tokens": 0}
            try:
                classification = classify_email(email_data, validate_only=False)
                # Pop internal usage metadata before passing classification downstream
                usage = classification.pop("_gpt_usage", _zero_usage)
                return (idx, email_data, classification, usage)
            except Exception as exc:
                logger.error(f"Classification failed for email {idx}: {exc}")
                return (idx, email_data, None, _zero_usage)

        classified: List[Tuple[int, Dict, Optional[Dict], Dict]] = []
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {
                pool.submit(_classify_one, (idx, email_data)): idx
                for idx, email_data in enumerate(emails, 1)
            }
            for future in as_completed(futures):
                classified.append(future.result())

        # Sort back into original order so logs are readable
        classified.sort(key=lambda x: x[0])

        # ── Cost accounting (post-classification) ─────────────────────────────
        total_input_tokens = sum(r[3]["input_tokens"] for r in classified)
        total_output_tokens = sum(r[3]["output_tokens"] for r in classified)
        actual_cost = _compute_cost(total_input_tokens, total_output_tokens)
        successful_calls = sum(1 for r in classified if r[2] is not None)

        logger.info(
            f"GPT usage: {successful_calls} calls | "
            f"{total_input_tokens:,} input tokens | "
            f"{total_output_tokens:,} output tokens | "
            f"estimated cost: ${actual_cost:.4f}"
        )

        # If actual cost exceeds limit, skip Gmail mutations (already paid for
        # the API calls — but don't compound with potentially wrong moves/deletes)
        cost_guardrail_triggered = actual_cost > _MAX_COST_PER_RUN_USD
        if cost_guardrail_triggered:
            logger.error(
                f"COST GUARDRAIL: actual cost ${actual_cost:.4f} exceeds "
                f"MAX_COST_PER_RUN_USD=${_MAX_COST_PER_RUN_USD} — "
                f"skipping Gmail mutations (emails classified but NOT moved/deleted)"
            )

        # ── Step 2: Apply actions sequentially (IMAP + DB) ───────────────────
        logger.info("Applying actions...")
        if cost_guardrail_triggered:
            logger.warning("Cost guardrail active — DB writes proceed, Gmail moves/deletes are SKIPPED")
        logger.info("")

        # Tracks final folder per email for SharePoint audit log
        _sp_folder_map: Dict[str, str] = {}

        for idx, email_data, classification, _usage in classified:
            email_subject = email_data.get("subject", "No Subject")[:60]

            if classification is None:
                logger.error(f"[{idx}/{len(emails)}] Skipped (classification error) - {email_subject}")
                continue

            try:
                category = classification.get("category")
                confidence = classification.get("confidence", 0)

                # CRITICAL SAFETY CHECK: Never move/delete emails from known interview companies
                from_known_company = is_from_known_company(email_data, classification)

                # Check if genuine interview request OR from known company (safety check)
                if is_genuine_interview_request(classification) or from_known_company:
                    # KEEP IN INBOX - Do not touch
                    stats["interview_requests"] += 1
                    stats["categories"][category] = stats["categories"].get(category, 0) + 1
                    company = classification["extracted_data"].get("company_name")

                    interview_requests.append({
                        "subject": email_subject,
                        "company": company,
                        "confidence": confidence,
                        "timestamp": datetime.now().isoformat(),
                        "safety_protected": from_known_company
                    })

                    if from_known_company:
                        logger.info(f"[{idx}/{len(emails)}] ** SAFETY PROTECTED ** - {email_subject}")
                        logger.info(f"              Company: {company}")
                        logger.info(f"              Category: {category} (confidence: {confidence:.0%})")
                        logger.info(f"              [KEPT IN INBOX - KNOWN INTERVIEW COMPANY]")
                    else:
                        logger.info(f"[{idx}/{len(emails)}] ** INTERVIEW REQUEST ** - {email_subject}")
                        logger.info(f"              Company: {company}")
                        logger.info(f"              [KEPT IN INBOX - NEEDS REVIEW]")

                    # Track folder for SharePoint audit log
                    _sp_folder_map[str(email_data.get("email_id", ""))] = "INBOX"

                    # Import email to database and process through interview pipeline
                    try:
                        email_db_id = import_email_to_db(email_data, classification, "INBOX")
                        if email_db_id:
                            if process_interview_email(email_data, email_db_id, classification):
                                logger.info(f"              [INTERVIEW EVENT CREATED]")
                            else:
                                logger.warning(f"              [INTERVIEW PROCESSING FAILED]")
                    except Exception as e:
                        logger.error(f"              [DB IMPORT FAILED: {e}]")

                elif category == "Other":
                    # SPAM - Delete
                    stats["spam_deleted"] += 1
                    spam_email_ids.append(email_data.get("email_id"))
                    _sp_folder_map[str(email_data.get("email_id", ""))] = "Deleted"
                    logger.info(f"[{idx}/{len(emails)}] [SPAM] - {email_subject}")

                else:
                    # OTHER CATEGORIES - Organize
                    stats["organized"] += 1
                    stats["categories"][category] = stats["categories"].get(category, 0) + 1

                    # Track for moving
                    server_folder = category_to_folder.get(category)
                    if server_folder:
                        email_moves[email_data.get("email_id")] = server_folder

                    # Track folder for SharePoint audit log
                    _sp_folder_map[str(email_data.get("email_id", ""))] = server_folder or "Organized"

                    logger.info(f"[{idx}/{len(emails)}] [{category}] - {email_subject}")

                    # Save to database for audit trail
                    try:
                        import_email_to_db(email_data, classification, server_folder or "Organized")
                    except Exception as _e:
                        logger.error(f"              [DB import failed: {_e}]")

            except Exception as e:
                logger.error(f"Failed to apply action for email {idx}: {e}")

        # Move organized emails
        if email_moves and not cost_guardrail_triggered:
            logger.info("")
            logger.info(f"Moving {len(email_moves)} emails to category folders...")
            try:
                moved_count = move_emails(
                    server=server,
                    port=port,
                    email_address=email_address,
                    password=password,
                    email_moves=email_moves
                )
                logger.info(f"Successfully moved {moved_count} emails")
            except Exception as e:
                logger.error(f"Failed to move emails: {e}")
        elif email_moves and cost_guardrail_triggered:
            logger.warning(f"Cost guardrail: skipped moving {len(email_moves)} emails")

        # Delete spam
        if spam_email_ids and not cost_guardrail_triggered:
            logger.info("")
            logger.info(f"Deleting {len(spam_email_ids)} spam emails...")
            try:
                deleted_count = delete_emails(
                    server=server,
                    port=port,
                    email_address=email_address,
                    password=password,
                    email_ids=spam_email_ids
                )
                logger.info(f"Successfully deleted {deleted_count} spam emails")
            except Exception as e:
                logger.error(f"Failed to delete spam: {e}")
        elif spam_email_ids and cost_guardrail_triggered:
            logger.warning(f"Cost guardrail: skipped deleting {len(spam_email_ids)} spam emails")

        # ── Google Sheets audit log ───────────────────────────────────────────
        # Non-blocking: appends all classified emails to a Google Sheet for
        # reference tracking. Silently skipped if not configured.
        try:
            from log_to_google_sheets import log_batch_to_sheets, is_configured as _gs_configured
            if _gs_configured():
                logger.info("Logging classified emails to Google Sheets...")
                gs_result = log_batch_to_sheets(classified, _sp_folder_map)
                logger.info(
                    f"Google Sheets: {gs_result['logged']} rows appended, "
                    f"{gs_result.get('failed', 0)} failed"
                )
                stats["google_sheets"] = gs_result
            else:
                logger.debug("Google Sheets not configured — skipping audit log")
        except Exception as _gs_err:
            logger.warning(f"Google Sheets batch logging failed (non-fatal): {_gs_err}")

        # Calculate and record duration
        duration_seconds = (datetime.now() - start_time).total_seconds()
        stats["duration_seconds"] = duration_seconds

        # Record GPT usage metrics
        stats["gpt_usage"] = {
            "calls": successful_calls,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "estimated_cost_usd": round(actual_cost, 6),
            "cost_guardrail_triggered": cost_guardrail_triggered,
        }

        # Save summary
        summary = {
            "processing_timestamp": datetime.utcnow().isoformat() + "Z",
            "duration_seconds": duration_seconds,
            "statistics": stats,
            "interview_requests": interview_requests
        }

        summary_file = output_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Processed: {stats['total_emails']}")
        logger.info(f"Interview Requests (kept in inbox): {stats['interview_requests']}")
        logger.info(f"Organized to folders: {stats['organized']}")
        logger.info(f"Spam Deleted: {stats['spam_deleted']}")

        if interview_requests:
            logger.info("")
            logger.info("INTERVIEW REQUESTS IN INBOX:")
            for ir in interview_requests:
                logger.info(f"  - {ir['company']}: {ir['subject']}")

        logger.info("")
        logger.info(f"Summary saved to: {summary_file}")
        logger.info("=" * 60)

        # Log this run to the dashboard ProcessRun table
        _log_process_run(stats, summary_file)

        return stats

    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        raise

    finally:
        # Clean up database session
        close_db_session()


def _log_process_run(stats: Dict[str, Any], summary_file) -> None:
    """
    Write a ProcessRun record to the dashboard database so the UI shows
    the latest run stats and the countdown timer has a reference point.
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Use DATABASE_URL env var if set (cloud deployment), else fall back to local SQLite
        dashboard_db_url = os.getenv("DATABASE_URL")
        if not dashboard_db_url:
            db_path = project_root / "services" / "dashboard" / "api" / "email_dashboard.db"
            if not db_path.exists():
                logger.warning("Dashboard database not found — skipping ProcessRun log")
                return
            dashboard_db_url = f"sqlite:///{db_path}"

        engine = create_engine(dashboard_db_url, echo=False)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            from models import ProcessRun

            # Parse timestamp from summary stats
            ts_str = stats.get("timestamp", "")
            try:
                run_timestamp = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            except ValueError:
                run_timestamp = datetime.utcnow()

            # Avoid duplicate entries
            existing = db.query(ProcessRun).filter(
                ProcessRun.run_timestamp == run_timestamp
            ).first()

            if existing:
                logger.debug("ProcessRun record already exists for this run")
                return

            gpt_usage = stats.get("gpt_usage") or {}
            process_run = ProcessRun(
                run_timestamp=run_timestamp,
                total_emails=stats.get("total_emails", 0),
                interview_requests=stats.get("interview_requests", 0),
                organized=stats.get("organized", 0),
                spam_deleted=stats.get("spam_deleted", 0),
                categories_breakdown=stats.get("categories", {}),
                duration_seconds=stats.get("duration_seconds", 0),
                gpt_cost_usd=gpt_usage.get("estimated_cost_usd", 0.0),
                status="success",
            )
            db.add(process_run)
            db.commit()
            logger.info(f"Dashboard ProcessRun record created (id={process_run.id})")
        except Exception as e:
            db.rollback()
            logger.warning(f"Could not write ProcessRun to dashboard DB: {e}")
        finally:
            db.close()
            engine.dispose()

    except Exception as e:
        logger.warning(f"_log_process_run failed: {e}")


def is_genuine_interview_request(classification: Dict[str, Any]) -> bool:
    """
    Determine if this is a REAL interview request (not a job alert).

    Based on the golden rule:
    "Interview Request = Initial outreach requesting an interview or availability,
    NO TIME CONFIRMED YET. They want to talk, but nothing is scheduled yet."

    Args:
        classification: Classification result

    Returns:
        True if genuine interview request that needs immediate attention
    """
    category = classification.get("category")

    # Must be categorized as Interview Request
    if category != "Interview Request":
        return False

    # Check confidence - must be high confidence (>=80%)
    confidence = classification.get("confidence", 0)
    if confidence < 0.80:
        return False

    # Check edge case - not spam or automated
    edge_case = classification.get("edge_case", {})
    if edge_case.get("is_edge_case"):
        edge_type = edge_case.get("type")
        if edge_type in ["spam", "unclear", "multi-intent"]:
            return False

    # Check extracted data - must have real company (not job board aggregator)
    extracted = classification.get("extracted_data", {})
    company = extracted.get("company_name")
    if not company:
        return False

    # Reject if from job board aggregators
    company_lower = company.lower()
    job_board_indicators = [
        "job board", "indeed", "linkedin", "ziprecruiter", "glassdoor",
        "monster", "careerbuilder", "dice", "job alert", "job posting"
    ]
    if any(indicator in company_lower for indicator in job_board_indicators):
        return False

    # All checks passed - this is a genuine interview request
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process unread emails from inbox with AI classification"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of emails to process (default: process all)"
    )
    parser.add_argument(
        "--triggered-by",
        default="scheduled",
        help="Label for who triggered this run (default: scheduled)"
    )
    args = parser.parse_args()

    # ── Alerting (non-blocking — failure here must never crash the run) ────────
    try:
        from alert import send_failure_alert, is_configured as _alert_configured
        _alerting_enabled = _alert_configured()
    except Exception:
        send_failure_alert = None  # type: ignore[assignment]
        _alerting_enabled = False

    # ── Run lock protection ───────────────────────────────────────────────────
    # Prevents concurrent execution: double Gmail mutations, GPT cost spikes,
    # race conditions outside the DB.
    from run_lock import acquire_lock, release_lock
    if not acquire_lock(triggered_by=args.triggered_by):
        logger.warning("Another processing run is already active — exiting.")
        sys.exit(2)  # Exit 2 = already running (not an error for Task Scheduler)

    try:
        stats = process_unread_emails(limit=args.limit)

        # ── Alert: pre-run cost guardrail abort ───────────────────────────────
        aborted = stats.get("aborted_reason", "")
        if aborted and send_failure_alert:
            send_failure_alert(
                "Run aborted — cost guardrail",
                f"The email processing run was aborted BEFORE any GPT calls:\n\n"
                f"  Reason: {aborted}\n\n"
                f"Action: Increase MAX_COST_PER_RUN_USD or reduce email volume in .env",
            )

        # ── Alert: post-classification cost guardrail ─────────────────────────
        gpt = stats.get("gpt_usage", {})
        if gpt.get("cost_guardrail_triggered") and send_failure_alert:
            actual = gpt.get("estimated_cost_usd", 0.0)
            send_failure_alert(
                "Cost guardrail triggered — Gmail moves SKIPPED",
                f"Emails were classified by GPT but NOT moved or deleted because\n"
                f"the actual cost exceeded the per-run limit.\n\n"
                f"  Actual cost : ${actual:.4f}\n"
                f"  Limit       : ${_MAX_COST_PER_RUN_USD}\n"
                f"  Emails seen : {stats.get('total_emails', '?')}\n\n"
                f"Action: Check logs, then increase MAX_COST_PER_RUN_USD in .env if needed.\n"
                f"  The emails remain unread in Gmail — next run will retry them.",
            )

        if stats["interview_requests"] > 0:
            logger.info(f"ACTION REQUIRED: {stats['interview_requests']} interview request(s) in inbox.")
        sys.exit(0)  # Always exit 0 so Task Scheduler reports success

    except Exception as e:
        import traceback as _tb
        logger.error(f"Fatal error: {e}\n{_tb.format_exc()}")
        if send_failure_alert:
            send_failure_alert(
                f"FATAL ERROR: {type(e).__name__}",
                f"The email processing script crashed with an unhandled error.\n\n"
                f"  Error      : {e}\n"
                f"  Triggered by: {args.triggered_by}\n\n"
                f"The run was aborted. Emails in Gmail are unchanged.\n"
                f"Check logs/inbox_auto_*.log for the full traceback.",
                exc=e,
            )
        sys.exit(1)  # Error

    finally:
        release_lock()


if __name__ == "__main__":
    main()

"""
Smart inbox processing with Interview Request detection and SQL logging.

This script:
1. Detects REAL interview requests (personalized, asking to schedule)
2. Leaves interview requests in inbox for manual processing
3. Alerts about interview requests (console + future WhatsApp)
4. Logs interview requests to SQL Server
5. Deletes spam
6. Organizes other emails into category folders
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Import our execution modules
from fetch_emails import fetch_emails, delete_emails, move_emails, EmailConnectionError, EmailFetchError
from classify_email import classify_email

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def safe_print_subject(subject: str) -> str:
    """
    Sanitize email subject for safe console printing.

    Removes or replaces characters that can't be encoded in Windows console.

    Args:
        subject: Email subject string

    Returns:
        Sanitized subject safe for printing
    """
    try:
        # Try to encode with ascii, replacing problematic characters
        return subject.encode('ascii', 'replace').decode('ascii')
    except Exception:
        return subject[:50] + "..."


def create_category_folders(base_dir: Path) -> Dict[str, Path]:
    """Create folders for organizing emails."""
    # Categories match classification output (with spaces)
    categories = [
        "Interview Schedule",
        "Interview Confirmation",
        "Interview Reschedule",
        "Interview Cancelled",
        "Final Interview Scheduled",
        "Rejection",
        "Job Alert",
        "Application Notification",
        "More Information Request",
        "Offer",
        "Background Check",
        "Assessment",
        "Phone Screen",
        "Other"
    ]

    category_folders = {}
    for category in categories:
        # Create folder name with underscores
        folder_name = category.replace(" ", "_")
        folder_path = base_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        # Key uses original category name (with spaces) to match classification output
        category_folders[category] = folder_path

    # Special folder for Interview Requests (for logging/tracking only, emails stay in inbox)
    ir_folder = base_dir / "Interview_Requests_Log"
    ir_folder.mkdir(parents=True, exist_ok=True)
    category_folders["Interview Request"] = ir_folder

    return category_folders


def is_genuine_interview_request(classification: Dict[str, Any]) -> bool:
    """
    Determine if this is a REAL interview request (not a job alert).

    Based on the golden rule:
    "Interview Request = Initial outreach requesting an interview or availability,
    NO TIME CONFIRMED YET. They want to talk, but nothing is scheduled yet."

    Genuine interview requests must be:
    - Category "Interview Request" (not "Job Alert")
    - Personal outreach from real company/recruiter
    - Asking for availability or to schedule
    - NOT automated job board notifications
    - NOT spam

    Args:
        classification: Classification result

    Returns:
        True if genuine interview request that needs immediate attention
    """
    category = classification.get("category")

    # Must be categorized as Interview Request
    if category != "Interview Request":
        return False

    # Must NOT be a Job Alert (critical distinction)
    if category == "Job Alert":
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


def log_interview_request(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    log_folder: Path
) -> None:
    """
    Log interview request for tracking and future SQL insertion.

    Args:
        email_data: Original email data
        classification: Classification result
        log_folder: Folder to save log
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    email_id = email_data.get("email_id", timestamp)

    log_entry = {
        "logged_at": datetime.utcnow().isoformat() + "Z",
        "email_id": email_id,
        "email": email_data,
        "classification": classification,
        "status": "PENDING_MANUAL_REVIEW",
        "needs_alert": True,
        "needs_sql_insert": True
    }

    log_file = log_folder / f"IR_{timestamp}_{email_id}.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)

    logger.info(f"Interview request logged: {log_file}")


def save_to_category_folder(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    category_folders: Dict[str, Path],
    email_index: int
) -> Path:
    """Save email to appropriate category folder."""
    category = classification.get("category", "Other")
    folder = category_folders.get(category, category_folders["Other"])

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    email_id = email_data.get("email_id", email_index)
    filename = f"{timestamp}_{email_id}.json"

    filepath = folder / filename

    combined = {
        "email": email_data,
        "classification": classification,
        "organized_at": datetime.utcnow().isoformat() + "Z"
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    return filepath


def process_inbox_smart(
    emails: List[Dict[str, Any]],
    output_dir: Path,
    validate_only: bool = False,
    delete_spam: bool = True,
    server: Optional[str] = None,
    port: Optional[int] = None,
    email_address: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Smart inbox processing with interview request detection.

    Args:
        emails: List of email dictionaries
        output_dir: Base directory for organized results
        validate_only: If True, skip API call
        delete_spam: If True, delete spam emails from server
        server: IMAP server (required if delete_spam=True)
        port: IMAP port (required if delete_spam=True)
        email_address: Email address (required if delete_spam=True)
        password: Email password (required if delete_spam=True)

    Returns:
        Summary statistics dictionary
    """
    category_folders = create_category_folders(output_dir)

    stats = {
        "total_emails": len(emails),
        "interview_requests_detected": 0,
        "spam_deleted": 0,
        "organized": 0,
        "failed": 0,
        "categories": {}
    }

    interview_requests = []
    spam_email_ids = []  # Track email IDs to delete
    email_moves = {}  # Track email IDs to move: email_id -> folder_name

    # Map categories to server folder names
    category_to_folder = {
        "Job Alert": "Job Alert",
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

    print("\n" + "="*60)
    print("PROCESSING EMAILS")
    print("="*60)

    for idx, email_data in enumerate(emails, 1):
        email_subject = email_data.get("subject", "No Subject")[:60]

        try:
            # Classify
            classification = classify_email(email_data, validate_only=validate_only)
            category = classification.get("category")
            confidence = classification.get("confidence", 0)

            # Check if genuine interview request
            if is_genuine_interview_request(classification):
                # INTERVIEW REQUEST - Keep in inbox, log, alert
                stats["interview_requests_detected"] += 1

                log_interview_request(
                    email_data,
                    classification,
                    category_folders["Interview Request"]
                )

                interview_requests.append({
                    "subject": email_subject,
                    "company": classification["extracted_data"].get("company_name"),
                    "confidence": confidence
                })

                print(f"[{idx}/{len(emails)}] ** INTERVIEW REQUEST ** - {safe_print_subject(email_subject)}")
                print(f"              Company: {classification['extracted_data'].get('company_name')}")
                print(f"              [KEPT IN INBOX - NEEDS MANUAL REVIEW]")

            elif category == "Other":
                # SPAM - Mark for deletion
                stats["spam_deleted"] += 1
                spam_email_ids.append(email_data.get("email_id"))
                print(f"[{idx}/{len(emails)}] [SPAM DELETED] - {safe_print_subject(email_subject)}")

            else:
                # OTHER CATEGORIES - Organize into folders
                saved_path = save_to_category_folder(
                    email_data,
                    classification,
                    category_folders,
                    idx
                )

                stats["organized"] += 1
                stats["categories"][category] = stats["categories"].get(category, 0) + 1

                # Track for moving on server
                server_folder = category_to_folder.get(category)
                if server_folder:
                    email_moves[email_data.get("email_id")] = server_folder

                folder_name = saved_path.parent.name
                print(f"[{idx}/{len(emails)}] [{category}] -> {folder_name}/")

        except Exception as e:
            logger.error(f"Failed to process email {idx}: {e}")
            stats["failed"] += 1
            print(f"[{idx}/{len(emails)}] [ERROR] - {safe_print_subject(email_subject)}")

    # Move organized emails to their folders on server
    if email_moves and all([server, port, email_address, password]):
        print(f"\n[ORGANIZING] Moving {len(email_moves)} emails to category folders on server...")
        try:
            moved_count = move_emails(
                server=server,
                port=port,
                email_address=email_address,
                password=password,
                email_moves=email_moves
            )
            print(f"[SUCCESS] Moved {moved_count} emails to category folders")
        except Exception as e:
            logger.error(f"Failed to move emails: {e}")
            print(f"[WARNING] Could not move emails: {e}")

    # Delete spam emails from server
    if delete_spam and spam_email_ids and all([server, port, email_address, password]):
        print(f"\n[DELETING SPAM] Removing {len(spam_email_ids)} spam emails from server...")
        try:
            deleted_count = delete_emails(
                server=server,
                port=port,
                email_address=email_address,
                password=password,
                email_ids=spam_email_ids
            )
            print(f"[SUCCESS] Deleted {deleted_count} spam emails from inbox")
        except Exception as e:
            logger.error(f"Failed to delete spam emails: {e}")
            print(f"[WARNING] Could not delete spam emails: {e}")

    # Save summary
    summary = {
        "processing_timestamp": datetime.utcnow().isoformat() + "Z",
        "statistics": stats,
        "interview_requests": interview_requests
    }

    summary_file = output_dir / "processing_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return stats, interview_requests


def print_summary(stats: Dict[str, Any], interview_requests: List[Dict[str, Any]]) -> None:
    """Print processing summary."""
    print("\n" + "="*60)
    print("PROCESSING SUMMARY")
    print("="*60)

    print(f"\nTotal Processed: {stats['total_emails']}")
    print(f"Interview Requests Detected: {stats['interview_requests_detected']}")
    print(f"Spam Deleted: {stats['spam_deleted']}")
    print(f"Organized: {stats['organized']}")
    print(f"Failed: {stats['failed']}")

    if interview_requests:
        print("\n" + "-"*60)
        print("INTERVIEW REQUESTS REQUIRING ATTENTION:")
        print("-"*60)
        for ir in interview_requests:
            print(f"\n  Subject: {ir['subject']}")
            print(f"  Company: {ir['company']}")
            print(f"  Confidence: {ir['confidence']:.0%}")
            print(f"  Status: IN INBOX - NEEDS MANUAL REVIEW")

    if stats['categories']:
        print("\n" + "-"*60)
        print("Other Categories Organized:")
        print("-"*60)
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {category}: {count}")

    print("\n" + "="*60)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python process_inbox_smart.py <output_dir> [--limit N] [--mark-read]")
        print("\nSmart processing:")
        print("  - Detects genuine interview requests")
        print("  - Leaves interview requests in inbox")
        print("  - Deletes spam")
        print("  - Organizes other emails")
        sys.exit(1)

    output_dir = Path(sys.argv[1])

    # Parse arguments
    limit = None
    if "--limit" in sys.argv:
        try:
            limit_index = sys.argv.index("--limit")
            limit = int(sys.argv[limit_index + 1])
        except (IndexError, ValueError):
            print("Error: --limit requires a number")
            sys.exit(1)

    mark_as_read = "--mark-read" in sys.argv
    validate_only = "--validate-only" in sys.argv

    # Load configuration
    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    folder = os.getenv("EMAIL_FOLDER", "INBOX")
    criteria = os.getenv("EMAIL_SEARCH_CRITERIA", "UNSEEN")

    if not all([server, email_address, password]):
        print("Error: Missing email configuration in .env file")
        sys.exit(1)

    if not validate_only and not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in .env file")
        sys.exit(1)

    try:
        print("\n[STEP 1] Fetching emails from inbox...")
        print(f"   Account: {email_address}")
        print(f"   Folder: {folder}")
        if limit:
            print(f"   Limit: {limit} emails")

        emails = fetch_emails(
            server=server,
            port=port,
            email_address=email_address,
            password=password,
            folder=folder,
            criteria=criteria,
            limit=limit,
            mark_as_read=False  # Never mark Interview Requests as read
        )

        if not emails:
            print("\n[SUCCESS] No emails found")
            sys.exit(0)

        print(f"\n[SUCCESS] Fetched {len(emails)} emails")

        print(f"\n[STEP 2] Smart processing...")
        stats, interview_requests = process_inbox_smart(
            emails=emails,
            output_dir=output_dir,
            validate_only=validate_only,
            delete_spam=True,
            server=server,
            port=port,
            email_address=email_address,
            password=password
        )

        print_summary(stats, interview_requests)

        if interview_requests:
            print(f"\n[ACTION REQUIRED] {len(interview_requests)} interview request(s) in inbox")
            print(f"[NEXT STEPS] Review inbox and respond to interview requests")

        print(f"\n[SUCCESS] Processing complete")
        print(f"           Results: {output_dir}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

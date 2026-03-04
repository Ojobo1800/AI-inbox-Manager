"""
Process emails and organize by category.

This script fetches emails, classifies them, and organizes results
into category-specific folders. Spam/Other emails are handled separately.
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

# Import our execution modules
from fetch_emails import fetch_emails, EmailConnectionError, EmailFetchError
from classify_email import classify_email

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_category_folders(base_dir: Path) -> Dict[str, Path]:
    """
    Create folders for each category.

    Args:
        base_dir: Base directory for organized results

    Returns:
        Dictionary mapping category names to folder paths
    """
    categories = [
        "Interview Request",
        "Interview Schedule",
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
        "Other_Spam"  # Special folder for Other/Spam
    ]

    category_folders = {}
    for category in categories:
        # Create safe folder name
        folder_name = category.replace(" ", "_")
        folder_path = base_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        category_folders[category] = folder_path

    logger.info(f"Created {len(category_folders)} category folders")
    return category_folders


def save_to_category_folder(
    email_data: Dict[str, Any],
    classification: Dict[str, Any],
    category_folders: Dict[str, Path],
    email_index: int
) -> Path:
    """
    Save email and classification to appropriate category folder.

    Args:
        email_data: Original email data
        classification: Classification result
        category_folders: Dictionary of category folder paths
        email_index: Email index for filename

    Returns:
        Path where file was saved
    """
    category = classification.get("category", "Other")

    # Map "Other" to "Other_Spam" folder
    if category == "Other":
        folder_key = "Other_Spam"
    else:
        folder_key = category

    folder = category_folders.get(folder_key)
    if not folder:
        folder = category_folders["Other_Spam"]

    # Create filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    email_id = email_data.get("email_id", email_index)
    filename = f"{timestamp}_{email_id}.json"

    filepath = folder / filename

    # Combine email data and classification
    combined = {
        "email": email_data,
        "classification": classification,
        "organized_at": datetime.utcnow().isoformat() + "Z"
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    return filepath


def process_and_organize(
    emails: List[Dict[str, Any]],
    output_dir: Path,
    validate_only: bool = False
) -> Dict[str, Any]:
    """
    Process emails and organize by category.

    Args:
        emails: List of email dictionaries
        output_dir: Base directory for organized results
        validate_only: If True, skip API call

    Returns:
        Summary statistics dictionary
    """
    # Create category folders
    category_folders = create_category_folders(output_dir)

    stats = {
        "total_emails": len(emails),
        "classified_success": 0,
        "classification_failed": 0,
        "requires_manual_review": 0,
        "high_confidence": 0,
        "spam_detected": 0,
        "categories": {},
        "processing_time": 0
    }

    start_time = datetime.utcnow()

    for idx, email_data in enumerate(emails, 1):
        email_subject = email_data.get("subject", "No Subject")
        logger.info(f"Processing email {idx}/{len(emails)}: {email_subject[:50]}...")

        try:
            # Classify email
            classification = classify_email(email_data, validate_only=validate_only)

            # Save to category folder
            saved_path = save_to_category_folder(
                email_data,
                classification,
                category_folders,
                idx
            )

            # Track statistics
            category = classification.get("category")
            confidence = classification.get("confidence", 0)

            stats["classified_success"] += 1

            if classification.get("requires_manual_review"):
                stats["requires_manual_review"] += 1

            if confidence >= 0.90:
                stats["high_confidence"] += 1

            # Track spam
            if category == "Other":
                stats["spam_detected"] += 1

            # Count categories
            stats["categories"][category] = stats["categories"].get(category, 0) + 1

            # Log result
            folder_name = saved_path.parent.name
            print(f"  [{idx}/{len(emails)}] {category} (conf: {confidence:.2f}) -> {folder_name}/")

        except Exception as e:
            logger.error(f"Failed to classify email {idx}: {e}")
            stats["classification_failed"] += 1
            continue

    # Calculate processing time
    end_time = datetime.utcnow()
    stats["processing_time"] = (end_time - start_time).total_seconds()

    # Save summary
    summary = {
        "processing_timestamp": end_time.isoformat() + "Z",
        "statistics": stats,
        "category_folders": {k: str(v) for k, v in category_folders.items()}
    }

    summary_file = output_dir / "organization_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Organization summary saved to: {summary_file}")

    return stats


def print_summary_report(stats: Dict[str, Any]) -> None:
    """
    Print summary report.

    Args:
        stats: Statistics dictionary
    """
    print("\n" + "=" * 60)
    print("EMAIL ORGANIZATION SUMMARY")
    print("=" * 60)

    print(f"\nTotal Emails: {stats['total_emails']}")
    print(f"Successfully Classified: {stats['classified_success']}")
    print(f"Failed: {stats['classification_failed']}")
    print(f"Spam Detected: {stats['spam_detected']}")
    print(f"Requires Manual Review: {stats['requires_manual_review']}")
    print(f"High Confidence (>=90%): {stats['high_confidence']}")
    print(f"Processing Time: {stats['processing_time']:.2f} seconds")

    if stats['categories']:
        print("\nOrganized by Category:")
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            folder_name = category.replace(" ", "_") if category != "Other" else "Other_Spam"
            print(f"  - {category}: {count} email(s) -> {folder_name}/")

    print("\n" + "=" * 60)


def main() -> None:
    """
    CLI entry point for organized inbox processing.

    Usage:
        python process_and_organize.py <output_dir> [--limit N] [--mark-read] [--validate-only]
    """
    if len(sys.argv) < 2:
        print("Usage: python process_and_organize.py <output_dir> [options]")
        print("\nFetches, classifies, and organizes emails into category folders.")
        print("\nOptions:")
        print("  --limit N         Fetch maximum N emails")
        print("  --mark-read       Mark fetched emails as read")
        print("  --validate-only   Skip API calls (for testing)")
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

    # Load email configuration
    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    folder = os.getenv("EMAIL_FOLDER", "INBOX")
    criteria = os.getenv("EMAIL_SEARCH_CRITERIA", "UNSEEN")

    # Validate configuration
    if not all([server, email_address, password]):
        print("Error: Missing email configuration in .env file")
        sys.exit(1)

    if not validate_only and not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in .env file")
        sys.exit(1)

    try:
        # Step 1: Fetch emails
        print("\n[STEP 1] Fetching emails from inbox...")
        print(f"   Server: {server}")
        print(f"   Account: {email_address}")
        print(f"   Folder: {folder}")
        print(f"   Criteria: {criteria}")
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
            mark_as_read=mark_as_read
        )

        if not emails:
            print("\n[SUCCESS] No emails found matching criteria")
            sys.exit(0)

        print(f"\n[SUCCESS] Fetched {len(emails)} emails")

        # Step 2: Process and organize
        print(f"\n[STEP 2] Classifying and organizing emails...")
        if validate_only:
            print("   (Running in validate-only mode - no API calls)")

        stats = process_and_organize(emails, output_dir, validate_only=validate_only)

        # Step 3: Report results
        print_summary_report(stats)

        print(f"\n[SUCCESS] Emails organized in: {output_dir}")
        print(f"\nNote: Spam emails saved to: {output_dir / 'Other_Spam'}")

        sys.exit(0)

    except EmailConnectionError as e:
        logger.error(f"Email connection failed: {e}")
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    except EmailFetchError as e:
        logger.error(f"Email fetch failed: {e}")
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

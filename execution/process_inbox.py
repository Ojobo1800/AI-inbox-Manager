"""
End-to-end inbox processing pipeline.

This script orchestrates the complete workflow:
1. Fetch emails from inbox
2. Classify each email
3. Save results
4. Generate summary report

This is the main entry point for processing job-related emails.
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
from validate_classification import validate_classification

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_email_batch(
    emails: List[Dict[str, Any]],
    output_dir: Path,
    validate_only: bool = False
) -> Dict[str, Any]:
    """
    Process a batch of emails through classification pipeline.

    Args:
        emails: List of email dictionaries
        output_dir: Directory to save classification results
        validate_only: If True, skip API call (for testing)

    Returns:
        Summary statistics dictionary
    """
    results = []
    stats = {
        "total_emails": len(emails),
        "classified_success": 0,
        "classification_failed": 0,
        "requires_manual_review": 0,
        "high_confidence": 0,
        "categories": {},
        "processing_time": 0
    }

    start_time = datetime.utcnow()

    for idx, email_data in enumerate(emails, 1):
        email_subject = email_data.get("subject", "No Subject")
        logger.info(f"Processing email {idx}/{len(emails)}: {email_subject}")

        try:
            # Classify email
            classification = classify_email(email_data, validate_only=validate_only)

            # Track statistics
            category = classification.get("category")
            confidence = classification.get("confidence", 0)

            stats["classified_success"] += 1

            if classification.get("requires_manual_review"):
                stats["requires_manual_review"] += 1

            if confidence >= 0.90:
                stats["high_confidence"] += 1

            # Count categories
            stats["categories"][category] = stats["categories"].get(category, 0) + 1

            # Save individual result
            email_id = email_data.get("email_id", f"email_{idx}")
            result_file = output_dir / f"{email_id}_classification.json"

            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(classification, f, indent=2, ensure_ascii=False)

            results.append({
                "email_id": email_id,
                "subject": email_subject,
                "category": category,
                "confidence": confidence,
                "requires_review": classification.get("requires_manual_review"),
                "result_file": str(result_file)
            })

            logger.info(
                f"  → {category} (confidence: {confidence:.2f}, "
                f"review: {classification.get('requires_manual_review')})"
            )

        except Exception as e:
            logger.error(f"Failed to classify email {idx}: {e}")
            stats["classification_failed"] += 1
            continue

    # Calculate processing time
    end_time = datetime.utcnow()
    stats["processing_time"] = (end_time - start_time).total_seconds()

    # Save batch summary
    summary = {
        "processing_timestamp": end_time.isoformat() + "Z",
        "statistics": stats,
        "results": results
    }

    summary_file = output_dir / "batch_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Batch summary saved to: {summary_file}")

    return stats


def print_summary_report(stats: Dict[str, Any]) -> None:
    """
    Print human-readable summary report.

    Args:
        stats: Statistics dictionary from processing
    """
    print("\n" + "=" * 60)
    print("EMAIL PROCESSING SUMMARY")
    print("=" * 60)

    print(f"\nTotal Emails: {stats['total_emails']}")
    print(f"Successfully Classified: {stats['classified_success']}")
    print(f"Failed: {stats['classification_failed']}")
    print(f"Requires Manual Review: {stats['requires_manual_review']}")
    print(f"High Confidence (>=90%): {stats['high_confidence']}")
    print(f"Processing Time: {stats['processing_time']:.2f} seconds")

    if stats['categories']:
        print("\nCategories Breakdown:")
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            print(f"  - {category}: {count}")

    print("\n" + "=" * 60)


def main() -> None:
    """
    CLI entry point for inbox processing pipeline.

    Usage:
        python process_inbox.py <output_dir> [--limit N] [--mark-read] [--validate-only]
    """
    if len(sys.argv) < 2:
        print("Usage: python process_inbox.py <output_dir> [options]")
        print("\nFetches emails from inbox, classifies them, and saves results.")
        print("\nOptions:")
        print("  --limit N         Fetch maximum N emails")
        print("  --mark-read       Mark fetched emails as read")
        print("  --validate-only   Skip API calls (for testing)")
        print("\nRequired .env variables:")
        print("  EMAIL_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD")
        print("  OPENAI_API_KEY")
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)

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
        print("Required: EMAIL_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD")
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

        # Step 2: Classify emails
        print(f"\n[STEP 2] Classifying emails...")
        if validate_only:
            print("   (Running in validate-only mode - no API calls)")

        stats = process_email_batch(emails, output_dir, validate_only=validate_only)

        # Step 3: Report results
        print_summary_report(stats)

        print(f"\n[SUCCESS] Results saved to: {output_dir}")

        # Exit with appropriate code
        if stats['classification_failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except EmailConnectionError as e:
        logger.error(f"Email connection failed: {e}")
        print(f"\n[ERROR] {e}", file=sys.stderr)
        print("\nCheck your email credentials and server settings in .env")
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

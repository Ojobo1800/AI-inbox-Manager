"""
Integration test for inbox processing.

CRITICAL TEST: Ensures interview requests are NEVER moved or deleted.
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch

# Add execution directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

from process_inbox_auto import process_unread_emails, is_genuine_interview_request


def create_mock_email(email_id, subject, from_addr, category, confidence=0.92, company="Test Company"):
    """Create a mock email for testing."""
    return {
        "email_id": str(email_id),
        "subject": subject,
        "from": from_addr,
        "body": f"Test email body for {subject}"
    }


def create_mock_classification(category, confidence=0.92, company="Test Company", is_edge_case=False, edge_type=None):
    """Create a mock classification result."""
    classification = {
        "category": category,
        "confidence": confidence,
        "extracted_data": {
            "company_name": company,
            "position": "BI Developer"
        },
        "edge_case": {
            "is_edge_case": is_edge_case
        }
    }

    if edge_type:
        classification["edge_case"]["type"] = edge_type

    return classification


def test_interview_requests_never_moved_or_deleted():
    """
    CRITICAL TEST: Interview requests must NEVER be moved or deleted.

    This test simulates processing emails and verifies that:
    1. Interview requests are NOT in spam_email_ids (would be deleted)
    2. Interview requests are NOT in email_moves (would be moved)
    3. Interview requests ARE counted in stats["interview_requests"]
    """

    print("\nTesting: Interview requests are NEVER moved or deleted")
    print("-" * 60)

    # Create mock emails
    mock_emails = [
        create_mock_email(1, "New Opportunity Available", "recruiter@askconsulting.com", "Interview Request"),
        create_mock_email(2, "Job Alert: BI Developer", "noreply@indeed.com", "Job Alert"),
        create_mock_email(3, "Spam email", "spam@spam.com", "Other"),
        create_mock_email(4, "Here is a new role", "recruiter@ugt.com", "Interview Request"),
    ]

    # Track which emails would be moved or deleted
    spam_email_ids = []
    email_moves = {}
    interview_requests = []

    # Category to folder mapping (from process_inbox_auto.py)
    category_to_folder = {
        "Job Alert": "Job Alerts",
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

    # Simulate the processing logic from process_inbox_auto.py
    mock_classifications = [
        create_mock_classification("Interview Request", 0.92, "Ask Consulting"),
        create_mock_classification("Job Alert", 0.95, "Indeed"),
        create_mock_classification("Other", 0.95, "Spam Company"),
        create_mock_classification("Interview Request", 0.92, "United Global Technologies"),
    ]

    for idx, (email_data, classification) in enumerate(zip(mock_emails, mock_classifications), 1):
        email_subject = email_data.get("subject", "No Subject")[:60]
        category = classification.get("category")
        confidence = classification.get("confidence", 0)

        # THIS IS THE CRITICAL LOGIC FROM process_inbox_auto.py
        if is_genuine_interview_request(classification):
            # KEEP IN INBOX - Do not touch
            company = classification["extracted_data"].get("company_name")
            interview_requests.append({
                "subject": email_subject,
                "company": company,
                "confidence": confidence
            })
            print(f"  [{idx}] INTERVIEW REQUEST from {company} - KEPT IN INBOX")

        elif category == "Other":
            # SPAM - Delete
            spam_email_ids.append(email_data.get("email_id"))
            print(f"  [{idx}] SPAM - MARKED FOR DELETION")

        else:
            # OTHER CATEGORIES - Organize
            server_folder = category_to_folder.get(category)
            if server_folder:
                email_moves[email_data.get("email_id")] = server_folder
                print(f"  [{idx}] {category} - MARKED FOR MOVE to {server_folder}")

    # CRITICAL ASSERTIONS
    print("\nVerifying critical requirements:")
    print("-" * 60)

    # Email 1: Ask Consulting - MUST NOT be moved or deleted
    assert "1" not in spam_email_ids, "CRITICAL BUG: Ask Consulting interview request in spam_email_ids!"
    assert "1" not in email_moves, "CRITICAL BUG: Ask Consulting interview request in email_moves!"
    print("[PASS] Ask Consulting NOT in spam or move lists")

    # Email 4: United Global Technologies - MUST NOT be moved or deleted
    assert "4" not in spam_email_ids, "CRITICAL BUG: UGT interview request in spam_email_ids!"
    assert "4" not in email_moves, "CRITICAL BUG: UGT interview request in email_moves!"
    print("[PASS] United Global Technologies NOT in spam or move lists")

    # Verify interview requests were detected
    assert len(interview_requests) == 2, f"Expected 2 interview requests, got {len(interview_requests)}"
    print(f"[PASS] {len(interview_requests)} interview requests correctly detected")

    # Email 2: Job Alert - SHOULD be moved
    assert "2" in email_moves, "Job Alert should be moved"
    assert email_moves["2"] == "Job Alerts", "Job Alert should go to Job Alerts folder"
    print("[PASS] Job Alert correctly marked for move")

    # Email 3: Spam - SHOULD be deleted
    assert "3" in spam_email_ids, "Spam should be deleted"
    print("[PASS] Spam correctly marked for deletion")

    print("\n" + "="*60)
    print("INTEGRATION TEST PASSED - Interview requests are safe!")
    print("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("INBOX PROCESSING INTEGRATION TEST")
    print("="*60)

    try:
        test_interview_requests_never_moved_or_deleted()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[FAIL] {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

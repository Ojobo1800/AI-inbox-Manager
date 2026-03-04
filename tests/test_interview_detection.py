"""
Unit tests for interview request detection.

CRITICAL: These tests ensure interview requests are NEVER moved or deleted.
"""

import sys
from pathlib import Path

# Add execution directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

from process_inbox_auto import is_genuine_interview_request


def test_genuine_interview_request_detection():
    """Test that genuine interview requests are correctly identified."""

    # Test case: Ask Consulting - MUST be detected as genuine
    ask_consulting = {
        "category": "Interview Request",
        "confidence": 0.92,
        "extracted_data": {
            "company_name": "Ask Consulting",
            "position": "BI Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(ask_consulting)
    assert result == True, "Ask Consulting interview request MUST be detected as genuine"

    # Test case: United Global Technologies
    ugt = {
        "category": "Interview Request",
        "confidence": 0.92,
        "extracted_data": {
            "company_name": "United Global Technologies",
            "position": "Developer IV"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(ugt)
    assert result == True, "United Global Technologies MUST be detected as genuine"

    # Test case: Excelon Solutions
    excelon = {
        "category": "Interview Request",
        "confidence": 0.90,
        "extracted_data": {
            "company_name": "Excelon Solutions",
            "position": "BI Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(excelon)
    assert result == True, "Excelon Solutions MUST be detected as genuine"

    # Test case: Wesco
    wesco = {
        "category": "Interview Request",
        "confidence": 0.90,
        "extracted_data": {
            "company_name": "Wesco",
            "position": "BI Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(wesco)
    assert result == True, "Wesco MUST be detected as genuine"

    print("[PASS] All genuine interview requests correctly detected")


def test_job_alert_rejection():
    """Test that job alerts are NOT detected as interview requests."""

    # Test case: Indeed job alert
    indeed_alert = {
        "category": "Job Alert",
        "confidence": 0.95,
        "extracted_data": {
            "company_name": "Indeed",
            "position": "BI Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(indeed_alert)
    assert result == False, "Job Alert category MUST be rejected"

    # Test case: LinkedIn notification (Interview Request category but from job board)
    linkedin = {
        "category": "Interview Request",
        "confidence": 0.90,
        "extracted_data": {
            "company_name": "LinkedIn Jobs",
            "position": "BI Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(linkedin)
    assert result == False, "LinkedIn job board MUST be rejected"

    print("[PASS] All job alerts correctly rejected")


def test_low_confidence_rejection():
    """Test that low confidence classifications are rejected."""

    low_confidence = {
        "category": "Interview Request",
        "confidence": 0.75,  # Below 80% threshold
        "extracted_data": {
            "company_name": "Some Company",
            "position": "Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(low_confidence)
    assert result == False, "Low confidence (<80%) MUST be rejected"

    print("[PASS] Low confidence correctly rejected")


def test_spam_edge_case_rejection():
    """Test that spam edge cases are rejected."""

    spam_case = {
        "category": "Interview Request",
        "confidence": 0.85,
        "extracted_data": {
            "company_name": "Suspicious Company",
            "position": "Developer"
        },
        "edge_case": {
            "is_edge_case": True,
            "type": "spam"
        }
    }

    result = is_genuine_interview_request(spam_case)
    assert result == False, "Spam edge case MUST be rejected"

    print("[PASS] Spam edge cases correctly rejected")


def test_missing_company_rejection():
    """Test that requests without company name are rejected."""

    no_company = {
        "category": "Interview Request",
        "confidence": 0.90,
        "extracted_data": {
            "position": "Developer"
        },
        "edge_case": {
            "is_edge_case": False
        }
    }

    result = is_genuine_interview_request(no_company)
    assert result == False, "Missing company name MUST be rejected"

    print("[PASS] Missing company name correctly rejected")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("INTERVIEW REQUEST DETECTION TESTS")
    print("="*60 + "\n")

    try:
        test_genuine_interview_request_detection()
        test_job_alert_rejection()
        test_low_confidence_rejection()
        test_spam_edge_case_rejection()
        test_missing_company_rejection()

        print("\n" + "="*60)
        print("ALL TESTS PASSED")
        print("="*60 + "\n")

        sys.exit(0)
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

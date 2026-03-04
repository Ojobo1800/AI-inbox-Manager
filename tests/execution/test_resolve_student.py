"""
Unit tests for resolve_student.py

Tests student identification from email headers, To fields,
and body content extraction.
"""

import pytest
from execution.resolve_student import (
    extract_username_from_email,
    find_student_email_from_headers,
    find_student_email_from_to_field,
    find_student_name_in_body,
    resolve_student,
    CENTRAL_INBOX,
)


class TestExtractUsernameFromEmail:
    """Test username extraction from email addresses."""

    def test_standard_gmail(self):
        assert extract_username_from_email("john.doe@gmail.com") == "john.doe"

    def test_uppercase_email(self):
        assert extract_username_from_email("John.Doe@Gmail.com") == "john.doe"

    def test_with_plus(self):
        assert extract_username_from_email("john.doe+test@gmail.com") == "john.doe+test"

    def test_simple_username(self):
        assert extract_username_from_email("jdoe@example.com") == "jdoe"

    def test_empty_string(self):
        assert extract_username_from_email("") == ""

    def test_no_at_sign(self):
        assert extract_username_from_email("not-an-email") == ""

    def test_none_input(self):
        assert extract_username_from_email(None) == ""

    def test_whitespace(self):
        assert extract_username_from_email("  john.doe@gmail.com  ") == "john.doe"


class TestFindStudentEmailFromHeaders:
    """Test student email extraction from forwarding headers."""

    def test_delivered_to_header(self):
        headers = {"Delivered-To": "student.name@gmail.com"}
        assert find_student_email_from_headers(headers) == "student.name@gmail.com"

    def test_x_forwarded_to_header(self):
        headers = {"X-Forwarded-To": "student@gmail.com"}
        assert find_student_email_from_headers(headers) == "student@gmail.com"

    def test_x_original_to_header(self):
        headers = {"X-Original-To": "student@gmail.com"}
        assert find_student_email_from_headers(headers) == "student@gmail.com"

    def test_envelope_to_header(self):
        headers = {"Envelope-To": "student@gmail.com"}
        assert find_student_email_from_headers(headers) == "student@gmail.com"

    def test_skips_central_inbox(self):
        headers = {"Delivered-To": CENTRAL_INBOX}
        assert find_student_email_from_headers(headers) is None

    def test_picks_non_central_from_multiple(self):
        headers = {
            "Delivered-To": CENTRAL_INBOX,
            "X-Forwarded-To": "student@gmail.com",
        }
        result = find_student_email_from_headers(headers)
        assert result == "student@gmail.com"

    def test_case_insensitive_header_keys(self):
        headers = {"delivered-to": "student@gmail.com"}
        assert find_student_email_from_headers(headers) == "student@gmail.com"

    def test_empty_headers(self):
        assert find_student_email_from_headers({}) is None

    def test_no_relevant_headers(self):
        headers = {"From": "recruiter@company.com", "Subject": "Interview"}
        assert find_student_email_from_headers(headers) is None

    def test_header_with_multiple_emails(self):
        # Some headers might have multiple emails
        headers = {
            "Delivered-To": f"{CENTRAL_INBOX}, student@gmail.com"
        }
        result = find_student_email_from_headers(headers)
        assert result == "student@gmail.com"

    def test_priority_order(self):
        """Delivered-To should be checked before X-Forwarded-To."""
        headers = {
            "X-Forwarded-To": "second@gmail.com",
            "Delivered-To": "first@gmail.com",
        }
        result = find_student_email_from_headers(headers)
        assert result == "first@gmail.com"


class TestFindStudentEmailFromToField:
    """Test student email extraction from To/CC fields."""

    def test_finds_gmail_address(self):
        to_addresses = ["student.name@gmail.com"]
        assert find_student_email_from_to_field(to_addresses) == "student.name@gmail.com"

    def test_skips_central_inbox(self):
        to_addresses = [CENTRAL_INBOX]
        assert find_student_email_from_to_field(to_addresses) is None

    def test_picks_gmail_over_central(self):
        to_addresses = [CENTRAL_INBOX, "student@gmail.com"]
        assert find_student_email_from_to_field(to_addresses) == "student@gmail.com"

    def test_only_returns_gmail(self):
        """Only @gmail.com addresses are considered (student accounts are Gmail)."""
        to_addresses = ["recruiter@company.com"]
        assert find_student_email_from_to_field(to_addresses) is None

    def test_empty_list(self):
        assert find_student_email_from_to_field([]) is None

    def test_case_insensitive(self):
        to_addresses = ["Student@Gmail.COM"]
        result = find_student_email_from_to_field(to_addresses)
        assert result == "student@gmail.com"


class TestFindStudentNameInBody:
    """Test name extraction from email body."""

    def test_dear_pattern(self):
        body = "Dear John Smith, We'd like to schedule an interview."
        assert find_student_name_in_body(body) == "John Smith"

    def test_hi_pattern(self):
        body = "Hi Jane Doe, Your interview has been scheduled."
        assert find_student_name_in_body(body) == "Jane Doe"

    def test_interview_for_pattern(self):
        body = "We have an interview for Bob Wilson next week."
        assert find_student_name_in_body(body) == "Bob Wilson"

    def test_candidate_pattern(self):
        body = "Candidate: Alice Johnson has been shortlisted."
        assert find_student_name_in_body(body) == "Alice Johnson"

    def test_no_name_found(self):
        body = "Please see the attached schedule for next week."
        assert find_student_name_in_body(body) is None

    def test_empty_body(self):
        assert find_student_name_in_body("") is None

    def test_none_body(self):
        assert find_student_name_in_body(None) is None


class TestResolveStudent:
    """Test the main resolve_student function."""

    def test_resolve_from_headers_high_confidence(self):
        email_data = {
            "headers": {"Delivered-To": "john.doe@gmail.com"},
            "body_content": "Interview scheduled.",
        }
        result = resolve_student(email_data)

        assert result["student_gmail"] == "john.doe@gmail.com"
        assert result["student_username"] == "john.doe"
        assert result["resolution_method"] == "email_headers"
        assert result["confidence"] == "high"

    def test_resolve_from_to_field_medium_confidence(self):
        email_data = {
            "headers": {},  # No forwarding headers
            "to_addresses": ["student.name@gmail.com"],
            "body_content": "Interview details below.",
        }
        result = resolve_student(email_data)

        assert result["student_gmail"] == "student.name@gmail.com"
        assert result["student_username"] == "student.name"
        assert result["resolution_method"] == "to_field"
        assert result["confidence"] == "medium"

    def test_resolve_from_body_low_confidence(self):
        email_data = {
            "headers": {},
            "to_addresses": [CENTRAL_INBOX],
            "body_content": "Dear Alice Brown, your interview is confirmed.",
        }
        result = resolve_student(email_data)

        assert result["student_gmail"] is None
        assert result["student_name_hint"] == "Alice Brown"
        assert result["resolution_method"] == "body_name_extraction"
        assert result["confidence"] == "low"

    def test_resolve_nothing_found(self):
        email_data = {
            "headers": {},
            "to_addresses": [],
            "body_content": "No identifiable information here.",
        }
        result = resolve_student(email_data)

        assert result["student_gmail"] is None
        assert result["student_username"] is None
        assert result["resolution_method"] == "none"
        assert result["confidence"] == "low"

    def test_resolve_headers_take_priority(self):
        """Headers should be used even if To field also has a Gmail."""
        email_data = {
            "headers": {"Delivered-To": "header.student@gmail.com"},
            "to_addresses": ["to.student@gmail.com"],
            "body_content": "Dear Body Student, hello.",
        }
        result = resolve_student(email_data)

        assert result["student_gmail"] == "header.student@gmail.com"
        assert result["resolution_method"] == "email_headers"

    def test_resolve_empty_email_data(self):
        result = resolve_student({})

        assert result["student_gmail"] is None
        assert result["resolution_method"] == "none"

    def test_resolve_skips_central_inbox_in_headers(self):
        email_data = {
            "headers": {"Delivered-To": CENTRAL_INBOX},
            "to_addresses": ["student@gmail.com"],
        }
        result = resolve_student(email_data)

        assert result["student_gmail"] == "student@gmail.com"
        assert result["resolution_method"] == "to_field"

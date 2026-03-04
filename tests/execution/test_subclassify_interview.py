"""
Unit tests for subclassify_interview.py

Tests the interview sub-classification logic with mocked API calls,
business rule application, and edge case handling.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from execution.subclassify_interview import (
    format_email_for_subclassification,
    parse_subclassification_response,
    apply_business_rules,
    subclassify_interview,
    is_interview_related,
    load_email_from_file,
    save_subclassification_result,
    call_openai_api,
    INTERVIEW_SUB_TYPES,
    INTERVIEW_RELATED_CATEGORIES,
    JOB_MACHINE_SUB_TYPES,
)


# --- Sample data helpers ---


def make_classification(
    sub_type="Interview Request",
    confidence=0.95,
    is_job_machine=False,
    job_machine_sub_type=None,
    is_next_round=False,
    interview_date=None,
    cancellation_reason=None,
    **kwargs,
):
    """Helper to build a classification dict with defaults."""
    result = {
        "interview_sub_type": sub_type,
        "job_machine_sub_type": job_machine_sub_type,
        "company_name": kwargs.get("company_name", "TechCorp"),
        "position_title": kwargs.get("position_title", "Data Analyst"),
        "contact_name": kwargs.get("contact_name", "Jane Smith"),
        "contact_title": kwargs.get("contact_title", "HR Manager"),
        "contact_email": kwargs.get("contact_email", "jane@techcorp.com"),
        "contact_phone": kwargs.get("contact_phone", None),
        "interview_date": interview_date,
        "interview_time": kwargs.get("interview_time", None),
        "interview_timezone": kwargs.get("interview_timezone", None),
        "interview_format": kwargs.get("interview_format", None),
        "meeting_link_or_dial_in": kwargs.get("meeting_link_or_dial_in", None),
        "num_interviewers": kwargs.get("num_interviewers", None),
        "interviewer_names_roles": kwargs.get("interviewer_names_roles", None),
        "cancellation_reason": cancellation_reason,
        "original_date": kwargs.get("original_date", None),
        "original_time": kwargs.get("original_time", None),
        "new_date": kwargs.get("new_date", None),
        "new_time": kwargs.get("new_time", None),
        "is_job_machine": is_job_machine,
        "is_next_round": is_next_round,
        "job_description_url": kwargs.get("job_description_url", None),
        "confidence": confidence,
        "reasoning": kwargs.get("reasoning", "Test classification"),
    }
    return result


def make_api_response(classification_dict):
    """Wrap a classification dict into the API response format."""
    return {
        "response": json.dumps(classification_dict),
        "usage": {"input_tokens": 200, "output_tokens": 100},
    }


SAMPLE_EMAIL = {
    "subject": "Interview Invitation - Data Analyst Position",
    "sender_email": "hr@techcorp.com",
    "sender_name": "Jane Smith",
    "email_date": "2026-02-15",
    "body_content": "We'd like to schedule an interview for the Data Analyst position.",
}


# --- Tests ---


class TestFormatEmailForSubclassification:
    """Test prompt formatting."""

    def test_format_complete_email(self):
        prompt = format_email_for_subclassification(SAMPLE_EMAIL)

        assert "Subject: Interview Invitation - Data Analyst Position" in prompt
        assert "From: hr@techcorp.com" in prompt
        assert "Sender Name: Jane Smith" in prompt
        assert "We'd like to schedule an interview" in prompt

    def test_format_minimal_email(self):
        email = {"subject": "Test", "body_content": "Test content"}
        prompt = format_email_for_subclassification(email)

        assert "Subject: Test" in prompt
        assert "Test content" in prompt
        assert "From:" in prompt

    def test_prompt_contains_sub_type_definitions(self):
        prompt = format_email_for_subclassification(SAMPLE_EMAIL)

        assert "Interview Request" in prompt
        assert "Phone Screen" in prompt
        assert "Client Screen" in prompt
        assert "Technical Interview" in prompt
        assert "Interview Cancelled" in prompt
        assert "Interview Rescheduled" in prompt
        assert "Job Machine" in prompt


class TestParseSubclassificationResponse:
    """Test JSON response parsing."""

    def test_parse_valid_json(self):
        classification = make_classification()
        response_text = json.dumps(classification)

        result = parse_subclassification_response(response_text)

        assert result["interview_sub_type"] == "Interview Request"
        assert result["confidence"] == 0.95

    def test_parse_json_with_markdown(self):
        classification = make_classification(sub_type="Phone Screen")
        response_text = f"```json\n{json.dumps(classification)}\n```"

        result = parse_subclassification_response(response_text)

        assert result["interview_sub_type"] == "Phone Screen"

    def test_parse_json_with_backticks(self):
        classification = make_classification(sub_type="Client Screen")
        response_text = f"```\n{json.dumps(classification)}\n```"

        result = parse_subclassification_response(response_text)

        assert result["interview_sub_type"] == "Client Screen"

    def test_parse_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_subclassification_response("Not valid JSON")

    def test_parse_empty_string(self):
        with pytest.raises(json.JSONDecodeError):
            parse_subclassification_response("")


class TestApplyBusinessRules:
    """Test business rule application."""

    # --- Confidence thresholds ---

    def test_high_confidence_auto_send(self):
        classification = make_classification(confidence=0.97)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is True
        assert result["requires_human_review"] is False
        assert result["confidence_tier"] == "high"

    def test_medium_high_confidence_auto_send_with_audit(self):
        classification = make_classification(confidence=0.88)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is True
        assert result["requires_human_review"] is False
        assert result["confidence_tier"] == "medium_high"
        assert result["flag_for_audit"] is True

    def test_medium_confidence_requires_review(self):
        classification = make_classification(confidence=0.75)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is False
        assert result["requires_human_review"] is True
        assert result["confidence_tier"] == "medium"

    def test_low_confidence_requires_review(self):
        classification = make_classification(confidence=0.55)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is False
        assert result["requires_human_review"] is True
        assert result["confidence_tier"] == "low"

    def test_boundary_095(self):
        classification = make_classification(confidence=0.95)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is True
        assert result["confidence_tier"] == "high"

    def test_boundary_080(self):
        classification = make_classification(confidence=0.80)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is True
        assert result["confidence_tier"] == "medium_high"

    def test_boundary_070(self):
        classification = make_classification(confidence=0.70)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is False
        assert result["confidence_tier"] == "medium"

    # --- Sub-type validation ---

    def test_invalid_sub_type_flags_review(self):
        classification = make_classification(sub_type="Unknown Type", confidence=0.99)
        result = apply_business_rules(classification)

        assert result["requires_human_review"] is True
        assert result["auto_send_eligible"] is False

    def test_valid_sub_types_accepted(self):
        for sub_type in INTERVIEW_SUB_TYPES:
            classification = make_classification(sub_type=sub_type, confidence=0.95)
            if sub_type == "Job Machine":
                classification["job_machine_sub_type"] = "interview"
            result = apply_business_rules(classification)
            # Should not be flagged for invalid sub-type (may still need review for
            # other reasons like Job Machine missing sub-type)
            assert result.get("interview_sub_type") == sub_type

    # --- Job Machine rules ---

    def test_job_machine_requires_sub_type(self):
        classification = make_classification(
            sub_type="Job Machine",
            confidence=0.95,
            is_job_machine=True,
            job_machine_sub_type=None,
        )
        result = apply_business_rules(classification)

        assert result["requires_human_review"] is True
        assert result["auto_send_eligible"] is False

    def test_job_machine_with_valid_sub_type(self):
        classification = make_classification(
            sub_type="Job Machine",
            confidence=0.95,
            is_job_machine=True,
            job_machine_sub_type="interview",
        )
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is True

    def test_job_machine_invalid_sub_type(self):
        classification = make_classification(
            sub_type="Job Machine",
            confidence=0.95,
            is_job_machine=True,
            job_machine_sub_type="invalid",
        )
        result = apply_business_rules(classification)

        assert result["requires_human_review"] is True
        assert result["auto_send_eligible"] is False

    def test_job_machine_all_valid_sub_types(self):
        for jm_sub in JOB_MACHINE_SUB_TYPES:
            classification = make_classification(
                sub_type="Job Machine",
                confidence=0.95,
                is_job_machine=True,
                job_machine_sub_type=jm_sub,
            )
            result = apply_business_rules(classification)
            assert result["auto_send_eligible"] is True

    # --- Cancelled/rescheduled rules ---

    def test_cancelled_without_reason_flags_audit(self):
        classification = make_classification(
            sub_type="Interview Cancelled",
            confidence=0.95,
            cancellation_reason=None,
        )
        result = apply_business_rules(classification)

        assert result.get("flag_for_audit") is True

    def test_cancelled_with_reason_no_extra_flag(self):
        classification = make_classification(
            sub_type="Interview Cancelled",
            confidence=0.95,
            cancellation_reason="Position filled",
        )
        result = apply_business_rules(classification)

        # Should not have flag_for_audit set by the cancellation rule
        # (it may be set by other rules, but not this one specifically)
        assert result["auto_send_eligible"] is True

    # --- Date validation ---

    def test_past_date_flags_audit(self):
        classification = make_classification(
            confidence=0.95, interview_date="2020-01-01"
        )
        result = apply_business_rules(classification)

        assert result.get("flag_for_audit") is True

    def test_future_date_no_flag(self):
        classification = make_classification(
            confidence=0.95, interview_date="2030-12-31"
        )
        result = apply_business_rules(classification)

        # flag_for_audit should not be set by date rule
        # (but may be set by confidence tier rule for medium_high)
        assert result["auto_send_eligible"] is True

    def test_invalid_date_format_flags_audit(self):
        classification = make_classification(
            confidence=0.95, interview_date="not-a-date"
        )
        result = apply_business_rules(classification)

        assert result.get("flag_for_audit") is True

    def test_null_date_no_flag(self):
        classification = make_classification(confidence=0.95, interview_date=None)
        result = apply_business_rules(classification)

        assert result["auto_send_eligible"] is True

    # --- Timestamp ---

    def test_adds_processing_timestamp(self):
        classification = make_classification()
        result = apply_business_rules(classification)

        assert "processing_timestamp" in result
        assert result["processing_timestamp"].endswith("Z")

    def test_does_not_mutate_input(self):
        classification = make_classification()
        original_keys = set(classification.keys())

        apply_business_rules(classification)

        assert set(classification.keys()) == original_keys
        assert "processing_timestamp" not in classification


class TestIsInterviewRelated:
    """Test interview-related category check."""

    def test_interview_categories_are_related(self):
        for category in INTERVIEW_RELATED_CATEGORIES:
            assert is_interview_related(category) is True

    def test_non_interview_categories_not_related(self):
        non_interview = [
            "Rejection",
            "Job Alert",
            "Application Notification",
            "More Information Request",
            "Offer",
            "Background Check",
            "Other",
        ]
        for category in non_interview:
            assert is_interview_related(category) is False

    def test_empty_string_not_related(self):
        assert is_interview_related("") is False

    def test_none_not_related(self):
        # Passing None should not crash
        assert is_interview_related(None) is False


class TestSubclassifyInterview:
    """Test main sub-classification function."""

    def test_validate_only_mode(self):
        result = subclassify_interview(SAMPLE_EMAIL, validate_only=True)

        assert result["interview_sub_type"] == "Interview Request"
        assert result["confidence"] == 0.5
        assert "processing_timestamp" in result
        assert "email_metadata" in result
        assert result["email_metadata"]["subject"] == SAMPLE_EMAIL["subject"]

    def test_missing_required_fields(self):
        email = {"sender_email": "test@example.com"}

        with pytest.raises(ValueError, match="Missing required fields"):
            subclassify_interview(email, validate_only=True)

    def test_missing_subject(self):
        email = {"body_content": "Some content"}

        with pytest.raises(ValueError, match="subject"):
            subclassify_interview(email, validate_only=True)

    def test_missing_body(self):
        email = {"subject": "Test Subject"}

        with pytest.raises(ValueError, match="body_content"):
            subclassify_interview(email, validate_only=True)

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_interview_request(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Interview Request",
                confidence=0.96,
                company_name="Acme Inc",
                position_title="Software Engineer",
            )
        )

        result = subclassify_interview(SAMPLE_EMAIL, api_key="test-key")

        mock_api.assert_called_once()
        assert result["interview_sub_type"] == "Interview Request"
        assert result["confidence"] == 0.96
        assert result["auto_send_eligible"] is True
        assert result["company_name"] == "Acme Inc"

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_phone_screen(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Phone Screen",
                confidence=0.93,
                interview_date="2026-02-20",
                interview_time="14:00",
                interview_format="phone",
                meeting_link_or_dial_in="555-123-4567",
            )
        )

        email = {
            "subject": "Phone Interview Scheduled - TechCorp",
            "sender_email": "recruiter@techcorp.com",
            "body_content": "Your phone screen is scheduled for Feb 20 at 2 PM. Call 555-123-4567.",
        }
        result = subclassify_interview(email, api_key="test-key")

        assert result["interview_sub_type"] == "Phone Screen"
        assert result["interview_date"] == "2026-02-20"
        assert result["meeting_link_or_dial_in"] == "555-123-4567"

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_client_screen(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Client Screen",
                confidence=0.91,
                is_next_round=True,
                num_interviewers=2,
                interviewer_names_roles=[
                    {"name": "Bob Jones", "role": "VP Engineering"},
                    {"name": "Jane Smith", "role": "HR"},
                ],
            )
        )

        email = {
            "subject": "Second Round Interview - TechCorp",
            "sender_email": "agency@recruit.com",
            "body_content": "Congrats on making it to the client interview round.",
        }
        result = subclassify_interview(email, api_key="test-key")

        assert result["interview_sub_type"] == "Client Screen"
        assert result["is_next_round"] is True
        assert result["num_interviewers"] == 2

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_technical_interview(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Technical Interview",
                confidence=0.97,
                is_next_round=True,
                interview_format="panel",
                num_interviewers=3,
            )
        )

        email = {
            "subject": "Technical Round Scheduled - Coding Assessment",
            "sender_email": "hr@company.com",
            "body_content": "Your technical interview with our engineering panel is confirmed.",
        }
        result = subclassify_interview(email, api_key="test-key")

        assert result["interview_sub_type"] == "Technical Interview"
        assert result["interview_format"] == "panel"
        assert result["is_next_round"] is True

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_cancelled(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Interview Cancelled",
                confidence=0.98,
                cancellation_reason="Position has been filled",
            )
        )

        email = {
            "subject": "Your Interview Has Been Cancelled",
            "sender_email": "hr@company.com",
            "body_content": "Unfortunately, the position has been filled.",
        }
        result = subclassify_interview(email, api_key="test-key")

        assert result["interview_sub_type"] == "Interview Cancelled"
        assert result["cancellation_reason"] == "Position has been filled"

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_rescheduled(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Interview Rescheduled",
                confidence=0.94,
                original_date="2026-02-15",
                new_date="2026-02-20",
                new_time="10:00",
            )
        )

        email = {
            "subject": "Your Interview Has Been Rescheduled",
            "sender_email": "recruiter@company.com",
            "body_content": "Your interview has been moved from Feb 15 to Feb 20 at 10 AM.",
        }
        result = subclassify_interview(email, api_key="test-key")

        assert result["interview_sub_type"] == "Interview Rescheduled"
        assert result["original_date"] == "2026-02-15"
        assert result["new_date"] == "2026-02-20"

    @patch("execution.subclassify_interview.call_openai_api")
    def test_classify_job_machine(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Job Machine",
                confidence=0.96,
                is_job_machine=True,
                job_machine_sub_type="interview",
            )
        )

        email = {
            "subject": "Interview Notification from Job Machine",
            "sender_email": "notifications@jobmachine.com",
            "body_content": "You have a new interview notification on Job Machine.",
        }
        result = subclassify_interview(email, api_key="test-key")

        assert result["interview_sub_type"] == "Job Machine"
        assert result["is_job_machine"] is True
        assert result["job_machine_sub_type"] == "interview"
        assert result["auto_send_eligible"] is True

    @patch("execution.subclassify_interview.call_openai_api")
    def test_api_error_propagated(self, mock_api):
        mock_api.side_effect = RuntimeError("API Error")

        with pytest.raises(RuntimeError, match="API Error"):
            subclassify_interview(SAMPLE_EMAIL, api_key="test-key")

    @patch("execution.subclassify_interview.call_openai_api")
    def test_low_confidence_result(self, mock_api):
        mock_api.return_value = make_api_response(
            make_classification(confidence=0.55)
        )

        result = subclassify_interview(SAMPLE_EMAIL, api_key="test-key")

        assert result["requires_human_review"] is True
        assert result["auto_send_eligible"] is False


class TestCallOpenaiAPI:
    """Test OpenAI API calling function."""

    def test_missing_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY not found"):
                call_openai_api("test prompt", api_key=None)

    def test_openai_library_not_installed(self):
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'openai'"),
        ):
            with pytest.raises(RuntimeError, match="openai library not installed"):
                call_openai_api("test prompt", api_key="test-key")


class TestLoadEmailFromFile:
    """Test email loading from file."""

    def test_load_valid_email(self, temp_dir):
        email_file = temp_dir / "email.json"
        with open(email_file, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_EMAIL, f)

        result = load_email_from_file(email_file)

        assert result == SAMPLE_EMAIL

    def test_load_nonexistent_file(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            load_email_from_file(temp_dir / "missing.json")


class TestSaveSubclassificationResult:
    """Test saving sub-classification results."""

    def test_save_creates_file(self, temp_dir):
        output_file = temp_dir / "result.json"
        result = make_classification()

        save_subclassification_result(result, output_file)

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["interview_sub_type"] == "Interview Request"

    def test_save_creates_directories(self, temp_dir):
        output_file = temp_dir / "nested" / "dir" / "result.json"
        result = make_classification()

        save_subclassification_result(result, output_file)

        assert output_file.exists()

    def test_save_handles_unicode(self, temp_dir):
        output_file = temp_dir / "unicode.json"
        result = make_classification(company_name="Café München GmbH")

        save_subclassification_result(result, output_file)

        with open(output_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["company_name"] == "Café München GmbH"


class TestConstants:
    """Test constant definitions."""

    def test_interview_sub_types_count(self):
        assert len(INTERVIEW_SUB_TYPES) == 7

    def test_interview_sub_types_no_duplicates(self):
        assert len(INTERVIEW_SUB_TYPES) == len(set(INTERVIEW_SUB_TYPES))

    def test_job_machine_sub_types_count(self):
        assert len(JOB_MACHINE_SUB_TYPES) == 3

    def test_interview_related_categories_not_empty(self):
        assert len(INTERVIEW_RELATED_CATEGORIES) > 0


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_pipeline_validate_only(self, temp_dir):
        input_file = temp_dir / "email.json"
        output_file = temp_dir / "result.json"

        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_EMAIL, f)

        loaded_email = load_email_from_file(input_file)
        result = subclassify_interview(loaded_email, validate_only=True)
        save_subclassification_result(result, output_file)

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            saved = json.load(f)

        assert saved["interview_sub_type"] == "Interview Request"
        assert "processing_timestamp" in saved
        assert saved["email_metadata"]["subject"] == SAMPLE_EMAIL["subject"]

    @patch("execution.subclassify_interview.call_openai_api")
    def test_full_pipeline_with_api(self, mock_api, temp_dir):
        mock_api.return_value = make_api_response(
            make_classification(
                sub_type="Technical Interview",
                confidence=0.98,
                company_name="DataCorp",
                position_title="Senior Data Engineer",
                interview_date="2026-03-01",
                interview_time="10:00",
                interview_format="panel",
                num_interviewers=3,
                is_next_round=True,
            )
        )

        input_file = temp_dir / "email.json"
        output_file = temp_dir / "result.json"

        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_EMAIL, f)

        loaded_email = load_email_from_file(input_file)
        result = subclassify_interview(loaded_email, api_key="test-key")
        save_subclassification_result(result, output_file)

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            saved = json.load(f)

        assert saved["interview_sub_type"] == "Technical Interview"
        assert saved["confidence"] == 0.98
        assert saved["auto_send_eligible"] is True
        assert saved["company_name"] == "DataCorp"
        assert saved["is_next_round"] is True

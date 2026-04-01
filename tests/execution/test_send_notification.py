"""
Unit tests for send_notification.py

Tests SMTP email sending with mocked SMTP connections.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from email.mime.multipart import MIMEMultipart
import smtplib

from execution.send_notification import (
    validate_send_inputs,
    build_email_message,
    send_email,
    send_notification,
    BCC_ADDRESS,
)


# ============================================================================
# Input Validation Tests
# ============================================================================


class TestValidateSendInputs:
    """Test input validation before sending."""

    def test_valid_inputs(self):
        result = validate_send_inputs(
            "student@personal.com", "Subject", "Body"
        )
        assert result is None

    def test_empty_recipient(self):
        result = validate_send_inputs("", "Subject", "Body")
        assert result is not None
        assert "recipient" in result.lower()

    def test_none_recipient(self):
        result = validate_send_inputs(None, "Subject", "Body")
        assert result is not None

    def test_invalid_email_no_at(self):
        result = validate_send_inputs("notanemail", "Subject", "Body")
        assert result is not None
        assert "recipient" in result.lower()

    def test_empty_subject(self):
        result = validate_send_inputs("test@test.com", "", "Body")
        assert result is not None
        assert "subject" in result.lower()

    def test_whitespace_subject(self):
        result = validate_send_inputs("test@test.com", "   ", "Body")
        assert result is not None
        assert "subject" in result.lower()

    def test_empty_body(self):
        result = validate_send_inputs("test@test.com", "Subject", "")
        assert result is not None
        assert "body" in result.lower()

    def test_none_body(self):
        result = validate_send_inputs("test@test.com", "Subject", None)
        assert result is not None
        assert "body" in result.lower()


# ============================================================================
# Email Message Building Tests
# ============================================================================


class TestBuildEmailMessage:
    """Test MIME message construction."""

    def test_basic_message(self):
        msg = build_email_message(
            recipient_email="student@personal.com",
            subject="Interview Notification",
            body="Hello, you have an interview.",
        )

        assert isinstance(msg, MIMEMultipart)
        assert msg["To"] == "student@personal.com"
        assert msg["Subject"] == "Interview Notification"

    def test_message_with_sender(self):
        msg = build_email_message(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            from_name="Test Sender",
            from_email="sender@colaberry.com",
        )

        assert "Test Sender" in msg["From"]
        assert "sender@colaberry.com" in msg["From"]

    def test_message_with_bcc(self):
        msg = build_email_message(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            bcc="audit@colaberry.com",
        )

        assert msg["Bcc"] == "audit@colaberry.com"

    def test_message_without_bcc(self):
        msg = build_email_message(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
        )

        assert msg["Bcc"] is None

    def test_body_in_payload(self):
        msg = build_email_message(
            recipient_email="student@test.com",
            subject="Test",
            body="Hello World",
        )

        # Check that the body is in the message payload
        payload = msg.get_payload()
        assert len(payload) > 0
        body_part = payload[0]
        assert "Hello World" in body_part.get_payload(decode=True).decode()


# ============================================================================
# Send Email Tests (Mocked SMTP)
# ============================================================================


class TestSendEmail:
    """Test email sending with mocked SMTP."""

    @patch("execution.send_notification.smtplib.SMTP")
    def test_successful_send(self, mock_smtp_class):
        """Test successful email send."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            recipient_email="student@personal.com",
            subject="Phone Screen - TechCorp",
            body="Dear Student, you have an interview.",
            smtp_username="sender@colaberry.com",
            smtp_password="testpassword",
        )

        assert result["status"] == "sent"
        assert result["error"] is None
        assert result["recipient"] == "student@personal.com"
        assert result["timestamp"]

        # Verify SMTP interactions
        mock_smtp.ehlo.assert_called()
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("sender@colaberry.com", "testpassword")
        mock_smtp.sendmail.assert_called_once()

    @patch("execution.send_notification.smtplib.SMTP")
    def test_send_includes_bcc(self, mock_smtp_class):
        """Verify BCC address is included in recipients."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        send_email(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            bcc="audit@colaberry.com",
            smtp_username="sender@test.com",
            smtp_password="pass",
        )

        # Check that sendmail was called with both To and BCC recipients
        send_call = mock_smtp.sendmail.call_args
        to_addrs = send_call[1]["to_addrs"] if "to_addrs" in send_call[1] else send_call[0][1]
        assert "student@test.com" in to_addrs
        assert "audit@colaberry.com" in to_addrs

    def test_validation_error_no_recipient(self):
        """Test that invalid inputs return validation error without SMTP."""
        result = send_email(
            recipient_email="",
            subject="Test",
            body="Test body",
        )

        assert result["status"] == "validation_error"
        assert result["error"] is not None

    @patch("execution.send_notification.SMTP_USERNAME", "")
    @patch("execution.send_notification.SMTP_PASSWORD", "")
    def test_missing_smtp_credentials(self):
        """Test that missing SMTP credentials are caught."""
        result = send_email(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            smtp_username="",
            smtp_password="",
        )

        assert result["status"] == "failed"
        assert "SMTP credentials" in result["error"]

    @patch("execution.send_notification.smtplib.SMTP")
    def test_auth_error(self, mock_smtp_class):
        """Test SMTP authentication failure."""
        mock_smtp = MagicMock()
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"Authentication failed"
        )
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            smtp_username="sender@test.com",
            smtp_password="wrongpass",
        )

        assert result["status"] == "failed"
        assert "authentication" in result["error"].lower()

    @patch("execution.send_notification.smtplib.SMTP")
    def test_recipient_refused(self, mock_smtp_class):
        """Test recipient refused error."""
        mock_smtp = MagicMock()
        mock_smtp.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
            {"bad@email.com": (550, b"User not found")}
        )
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            recipient_email="bad@email.com",
            subject="Test",
            body="Test body",
            smtp_username="sender@test.com",
            smtp_password="pass",
        )

        assert result["status"] == "failed"
        assert "refused" in result["error"].lower()

    @patch("execution.send_notification.smtplib.SMTP")
    def test_connection_error(self, mock_smtp_class):
        """Test SMTP connection failure."""
        mock_smtp_class.side_effect = ConnectionError("Connection refused")

        result = send_email(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            smtp_username="sender@test.com",
            smtp_password="pass",
        )

        assert result["status"] == "failed"
        assert "connection" in result["error"].lower()

    @patch("execution.send_notification.smtplib.SMTP")
    def test_timeout_error(self, mock_smtp_class):
        """Test SMTP timeout."""
        mock_smtp_class.side_effect = TimeoutError("Timed out")

        result = send_email(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            smtp_username="sender@test.com",
            smtp_password="pass",
        )

        assert result["status"] == "failed"
        assert "timeout" in result["error"].lower()

    @patch("execution.send_notification.smtplib.SMTP")
    def test_custom_smtp_server(self, mock_smtp_class):
        """Test custom SMTP server parameters."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        send_email(
            recipient_email="student@test.com",
            subject="Test",
            body="Test body",
            smtp_server="custom.smtp.com",
            smtp_port=465,
            smtp_username="user@custom.com",
            smtp_password="pass",
        )

        mock_smtp_class.assert_called_once_with("custom.smtp.com", 465, timeout=30)


# ============================================================================
# Send Notification Wrapper Tests
# ============================================================================


class TestSendNotification:
    """Test the convenience wrapper for sending from draft dicts."""

    @patch("execution.send_notification.send_email")
    def test_send_from_draft(self, mock_send):
        mock_send.return_value = {"status": "sent", "message_id": "123"}

        draft = {
            "recipient_email": "student@personal.com",
            "email_subject": "Phone Screen - TechCorp",
            "email_body": "Dear Student, you have an interview.",
            "bcc": "c_interviews@colaberry.com",
        }

        result = send_notification(draft)

        mock_send.assert_called_once_with(
            recipient_email="student@personal.com",
            subject="Phone Screen - TechCorp",
            body="Dear Student, you have an interview.",
            bcc="c_interviews@colaberry.com",
        )
        assert result["status"] == "sent"

    @patch("execution.send_notification.send_email")
    def test_send_from_empty_draft(self, mock_send):
        mock_send.return_value = {
            "status": "validation_error",
            "error": "Invalid recipient",
        }

        result = send_notification({})

        mock_send.assert_called_once()
        assert result["status"] == "validation_error"

    @patch("execution.send_notification.send_email")
    def test_default_bcc(self, mock_send):
        """Verify default BCC is used when draft has no bcc field."""
        mock_send.return_value = {"status": "sent"}

        draft = {
            "recipient_email": "student@test.com",
            "email_subject": "Test",
            "email_body": "Body",
        }

        send_notification(draft)

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["bcc"] == BCC_ADDRESS

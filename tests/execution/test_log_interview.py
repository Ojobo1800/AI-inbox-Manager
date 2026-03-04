"""
Unit tests for log_interview.py

Tests interview event logging and notification draft persistence
using an in-memory SQLite database with test-local model definitions.

We define models locally to avoid importing the dashboard's database.py,
which triggers config.py Settings validation against the root .env file.
"""

import sys
import types
import pytest
from datetime import datetime

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Create a test-local Base for model definitions
TestBase = declarative_base()


# ============================================================================
# Test-local model definitions (mirror the dashboard models)
# ============================================================================


class Email(TestBase):
    __tablename__ = "emails"
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(String(255), unique=True, nullable=False)
    subject = Column(String(500), nullable=False)
    from_address = Column(String(255), nullable=False)
    received_date = Column(DateTime, nullable=False)
    body_preview = Column(String(500))
    full_body = Column(Text)
    current_folder = Column(String(100), default="INBOX")
    is_read = Column(Boolean, default=False)
    fetch_timestamp = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)


class Student(TestBase):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255))
    personal_email = Column(String(255))
    assigned_gmail = Column(String(255))
    phone_number = Column(String(50))
    drive_folder_id = Column(String(255))
    last_synced_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    interview_events = relationship("InterviewEvent", back_populates="student")


class InterviewEvent(TestBase):
    __tablename__ = "interview_events"
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"))
    sub_type = Column(String(100), nullable=False)
    company_name = Column(String(255))
    position_title = Column(String(255))
    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(100))
    interview_date = Column(String(20))
    interview_time = Column(String(10))
    interview_timezone = Column(String(20))
    interview_format = Column(String(50))
    meeting_link = Column(Text)
    num_interviewers = Column(Integer)
    is_job_machine = Column(Boolean, default=False)
    is_next_round = Column(Boolean, default=False)
    confidence = Column(Float, nullable=False)
    raw_extraction = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    email = relationship("Email")
    student = relationship("Student", back_populates="interview_events")
    notification_drafts = relationship(
        "NotificationDraft", back_populates="interview_event"
    )


class NotificationDraft(TestBase):
    __tablename__ = "notification_drafts"
    id = Column(Integer, primary_key=True, index=True)
    interview_event_id = Column(
        Integer, ForeignKey("interview_events.id"), nullable=False
    )
    template_id = Column(String(100))
    email_subject = Column(String(500))
    email_body = Column(Text)
    recipient_email = Column(String(255))
    email_status = Column(String(50), default="draft")
    auto_send_eligible = Column(Boolean, default=False)
    whatsapp_message = Column(Text)
    whatsapp_recipient_phone = Column(String(50))
    whatsapp_sender_phone = Column(String(50))
    whatsapp_status = Column(String(50), default="draft")
    missing_fields = Column(JSON)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    sent_at = Column(DateTime)
    send_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    interview_event = relationship(
        "InterviewEvent", back_populates="notification_drafts"
    )


# ============================================================================
# Mock the services.dashboard.api.models module
# ============================================================================

# Create a fake module with our test models so that log_interview.py's
# function-level imports resolve correctly without triggering config.py.
_mock_models = types.ModuleType("services.dashboard.api.models")
_mock_models.Student = Student
_mock_models.InterviewEvent = InterviewEvent
_mock_models.NotificationDraft = NotificationDraft
_mock_models.Email = Email

# Ensure the full module path exists in sys.modules
for mod_path in [
    "services",
    "services.dashboard",
    "services.dashboard.api",
]:
    if mod_path not in sys.modules:
        sys.modules[mod_path] = types.ModuleType(mod_path)

sys.modules["services.dashboard.api.models"] = _mock_models

from execution.log_interview import (
    upsert_student,
    log_interview_event,
    log_notification_draft,
    update_notification_status,
    update_whatsapp_status,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database with all tables for testing."""
    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create a sample email record (required for FK relationships)
    email = Email(
        email_id="test-email-001",
        subject="Interview at TechCorp",
        from_address="hr@techcorp.com",
        received_date=datetime(2026, 3, 1),
        body_preview="Phone screen scheduled",
        current_folder="INBOX",
    )
    session.add(email)
    session.commit()

    yield session

    session.close()


@pytest.fixture
def sample_email_id(db_session):
    """Return the ID of the sample email."""
    email = db_session.query(Email).first()
    return email.id


@pytest.fixture
def sample_classification():
    """Sample sub-classification result."""
    return {
        "interview_sub_type": "Phone Screen",
        "company_name": "TechCorp",
        "position_title": "Data Analyst",
        "contact_name": "Jane Smith",
        "contact_email": "jane@techcorp.com",
        "contact_phone": "555-1234",
        "interview_date": "2026-03-01",
        "interview_time": "14:00",
        "interview_timezone": "CST",
        "interview_format": "phone",
        "meeting_link_or_dial_in": "555-0000",
        "num_interviewers": 1,
        "is_job_machine": False,
        "is_next_round": False,
        "confidence": 0.95,
    }


@pytest.fixture
def sample_draft():
    """Sample notification draft result."""
    return {
        "template_id": "phone_screening_scheduled",
        "template_name": "Phone Screening Scheduled",
        "email_subject": "Phone Screen - TechCorp - Data Analyst",
        "email_body": "Dear John, you have a phone screen...",
        "recipient_email": "john@personal.com",
        "bcc": "c_interviews@colaberry.com",
        "missing_fields": [],
        "draft_status": "ready",
        "whatsapp_message": "Hi John! You have a phone screening with TechCorp.",
        "whatsapp_recipient_phone": "555-9999",
        "whatsapp_sender_phone": "214-607-8702",
    }


# ============================================================================
# Student Upsert Tests
# ============================================================================


class TestUpsertStudent:
    """Test student creation and update."""

    def test_create_new_student(self, db_session):
        result = upsert_student(
            db_session,
            username="john.doe",
            full_name="John Doe",
            personal_email="john@personal.com",
            assigned_gmail="john.doe@gmail.com",
            phone_number="555-9999",
        )

        assert result["created"] is True
        assert result["username"] == "john.doe"
        assert result["full_name"] == "John Doe"
        assert result["personal_email"] == "john@personal.com"
        assert result["assigned_gmail"] == "john.doe@gmail.com"
        assert result["id"] is not None

    def test_update_existing_student(self, db_session):
        # Create first
        upsert_student(
            db_session,
            username="john.doe",
            full_name="John Doe",
            personal_email="old@email.com",
        )

        # Update
        result = upsert_student(
            db_session,
            username="john.doe",
            personal_email="new@email.com",
            phone_number="555-0000",
        )

        assert result["created"] is False
        assert result["personal_email"] == "new@email.com"
        assert result["phone_number"] == "555-0000"
        # Name should remain from initial creation
        assert result["full_name"] == "John Doe"

    def test_update_preserves_existing_fields(self, db_session):
        """Fields not provided in update should not be overwritten."""
        upsert_student(
            db_session,
            username="jane.smith",
            full_name="Jane Smith",
            personal_email="jane@personal.com",
            assigned_gmail="jane.smith@gmail.com",
        )

        # Update only phone, other fields should remain
        result = upsert_student(
            db_session,
            username="jane.smith",
            phone_number="555-1111",
        )

        assert result["full_name"] == "Jane Smith"
        assert result["personal_email"] == "jane@personal.com"
        assert result["phone_number"] == "555-1111"

    def test_create_minimal_student(self, db_session):
        result = upsert_student(db_session, username="minimal.user")

        assert result["created"] is True
        assert result["username"] == "minimal.user"
        assert result["full_name"] is None
        assert result["personal_email"] is None

    def test_student_persisted_in_db(self, db_session):
        upsert_student(
            db_session,
            username="persisted.user",
            full_name="Persisted User",
        )

        # Verify by querying directly
        student = (
            db_session.query(Student)
            .filter(Student.username == "persisted.user")
            .first()
        )
        assert student is not None
        assert student.full_name == "Persisted User"
        assert student.is_active is True
        assert student.last_synced_at is not None


# ============================================================================
# Interview Event Logging Tests
# ============================================================================


class TestLogInterviewEvent:
    """Test interview event creation."""

    def test_log_event(self, db_session, sample_email_id, sample_classification):
        result = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )

        assert result["id"] is not None
        assert result["sub_type"] == "Phone Screen"
        assert result["company_name"] == "TechCorp"
        assert result["confidence"] == 0.95
        assert result["email_id"] == sample_email_id

    def test_log_event_with_student(
        self, db_session, sample_email_id, sample_classification
    ):
        # Create student first
        student = upsert_student(
            db_session,
            username="john.doe",
            full_name="John Doe",
        )

        result = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
            student_id=student["id"],
        )

        assert result["student_id"] == student["id"]

    def test_log_event_persisted(
        self, db_session, sample_email_id, sample_classification
    ):
        log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )

        event = db_session.query(InterviewEvent).first()
        assert event is not None
        assert event.sub_type == "Phone Screen"
        assert event.company_name == "TechCorp"
        assert event.position_title == "Data Analyst"
        assert event.contact_name == "Jane Smith"
        assert event.interview_date == "2026-03-01"
        assert event.interview_time == "14:00"
        assert event.interview_timezone == "CST"
        assert event.interview_format == "phone"
        assert event.meeting_link == "555-0000"
        assert event.num_interviewers == 1
        assert event.is_job_machine is False
        assert event.is_next_round is False
        assert event.confidence == 0.95
        assert event.raw_extraction is not None

    def test_log_event_minimal_classification(self, db_session, sample_email_id):
        minimal = {
            "interview_sub_type": "Interview Request",
            "confidence": 0.8,
        }

        result = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=minimal,
        )

        assert result["sub_type"] == "Interview Request"
        assert result["confidence"] == 0.8
        assert result["company_name"] is None

    def test_log_job_machine_event(self, db_session, sample_email_id):
        classification = {
            "interview_sub_type": "Job Machine",
            "job_machine_sub_type": "interview",
            "company_name": "Acme Corp",
            "is_job_machine": True,
            "confidence": 0.92,
        }

        result = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=classification,
        )

        event = db_session.query(InterviewEvent).get(result["id"])
        assert event.is_job_machine is True
        assert event.sub_type == "Job Machine"


# ============================================================================
# Notification Draft Logging Tests
# ============================================================================


class TestLogNotificationDraft:
    """Test notification draft creation."""

    def test_log_draft(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        # Create event first
        event = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )

        result = log_notification_draft(
            db_session,
            interview_event_id=event["id"],
            draft=sample_draft,
            auto_send_eligible=True,
        )

        assert result["id"] is not None
        assert result["interview_event_id"] == event["id"]
        assert result["template_id"] == "phone_screening_scheduled"
        assert result["recipient_email"] == "john@personal.com"
        assert result["email_status"] == "draft"
        assert result["auto_send_eligible"] is True

    def test_log_draft_persisted(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        event = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )

        log_notification_draft(
            db_session,
            interview_event_id=event["id"],
            draft=sample_draft,
        )

        draft = db_session.query(NotificationDraft).first()
        assert draft is not None
        assert draft.email_subject == "Phone Screen - TechCorp - Data Analyst"
        assert "phone screen" in draft.email_body.lower()
        assert draft.recipient_email == "john@personal.com"
        assert draft.whatsapp_message is not None
        assert draft.whatsapp_recipient_phone == "555-9999"
        assert draft.whatsapp_sender_phone == "214-607-8702"
        assert draft.whatsapp_status == "draft"
        assert draft.missing_fields == []

    def test_log_draft_with_missing_fields(
        self, db_session, sample_email_id, sample_classification
    ):
        event = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )

        draft = {
            "template_id": "phone_screening_scheduled",
            "email_subject": "Test",
            "email_body": "Test body",
            "recipient_email": "test@test.com",
            "missing_fields": ["contact_name", "interview_datetime"],
        }

        log_notification_draft(
            db_session,
            interview_event_id=event["id"],
            draft=draft,
            auto_send_eligible=False,
        )

        notification = db_session.query(NotificationDraft).first()
        assert notification.missing_fields == [
            "contact_name",
            "interview_datetime",
        ]
        assert notification.auto_send_eligible is False


# ============================================================================
# Notification Status Update Tests
# ============================================================================


class TestUpdateNotificationStatus:
    """Test notification status updates."""

    def _create_draft(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        """Helper to create an event and draft."""
        event = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )
        draft_result = log_notification_draft(
            db_session,
            interview_event_id=event["id"],
            draft=sample_draft,
        )
        return draft_result["id"]

    def test_mark_as_sent(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        draft_id = self._create_draft(
            db_session, sample_email_id, sample_classification, sample_draft
        )

        result = update_notification_status(
            db_session,
            notification_id=draft_id,
            email_status="sent",
        )

        assert result["email_status"] == "sent"
        assert result["sent_at"] is not None

    def test_mark_as_failed(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        draft_id = self._create_draft(
            db_session, sample_email_id, sample_classification, sample_draft
        )

        result = update_notification_status(
            db_session,
            notification_id=draft_id,
            email_status="failed",
            send_error="SMTP connection refused",
        )

        assert result["email_status"] == "failed"
        assert result["send_error"] == "SMTP connection refused"

    def test_mark_as_approved(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        draft_id = self._create_draft(
            db_session, sample_email_id, sample_classification, sample_draft
        )

        result = update_notification_status(
            db_session,
            notification_id=draft_id,
            email_status="approved",
            reviewed_by="admin",
        )

        assert result["email_status"] == "approved"
        assert result["reviewed_by"] == "admin"

    def test_mark_as_rejected(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        draft_id = self._create_draft(
            db_session, sample_email_id, sample_classification, sample_draft
        )

        result = update_notification_status(
            db_session,
            notification_id=draft_id,
            email_status="rejected",
            reviewed_by="admin",
        )

        assert result["email_status"] == "rejected"
        assert result["reviewed_by"] == "admin"

    def test_nonexistent_notification(self, db_session):
        result = update_notification_status(
            db_session,
            notification_id=9999,
            email_status="sent",
        )

        assert "error" in result


# ============================================================================
# WhatsApp Status Update Tests
# ============================================================================


class TestUpdateWhatsappStatus:
    """Test WhatsApp status updates."""

    def _create_draft(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        """Helper to create an event and draft."""
        event = log_interview_event(
            db_session,
            email_db_id=sample_email_id,
            classification=sample_classification,
        )
        draft_result = log_notification_draft(
            db_session,
            interview_event_id=event["id"],
            draft=sample_draft,
        )
        return draft_result["id"]

    def test_mark_as_copied(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        draft_id = self._create_draft(
            db_session, sample_email_id, sample_classification, sample_draft
        )

        result = update_whatsapp_status(
            db_session,
            notification_id=draft_id,
            whatsapp_status="copied",
        )

        assert result["whatsapp_status"] == "copied"

    def test_mark_as_sent(
        self, db_session, sample_email_id, sample_classification, sample_draft
    ):
        draft_id = self._create_draft(
            db_session, sample_email_id, sample_classification, sample_draft
        )

        result = update_whatsapp_status(
            db_session,
            notification_id=draft_id,
            whatsapp_status="sent",
        )

        assert result["whatsapp_status"] == "sent"

    def test_nonexistent_notification(self, db_session):
        result = update_whatsapp_status(
            db_session,
            notification_id=9999,
            whatsapp_status="sent",
        )

        assert "error" in result

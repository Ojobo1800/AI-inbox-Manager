"""
SQLAlchemy database models for the email management dashboard.

Defines all tables: emails, classifications, approvals, process_runs,
whitelist_companies, email_actions, user_sessions, system_config
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime,
    ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from database import Base


class Email(Base):
    """
    Stores email metadata and content.

    This table holds all emails fetched from the inbox, including
    their current classification and folder location.
    """
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(String(255), unique=True, nullable=False, index=True)  # Gmail UID
    subject = Column(String(500), nullable=False)
    from_address = Column(String(255), nullable=False)
    received_date = Column(DateTime, nullable=False, index=True)
    body_preview = Column(String(500))  # First 500 chars for quick display
    full_body = Column(Text)
    current_folder = Column(String(100), default="INBOX", index=True)
    is_read = Column(Boolean, default=False, index=True)
    fetch_timestamp = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    classifications = relationship("Classification", back_populates="email", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="email", cascade="all, delete-orphan")
    actions = relationship("EmailAction", back_populates="email", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_folder_read', 'current_folder', 'is_read'),
    )


class Classification(Base):
    """
    Stores AI classification results for emails.

    Each email can have multiple classifications (reclassifications),
    but only the most recent is typically used.
    """
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)  # 14 email categories
    confidence = Column(Float, nullable=False, index=True)  # 0.0 to 1.0
    company_name = Column(String(255))
    position = Column(String(255))
    classification_timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    classifier_version = Column(String(50), default="gpt-4o-2024-08-06")
    raw_response = Column(JSON)  # Store full AI response for debugging

    # Relationships
    email = relationship("Email", back_populates="classifications")
    approvals = relationship("Approval", back_populates="classification", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_category_confidence', 'category', 'confidence'),
    )


class Approval(Base):
    """
    Tracks human review and approval of email classifications.

    When an email has low confidence (<0.70) or needs manual review,
    an approval record is created. The human can approve, reject, or override.
    """
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    classification_id = Column(Integer, ForeignKey("classifications.id"), nullable=False)
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, overridden
    human_category = Column(String(100))  # If overridden
    human_action = Column(String(50))  # keep_inbox, move_to_folder, delete
    target_folder = Column(String(100))  # If moved
    reviewed_by = Column(String(100))  # username
    reviewed_at = Column(DateTime, index=True)
    notes = Column(Text)

    # Relationships
    email = relationship("Email", back_populates="approvals")
    classification = relationship("Classification", back_populates="approvals")

    # Indexes
    __table_args__ = (
        Index('idx_status', 'status'),
    )


class ProcessRun(Base):
    """
    Stores statistics and metadata for each automated processing run.

    Each time process_inbox_auto.py runs, a record is created here
    with summary statistics.
    """
    __tablename__ = "process_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    total_emails = Column(Integer, default=0)
    interview_requests = Column(Integer, default=0)
    organized = Column(Integer, default=0)
    spam_deleted = Column(Integer, default=0)
    categories_breakdown = Column(JSON)  # {"Job Alert": 5, "Rejection": 2, ...}
    duration_seconds = Column(Float)
    gpt_cost_usd = Column(Float, nullable=True)  # Actual GPT API cost for this run
    status = Column(String(50), default="success", index=True)  # success, partial_failure, failure
    error_log = Column(Text)

    # Indexes
    __table_args__ = (
        Index('idx_run_status', 'run_timestamp', 'status'),
    )


class WhitelistCompany(Base):
    """
    Stores companies that have sent genuine interview requests.

    These companies are protected - their emails are never moved or deleted
    regardless of AI classification.
    """
    __tablename__ = "whitelist_companies"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), unique=True, nullable=False, index=True)  # Normalized lowercase
    added_date = Column(DateTime, default=datetime.utcnow)
    added_by = Column(String(100), default="system")  # system or username
    notes = Column(Text)


class EmailAction(Base):
    """
    Audit trail of all actions performed on emails.

    Records every move, delete, reclassification, etc. for compliance
    and debugging purposes.
    """
    __tablename__ = "email_actions"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)  # moved, deleted, marked_read, reclassified
    from_folder = Column(String(100))
    to_folder = Column(String(100))
    performed_by = Column(String(100), nullable=False)  # system or username
    performed_at = Column(DateTime, default=datetime.utcnow, index=True)
    reason = Column(Text)

    # Relationships
    email = relationship("Email", back_populates="actions")

    # Indexes
    __table_args__ = (
        Index('idx_action_performed', 'action_type', 'performed_at'),
    )


class UserSession(Base):
    """
    Stores active user sessions for authentication.

    Session tokens are UUIDs stored in HTTP-only cookies.
    Sessions expire after 24 hours of inactivity.
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)  # UUID
    username = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False, default="stakeholder")  # admin or stakeholder
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_activity = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    """
    Stores student information synced from Google Drive.

    Each student has an assigned Gmail (used for job submissions,
    forwarded to c_interviews@colaberry.com) and a personal email
    (where notifications are sent).
    """
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)  # Drive folder name / Gmail username
    full_name = Column(String(255))
    personal_email = Column(String(255))  # WHERE WE SEND NOTIFICATIONS
    assigned_gmail = Column(String(255))  # The c_interviews-linked Gmail
    phone_number = Column(String(50))
    drive_folder_id = Column(String(255))
    last_synced_at = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    interview_events = relationship("InterviewEvent", back_populates="student", cascade="all, delete-orphan")


class InterviewEvent(Base):
    """
    Stores sub-classified interview events extracted from emails.

    Each interview email produces one InterviewEvent record with
    all extracted details (company, date, format, etc.).
    """
    __tablename__ = "interview_events"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    sub_type = Column(String(100), nullable=False, index=True)  # Phone Screen, Client Screen, etc.
    company_name = Column(String(255))
    position_title = Column(String(255))
    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(100))
    interview_date = Column(String(20))  # YYYY-MM-DD
    interview_time = Column(String(10))  # HH:MM
    interview_timezone = Column(String(20))
    interview_format = Column(String(50))  # phone / video / in-person / panel
    meeting_link = Column(Text)
    num_interviewers = Column(Integer)
    is_job_machine = Column(Boolean, default=False)
    is_next_round = Column(Boolean, default=False)
    confidence = Column(Float, nullable=False, index=True)
    raw_extraction = Column(JSON)  # Full AI extraction for audit
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    email = relationship("Email")
    student = relationship("Student", back_populates="interview_events")
    notification_drafts = relationship("NotificationDraft", back_populates="interview_event", cascade="all, delete-orphan")
    checklist_completions = relationship("ChecklistCompletion", back_populates="interview_event", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_interview_sub_type_date', 'sub_type', 'created_at'),
        Index('idx_interview_company', 'company_name'),
    )


class NotificationDraft(Base):
    """
    Stores notification drafts (email + WhatsApp) for interview events.

    Tracks the full lifecycle: draft → approved → sent (or rejected).
    """
    __tablename__ = "notification_drafts"

    id = Column(Integer, primary_key=True, index=True)
    interview_event_id = Column(Integer, ForeignKey("interview_events.id"), nullable=False, index=True)

    # Email notification
    template_id = Column(String(100))
    email_subject = Column(String(500))
    email_body = Column(Text)
    recipient_email = Column(String(255))  # Student's PERSONAL email
    email_status = Column(String(50), default="draft", index=True)  # draft, approved, sent, failed, rejected
    auto_send_eligible = Column(Boolean, default=False)

    # Review tracking
    missing_fields = Column(JSON)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    sent_at = Column(DateTime)
    send_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    interview_event = relationship("InterviewEvent", back_populates="notification_drafts")

    # Indexes
    __table_args__ = (
        Index('idx_draft_status', 'email_status', 'created_at'),
    )


class ChecklistCompletion(Base):
    """
    Tracks completion state of process checklist steps per interview event.

    Each interview event has a set of process steps determined by its sub_type.
    Step definitions are hardcoded in checklist_steps.py; only completion
    state is persisted here.
    """
    __tablename__ = "checklist_completions"

    id = Column(Integer, primary_key=True, index=True)
    interview_event_id = Column(Integer, ForeignKey("interview_events.id"), nullable=False, index=True)
    step_key = Column(String(100), nullable=False)  # e.g. "phone_screen.1.1"
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_by = Column(String(100))
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    interview_event = relationship("InterviewEvent", back_populates="checklist_completions")

    # Indexes
    __table_args__ = (
        Index('idx_checklist_event_step', 'interview_event_id', 'step_key', unique=True),
    )


class SystemConfig(Base):
    """
    Stores system-wide configuration key-value pairs.

    Used for runtime configuration that can be changed without
    redeploying the application.
    """
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100))

"""
Unit tests for process_inbox_auto.import_email_to_db().

Regression coverage for the 2026-08 bug where every classified email after
2026-06-29 silently failed to reach the dashboard database: the importer keyed
dedup on `email_id` (the IMAP message-sequence number, which repeats every run),
so new emails collided with old rows and were never inserted.

The fix keys dedup on the RFC 5322 Message-ID header instead.

Uses an in-memory SQLite database with test-local model definitions (same
pattern as test_log_interview.py) so nothing touches a real database.
"""

import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

# process_inbox_auto.py uses bare imports (`from fetch_emails import ...`) and is
# designed to run as a script from execution/. Mirror that here.
_EXECUTION_DIR = Path(__file__).resolve().parents[2] / "execution"
if str(_EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(_EXECUTION_DIR))
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

TestBase = declarative_base()


class Email(TestBase):
    __tablename__ = "emails"
    id = Column(Integer, primary_key=True)
    email_id = Column(String(255), nullable=False, index=True)  # IMAP seq no. — not unique
    message_id = Column(String(500), nullable=True, unique=True, index=True)
    subject = Column(String(500), nullable=False)
    from_address = Column(String(255), nullable=False)
    received_date = Column(DateTime, nullable=False)
    body_preview = Column(String(500))
    full_body = Column(Text)
    current_folder = Column(String(100), default="INBOX")
    is_read = Column(Boolean, default=False)
    fetch_timestamp = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    classifications = relationship("Classification", back_populates="email")


class Classification(TestBase):
    __tablename__ = "classifications"
    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    company_name = Column(String(255))
    position = Column(String(255))
    classification_timestamp = Column(DateTime, default=datetime.utcnow)
    classifier_version = Column(String(50))
    raw_response = Column(JSON)
    email = relationship("Email", back_populates="classifications")


import process_inbox_auto  # noqa: E402


@pytest.fixture
def db(monkeypatch):
    # Install a fake `models` module (scoped to the test, cleaned up after) so
    # import_email_to_db's function-level `from models import Email, Classification`
    # resolves to the test models without polluting other test files.
    mock_models = types.ModuleType("models")
    mock_models.Email = Email
    mock_models.Classification = Classification
    monkeypatch.setitem(sys.modules, "models", mock_models)

    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    monkeypatch.setattr(process_inbox_auto, "get_db_session", lambda: session)
    monkeypatch.setattr(process_inbox_auto, "_ensure_schema", lambda _engine: None)

    yield session
    session.close()


def _email(**over):
    base = {
        "subject": "Power BI Developer role",
        "sender_email": "jobs@indeed.com",
        "email_date": "Mon, 25 Aug 2026 10:00:00 -0400",
        "body_content": "We think you're a great fit.",
        "email_id": "42",  # IMAP sequence number
        "message_id": "<abc123@indeed.com>",
    }
    base.update(over)
    return base


def _clf(category="Job Alert", confidence=0.95, **extracted):
    return {
        "category": category,
        "confidence": confidence,
        "extracted_data": extracted or {"company_name": "Indeed", "position_title": "BI Dev"},
    }


def test_new_email_is_inserted_with_classification(db):
    eid = process_inbox_auto.import_email_to_db(_email(), _clf(), "Job Alerts")

    assert eid is not None
    row = db.get(Email, eid)
    assert row.message_id == "<abc123@indeed.com>"
    assert row.current_folder == "Job Alerts"
    assert row.from_address == "jobs@indeed.com"
    assert row.received_date == datetime(2026, 8, 25, 14, 0, 0)  # parsed to UTC-naive
    clf = db.query(Classification).filter_by(email_id=eid).one()
    assert clf.category == "Job Alert"
    assert clf.company_name == "Indeed"


def test_reprocessing_same_message_id_updates_not_duplicates(db):
    first = process_inbox_auto.import_email_to_db(_email(), _clf(), "Job Alerts")

    # Same email, next run: IMAP hands it a different sequence number, and the
    # classifier now routes it elsewhere.
    second = process_inbox_auto.import_email_to_db(
        _email(email_id="999"), _clf(category="Rejection", confidence=0.9), "Rejection"
    )

    assert second == first
    assert db.query(Email).count() == 1
    assert db.query(Classification).count() == 1
    row = db.get(Email, first)
    assert row.current_folder == "Rejection"
    assert row.email_id == "999"  # refreshed to the latest sequence number
    assert db.query(Classification).filter_by(email_id=first).one().category == "Rejection"


def test_sequence_number_collision_still_inserts_distinct_rows(db):
    """The original bug: two unrelated emails sharing an IMAP seq number."""
    a = process_inbox_auto.import_email_to_db(
        _email(email_id="10", message_id="<aaa@x.com>", subject="Email A"), _clf(), "Job Alerts"
    )
    b = process_inbox_auto.import_email_to_db(
        _email(email_id="10", message_id="<bbb@y.com>", subject="Email B"),
        _clf(category="Rejection"),
        "Rejection",
    )

    assert a is not None and b is not None and a != b
    assert db.query(Email).count() == 2


def test_email_without_message_id_dedupes_on_content(db):
    no_id = _email(message_id="")
    first = process_inbox_auto.import_email_to_db(no_id, _clf(), "Spam Review")
    second = process_inbox_auto.import_email_to_db(no_id, _clf(), "Spam Review")

    assert first is not None
    assert second == first
    assert db.query(Email).count() == 1


def test_returns_none_when_no_session(db, monkeypatch):
    monkeypatch.setattr(process_inbox_auto, "get_db_session", lambda: None)
    assert process_inbox_auto.import_email_to_db(_email(), _clf(), "Job Alerts") is None

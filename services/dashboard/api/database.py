"""
Database connection and session management.

Provides SQLAlchemy engine, session factory, and base model class.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.debug  # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create base model class
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.

    Usage in FastAPI endpoints:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        Database session that is automatically closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations() -> None:
    """
    Apply incremental schema changes that create_all() cannot handle
    (i.e., new columns added to existing tables).
    Safe to call every startup — each migration is idempotent.
    """
    with engine.connect() as conn:
        # process_runs.gpt_cost_usd  (added 2026-02)
        result = conn.execute(text("PRAGMA table_info(process_runs)"))
        columns = {row[1] for row in result.fetchall()}
        if "gpt_cost_usd" not in columns:
            conn.execute(text("ALTER TABLE process_runs ADD COLUMN gpt_cost_usd REAL"))
            conn.commit()


def init_db():
    """
    Initialize the database by creating all tables.

    This should be called on application startup to ensure
    all tables exist before the application starts handling requests.
    """
    from models import (
        Email, Classification, Approval, ProcessRun,
        WhitelistCompany, EmailAction, UserSession, SystemConfig,
        Student, InterviewEvent, NotificationDraft, ChecklistCompletion
    )
    Base.metadata.create_all(bind=engine)
    _run_migrations()

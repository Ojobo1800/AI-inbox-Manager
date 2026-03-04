"""
Summary file importer for automated processing runs.

Monitors tmp/auto_process_* directories for summary.json files
and imports them into the database.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models import ProcessRun, Email, Classification, WhitelistCompany
from config import settings

logger = logging.getLogger(__name__)


def import_summary_file(db: Session, summary_file: Path) -> Optional[ProcessRun]:
    """
    Import a single summary.json file into the database.

    Args:
        db: Database session
        summary_file: Path to summary.json file

    Returns:
        ProcessRun object if imported, None if already exists or error

    Raises:
        Exception: If file format is invalid
    """
    logger.info(f"Importing summary file: {summary_file}")

    try:
        with open(summary_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading summary file {summary_file}: {e}")
        raise

    # Extract data
    stats = data.get("statistics", {})
    timestamp_str = stats.get("timestamp", "")
    processing_timestamp_str = data.get("processing_timestamp", "")

    # Parse timestamp from folder name (e.g., auto_process_20260128_082111)
    try:
        run_timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
    except ValueError:
        logger.error(f"Invalid timestamp format in {summary_file}: {timestamp_str}")
        return None

    # Check if already imported
    existing = db.query(ProcessRun).filter(
        ProcessRun.run_timestamp == run_timestamp
    ).first()

    if existing:
        logger.debug(f"Summary file already imported: {summary_file}")
        return None

    # Create ProcessRun record
    process_run = ProcessRun(
        run_timestamp=run_timestamp,
        total_emails=stats.get("total_emails", 0),
        interview_requests=stats.get("interview_requests", 0),
        organized=stats.get("organized", 0),
        spam_deleted=stats.get("spam_deleted", 0),
        categories_breakdown=stats.get("categories", {}),
        status="success"  # If summary exists, processing was successful
    )

    db.add(process_run)

    # Import interview requests metadata (optional - doesn't fetch full emails)
    interview_requests = data.get("interview_requests", [])
    for ir_data in interview_requests:
        subject = ir_data.get("subject", "")
        company = ir_data.get("company")
        confidence = ir_data.get("confidence", 0.0)
        safety_protected = ir_data.get("safety_protected", False)

        logger.debug(
            f"Interview request detected: {company} - {subject[:50]} "
            f"(confidence: {confidence:.2f}, protected: {safety_protected})"
        )

        # If company was safety-protected, ensure it's in whitelist
        if safety_protected and company:
            add_to_whitelist(db, company, "Detected in automated processing")

    db.commit()
    db.refresh(process_run)

    logger.info(
        f"Imported summary: {stats['total_emails']} emails, "
        f"{stats['interview_requests']} interview requests"
    )

    return process_run


def import_all_summaries(db: Session, tmp_dir: Optional[Path] = None) -> List[ProcessRun]:
    """
    Import all unprocessed summary.json files.

    Args:
        db: Database session
        tmp_dir: Path to tmp directory (defaults to project tmp/)

    Returns:
        List of imported ProcessRun objects
    """
    if tmp_dir is None:
        tmp_dir = Path(__file__).parent.parent.parent.parent.parent / "tmp"

    logger.info(f"Scanning for summary files in: {tmp_dir}")

    if not tmp_dir.exists():
        logger.warning(f"tmp directory does not exist: {tmp_dir}")
        return []

    # Find all summary.json files
    summary_files = list(tmp_dir.glob("auto_process_*/summary.json"))
    logger.info(f"Found {len(summary_files)} summary files")

    # Import each one
    imported_runs = []
    for summary_file in summary_files:
        try:
            process_run = import_summary_file(db, summary_file)
            if process_run:
                imported_runs.append(process_run)
        except Exception as e:
            logger.error(f"Error importing {summary_file}: {e}")
            continue

    logger.info(f"Imported {len(imported_runs)} new process runs")
    return imported_runs


def get_latest_process_run(db: Session) -> Optional[ProcessRun]:
    """
    Get the most recent process run.

    Args:
        db: Database session

    Returns:
        Latest ProcessRun or None
    """
    return db.query(ProcessRun).order_by(
        ProcessRun.run_timestamp.desc()
    ).first()


def get_process_runs_since(db: Session, since: datetime) -> List[ProcessRun]:
    """
    Get all process runs since a given timestamp.

    Args:
        db: Database session
        since: Timestamp to filter from

    Returns:
        List of ProcessRun objects
    """
    return db.query(ProcessRun).filter(
        ProcessRun.run_timestamp >= since
    ).order_by(
        ProcessRun.run_timestamp.desc()
    ).all()


def add_to_whitelist(
    db: Session,
    company_name: str,
    notes: str,
    added_by: str = "system"
) -> WhitelistCompany:
    """
    Add a company to the whitelist if not already present.

    Args:
        db: Database session
        company_name: Company name to add (will be normalized to lowercase)
        notes: Reason for adding
        added_by: Who added it (system or username)

    Returns:
        WhitelistCompany object (existing or new)
    """
    # Normalize company name
    normalized_name = company_name.lower().strip()

    # Check if already exists
    existing = db.query(WhitelistCompany).filter(
        WhitelistCompany.company_name == normalized_name
    ).first()

    if existing:
        logger.debug(f"Company already in whitelist: {normalized_name}")
        return existing

    # Add new entry
    whitelist_entry = WhitelistCompany(
        company_name=normalized_name,
        added_by=added_by,
        added_date=datetime.utcnow(),
        notes=notes
    )

    db.add(whitelist_entry)
    db.commit()
    db.refresh(whitelist_entry)

    logger.info(f"Added company to whitelist: {normalized_name}")

    return whitelist_entry


def get_whitelist(db: Session) -> List[WhitelistCompany]:
    """
    Get all whitelisted companies.

    Args:
        db: Database session

    Returns:
        List of WhitelistCompany objects
    """
    return db.query(WhitelistCompany).order_by(
        WhitelistCompany.added_date.desc()
    ).all()


def remove_from_whitelist(db: Session, company_id: int) -> bool:
    """
    Remove a company from the whitelist.

    Args:
        db: Database session
        company_id: WhitelistCompany ID to remove

    Returns:
        True if removed, False if not found
    """
    company = db.query(WhitelistCompany).filter(
        WhitelistCompany.id == company_id
    ).first()

    if not company:
        return False

    logger.info(f"Removing company from whitelist: {company.company_name}")
    db.delete(company)
    db.commit()

    return True

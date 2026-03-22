"""
Integration wrapper for fetch_emails.py

Provides a clean interface to fetch emails from IMAP and store them in the database.
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

# Add execution directory to path
execution_path = Path(__file__).parent.parent.parent.parent.parent / "execution"
sys.path.insert(0, str(execution_path))

try:
    from fetch_emails import fetch_emails as fetch_emails_imap, EmailConnectionError, EmailFetchError
    FETCHER_AVAILABLE = True
except ImportError:
    fetch_emails_imap = None
    EmailConnectionError = Exception
    EmailFetchError = Exception
    FETCHER_AVAILABLE = False
from config import settings
from models import Email

logger = logging.getLogger(__name__)


def fetch_and_store_emails(
    db: Session,
    folder: str = "INBOX",
    criteria: str = "ALL",
    mark_as_read: bool = False,
    limit: Optional[int] = None
) -> List[Email]:
    """
    Fetch emails from IMAP and store them in the database.

    Args:
        db: Database session
        folder: IMAP folder to fetch from (default: INBOX)
        criteria: IMAP search criteria (ALL, UNSEEN, etc.)
        mark_as_read: Whether to mark emails as read
        limit: Maximum number of emails to fetch

    Returns:
        List of Email objects stored in database

    Raises:
        EmailConnectionError: If cannot connect to IMAP server
        EmailFetchError: If error fetching emails
    """
    logger.info(f"Fetching emails from {folder} with criteria: {criteria}")

    # Fetch emails from IMAP
    try:
        email_data_list = fetch_emails_imap(
            server=settings.email_server,
            port=settings.email_port,
            email_address=settings.email_address,
            password=settings.email_password,
            folder=folder,
            criteria=criteria,
            mark_as_read=mark_as_read
        )
    except Exception as e:
        logger.error(f"Error fetching emails from IMAP: {e}")
        raise

    if not email_data_list:
        logger.info("No emails fetched")
        return []

    logger.info(f"Fetched {len(email_data_list)} emails from IMAP")

    # Apply limit if specified
    if limit:
        email_data_list = email_data_list[:limit]

    # Store in database
    stored_emails = []
    for email_data in email_data_list:
        try:
            # Check if email already exists
            email_id = email_data.get("email_id")
            existing_email = db.query(Email).filter(Email.email_id == email_id).first()

            if existing_email:
                # Update existing email
                existing_email.subject = email_data.get("subject", "No Subject")
                existing_email.from_address = email_data.get("from", "Unknown")
                existing_email.received_date = email_data.get("date", datetime.utcnow())
                existing_email.body_preview = email_data.get("body", "")[:500]
                existing_email.full_body = email_data.get("body", "")
                existing_email.current_folder = folder
                existing_email.is_read = mark_as_read
                existing_email.last_updated = datetime.utcnow()
                stored_emails.append(existing_email)
                logger.debug(f"Updated existing email: {email_id}")
            else:
                # Create new email
                new_email = Email(
                    email_id=email_id,
                    subject=email_data.get("subject", "No Subject"),
                    from_address=email_data.get("from", "Unknown"),
                    received_date=email_data.get("date", datetime.utcnow()),
                    body_preview=email_data.get("body", "")[:500],
                    full_body=email_data.get("body", ""),
                    current_folder=folder,
                    is_read=mark_as_read,
                    fetch_timestamp=datetime.utcnow()
                )
                db.add(new_email)
                stored_emails.append(new_email)
                logger.debug(f"Created new email: {email_id}")

        except Exception as e:
            logger.error(f"Error storing email {email_data.get('email_id')}: {e}")
            continue

    # Commit all changes
    db.commit()

    logger.info(f"Stored {len(stored_emails)} emails in database")
    return stored_emails


def get_current_inbox_state(db: Session) -> List[Email]:
    """
    Fetch current INBOX state from IMAP and sync with database.

    This is useful for real-time monitoring of inbox state.

    Args:
        db: Database session

    Returns:
        List of Email objects representing current inbox state
    """
    return fetch_and_store_emails(
        db=db,
        folder="INBOX",
        criteria="ALL",
        mark_as_read=False
    )


def get_unread_emails(db: Session) -> List[Email]:
    """
    Fetch only unread emails from inbox.

    Args:
        db: Database session

    Returns:
        List of unread Email objects
    """
    return fetch_and_store_emails(
        db=db,
        folder="INBOX",
        criteria="UNSEEN",
        mark_as_read=False
    )

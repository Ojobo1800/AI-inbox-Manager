"""
Integration wrapper for classify_email.py

Provides interface to classify emails using OpenAI and store results in database.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

# Add execution directory to path
execution_path = Path(__file__).parent.parent.parent.parent.parent / "execution"
sys.path.insert(0, str(execution_path))

from classify_email import classify_email as classify_email_ai
from models import Email, Classification, Approval

logger = logging.getLogger(__name__)


def classify_and_store(
    db: Session,
    email: Email,
    validate_only: bool = False
) -> Classification:
    """
    Classify an email using AI and store the result in database.

    Args:
        db: Database session
        email: Email object to classify
        validate_only: If True, only validates email format (no AI call)

    Returns:
        Classification object stored in database
    """
    logger.info(f"Classifying email: {email.email_id}")

    # Prepare email data for classifier
    email_data = {
        "email_id": email.email_id,
        "subject": email.subject,
        "from": email.from_address,
        "body": email.full_body,
        "date": email.received_date
    }

    # Call AI classifier
    try:
        classification_result = classify_email_ai(email_data, validate_only=validate_only)
    except Exception as e:
        logger.error(f"Error classifying email {email.email_id}: {e}")
        raise

    # Store classification in database
    classification = Classification(
        email_id=email.id,
        category=classification_result.get("category"),
        confidence=classification_result.get("confidence", 0.0),
        company_name=classification_result.get("extracted_data", {}).get("company_name"),
        position=classification_result.get("extracted_data", {}).get("position"),
        classification_timestamp=datetime.utcnow(),
        classifier_version="gpt-4o-2024-08-06",
        raw_response=classification_result
    )

    db.add(classification)
    db.commit()
    db.refresh(classification)

    logger.info(
        f"Email {email.email_id} classified as {classification.category} "
        f"(confidence: {classification.confidence:.2f})"
    )

    # Check if approval needed (confidence < 0.70)
    if classification.confidence < 0.70:
        create_approval_request(db, email, classification)

    return classification


def create_approval_request(
    db: Session,
    email: Email,
    classification: Classification
) -> Approval:
    """
    Create an approval request for a low-confidence classification.

    Args:
        db: Database session
        email: Email object
        classification: Classification object

    Returns:
        Approval object created
    """
    logger.info(
        f"Creating approval request for email {email.email_id} "
        f"(confidence: {classification.confidence:.2f})"
    )

    # Check if approval already exists
    existing = db.query(Approval).filter(
        Approval.email_id == email.id,
        Approval.classification_id == classification.id,
        Approval.status == "pending"
    ).first()

    if existing:
        logger.debug(f"Approval already exists for email {email.email_id}")
        return existing

    # Create new approval request
    approval = Approval(
        email_id=email.id,
        classification_id=classification.id,
        status="pending"
    )

    db.add(approval)
    db.commit()
    db.refresh(approval)

    logger.info(f"Created approval request ID {approval.id}")
    return approval


def reclassify_email(db: Session, email: Email) -> Classification:
    """
    Re-classify an existing email (e.g., after user override).

    Args:
        db: Database session
        email: Email object to reclassify

    Returns:
        New Classification object
    """
    logger.info(f"Re-classifying email: {email.email_id}")
    return classify_and_store(db, email, validate_only=False)


def get_latest_classification(db: Session, email: Email) -> Classification:
    """
    Get the most recent classification for an email.

    Args:
        db: Database session
        email: Email object

    Returns:
        Latest Classification object or None
    """
    return db.query(Classification).filter(
        Classification.email_id == email.id
    ).order_by(
        Classification.classification_timestamp.desc()
    ).first()

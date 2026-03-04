"""
Email manual action API endpoints.

Handles manual classification, moving, deleting, and marking emails.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from auth import get_current_user
from models import Email, UserSession
from integration.email_classifier import classify_and_store, reclassify_email
from integration.email_actions import move_email, delete_email, mark_email_read

router = APIRouter()


# Pydantic models
class ClassifyResponse(BaseModel):
    email_id: int
    category: str
    confidence: float
    company_name: Optional[str]
    position: Optional[str]


class MoveRequest(BaseModel):
    target_folder: str


class MarkReadRequest(BaseModel):
    mark_as_read: bool


@router.post("/{email_id}/classify", response_model=ClassifyResponse)
async def classify_email_endpoint(
    email_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Manually classify or re-classify an email.

    Triggers AI classification and stores the result.

    Args:
        email_id: Email database ID

    Returns:
        Classification result

    Raises:
        HTTPException: If email not found or classification fails
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    try:
        classification = reclassify_email(db, email)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error classifying email: {str(e)}"
        )

    return ClassifyResponse(
        email_id=email.id,
        category=classification.category,
        confidence=classification.confidence,
        company_name=classification.company_name,
        position=classification.position
    )


@router.post("/{email_id}/move")
async def move_email_endpoint(
    email_id: int,
    request: MoveRequest,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Move an email to a different folder.

    Args:
        email_id: Email database ID
        request: Target folder name

    Returns:
        Success message with action details

    Raises:
        HTTPException: If email not found or move fails
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    try:
        action = move_email(
            db=db,
            email=email,
            target_folder=request.target_folder,
            performed_by=user.username,
            reason=f"Manual move via dashboard by {user.username}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error moving email: {str(e)}"
        )

    return {
        "message": "Email moved successfully",
        "email_id": email.id,
        "from_folder": action.from_folder,
        "to_folder": action.to_folder,
        "action_id": action.id
    }


@router.post("/{email_id}/delete")
async def delete_email_endpoint(
    email_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Delete an email permanently.

    Args:
        email_id: Email database ID
        reason: Optional reason for deletion

    Returns:
        Success message with action details

    Raises:
        HTTPException: If email not found or deletion fails
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    try:
        action = delete_email(
            db=db,
            email=email,
            performed_by=user.username,
            reason=reason or f"Manual deletion via dashboard by {user.username}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting email: {str(e)}"
        )

    return {
        "message": "Email deleted successfully",
        "email_id": email.id,
        "action_id": action.id
    }


@router.post("/{email_id}/mark-read")
async def mark_email_read_endpoint(
    email_id: int,
    request: MarkReadRequest,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Mark an email as read or unread.

    Args:
        email_id: Email database ID
        request: Whether to mark as read (true) or unread (false)

    Returns:
        Success message

    Raises:
        HTTPException: If email not found
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    try:
        action = mark_email_read(
            db=db,
            email=email,
            performed_by=user.username,
            mark_as_read=request.mark_as_read
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error marking email: {str(e)}"
        )

    status_text = "read" if request.mark_as_read else "unread"

    return {
        "message": f"Email marked as {status_text}",
        "email_id": email.id,
        "is_read": email.is_read,
        "action_id": action.id
    }

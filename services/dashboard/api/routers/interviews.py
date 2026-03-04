"""
Interview requests API endpoints.

Provides access to detected interview requests.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date

from database import get_db
from auth import get_current_user
from models import Email, Classification, UserSession, InterviewEvent, Student
from checklist_steps import normalize_sub_type

router = APIRouter()


# Pydantic models
class InterviewRequest(BaseModel):
    id: int
    email_id: str
    subject: str
    from_address: str
    received_date: datetime
    company_name: Optional[str]
    position: Optional[str]
    confidence: float
    classification_timestamp: datetime
    body_preview: str
    current_folder: str
    is_read: bool
    student_name: Optional[str] = None
    interview_type: Optional[str] = None
    interview_date: Optional[str] = None
    interview_time: Optional[str] = None
    contact_name: Optional[str] = None
    interview_event_id: Optional[int] = None

    class Config:
        from_attributes = True


class UpcomingInterview(BaseModel):
    interview_event_id: int
    student_name: Optional[str]
    company_name: Optional[str]
    position: Optional[str]
    interview_type: Optional[str]
    interview_date: Optional[str]
    interview_time: Optional[str]
    interview_timezone: Optional[str]
    interview_format: Optional[str]
    meeting_link: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]

    class Config:
        from_attributes = True


@router.get("/upcoming", response_model=List[UpcomingInterview])
async def get_upcoming_interviews(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get interviews scheduled for today or in the future (have an interview_date set).

    Returns events ordered by interview_date ascending so the soonest appears first.
    """
    today_str = date.today().isoformat()  # "YYYY-MM-DD"

    results = db.query(InterviewEvent, Student).outerjoin(
        Student, InterviewEvent.student_id == Student.id
    ).filter(
        InterviewEvent.interview_date != None,
        InterviewEvent.interview_date >= today_str
    ).order_by(
        InterviewEvent.interview_date.asc(),
        InterviewEvent.interview_time.asc()
    ).all()

    upcoming = []
    for event, student in results:
        upcoming.append(UpcomingInterview(
            interview_event_id=event.id,
            student_name=student.full_name if student else "Unknown",
            company_name=event.company_name,
            position=event.position_title,
            interview_type=normalize_sub_type(event.sub_type),
            interview_date=event.interview_date,
            interview_time=event.interview_time,
            interview_timezone=event.interview_timezone,
            interview_format=event.interview_format,
            meeting_link=event.meeting_link,
            contact_name=event.contact_name,
            contact_email=event.contact_email,
        ))

    return upcoming


@router.get("/", response_model=List[InterviewRequest])
async def get_interview_requests(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get all detected interview requests.

    Args:
        limit: Number of records to return (1-200)
        offset: Number of records to skip

    Returns:
        List of interview requests with email and classification data
    """
    # Query for emails classified as Interview Request
    # Also join with InterviewEvent and Student to get extracted details
    results = db.query(Email, Classification, InterviewEvent, Student).join(
        Classification, Email.id == Classification.email_id
    ).outerjoin(
        InterviewEvent, Email.id == InterviewEvent.email_id
    ).outerjoin(
        Student, InterviewEvent.student_id == Student.id
    ).filter(
        Classification.category == "Interview Request"
    ).order_by(
        desc(Email.received_date)
    ).limit(limit).offset(offset).all()

    # Convert to response model
    interview_requests = []
    for email, classification, interview_event, student in results:
        interview_requests.append(InterviewRequest(
            id=email.id,
            email_id=email.email_id,
            subject=email.subject,
            from_address=email.from_address,
            received_date=email.received_date,
            company_name=classification.company_name,
            position=classification.position or (interview_event.position_title if interview_event else None),
            confidence=classification.confidence,
            classification_timestamp=classification.classification_timestamp,
            body_preview=email.body_preview or "",
            current_folder=email.current_folder,
            student_name=student.full_name if student else "Unknown",
            interview_type=normalize_sub_type(interview_event.sub_type) if interview_event else None,
            interview_date=interview_event.interview_date if interview_event else None,
            interview_time=interview_event.interview_time if interview_event else None,
            contact_name=interview_event.contact_name if interview_event else None,
            interview_event_id=interview_event.id if interview_event else None,
            is_read=email.is_read
        ))

    return interview_requests


@router.get("/count")
async def get_interview_count(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get total count of interview requests.

    Returns:
        Total count of emails classified as Interview Request
    """
    count = db.query(Email).join(
        Classification, Email.id == Classification.email_id
    ).filter(
        Classification.category == "Interview Request"
    ).count()

    return {"count": count}


@router.get("/{email_id}")
async def get_interview_detail(
    email_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get full details of a specific interview request.

    Args:
        email_id: Email database ID

    Returns:
        Full email content and classification details
    """
    result = db.query(Email, Classification).join(
        Classification, Email.id == Classification.email_id
    ).filter(
        and_(
            Email.id == email_id,
            Classification.category == "Interview Request"
        )
    ).first()

    if not result:
        return {"error": "Interview request not found"}

    email, classification = result

    return {
        "id": email.id,
        "email_id": email.email_id,
        "subject": email.subject,
        "from_address": email.from_address,
        "received_date": email.received_date.isoformat(),
        "full_body": email.full_body,
        "company_name": classification.company_name,
        "position": classification.position,
        "confidence": classification.confidence,
        "classification_timestamp": classification.classification_timestamp.isoformat(),
        "current_folder": email.current_folder,
        "is_read": email.is_read
    }

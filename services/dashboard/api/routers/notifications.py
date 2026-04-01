"""
Notification management API endpoints.

Provides endpoints for viewing, approving, rejecting, and sending
interview notification drafts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from database import get_db
from auth import get_current_user
from models import (
    NotificationDraft,
    InterviewEvent,
    Student,
    Email,
    UserSession,
)

router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================


class NotificationSummary(BaseModel):
    """Summary view of a notification draft."""

    id: int
    interview_event_id: int
    template_id: Optional[str]
    email_subject: Optional[str]
    recipient_email: Optional[str]
    email_status: str
    auto_send_eligible: bool
    missing_fields: Optional[list]
    created_at: Optional[datetime]

    # From InterviewEvent
    sub_type: Optional[str] = None
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    confidence: Optional[float] = None

    # From Student
    student_name: Optional[str] = None
    student_username: Optional[str] = None

    class Config:
        from_attributes = True


class NotificationDetail(BaseModel):
    """Full detail view of a notification draft."""

    id: int
    interview_event_id: int

    # Email notification
    template_id: Optional[str]
    email_subject: Optional[str]
    email_body: Optional[str]
    recipient_email: Optional[str]
    email_status: str
    auto_send_eligible: bool

    # Review tracking
    missing_fields: Optional[list]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    sent_at: Optional[datetime]
    send_error: Optional[str]
    created_at: Optional[datetime]

    # Interview details
    sub_type: Optional[str] = None
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    interview_date: Optional[str] = None
    interview_time: Optional[str] = None
    interview_timezone: Optional[str] = None
    interview_format: Optional[str] = None
    confidence: Optional[float] = None
    is_job_machine: Optional[bool] = None

    # Student details
    student_name: Optional[str] = None
    student_username: Optional[str] = None
    student_personal_email: Optional[str] = None
    student_assigned_gmail: Optional[str] = None
    student_phone: Optional[str] = None

    # Source email
    email_db_id: Optional[int] = None
    email_subject_original: Optional[str] = None

    class Config:
        from_attributes = True


class EditDraftRequest(BaseModel):
    """Request to edit and optionally send a notification draft."""

    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    recipient_email: Optional[str] = None
    send_after_edit: bool = False


class RejectRequest(BaseModel):
    """Request to reject a notification draft."""

    reason: Optional[str] = None


class StudentResponse(BaseModel):
    """Student info response."""

    id: int
    username: str
    full_name: Optional[str]
    personal_email: Optional[str]
    assigned_gmail: Optional[str]
    phone_number: Optional[str]
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# Helper Functions
# ============================================================================


def _build_notification_summary(
    draft: NotificationDraft,
    event: Optional[InterviewEvent] = None,
    student: Optional[Student] = None,
) -> dict:
    """Build a summary dict from ORM objects."""
    data = {
        "id": draft.id,
        "interview_event_id": draft.interview_event_id,
        "template_id": draft.template_id,
        "email_subject": draft.email_subject,
        "recipient_email": draft.recipient_email,
        "email_status": draft.email_status,
        "auto_send_eligible": draft.auto_send_eligible,
        "missing_fields": draft.missing_fields,
        "created_at": draft.created_at,
    }
    if event:
        data["sub_type"] = event.sub_type
        data["company_name"] = event.company_name
        data["position_title"] = event.position_title
        data["confidence"] = event.confidence
    if student:
        data["student_name"] = student.full_name
        data["student_username"] = student.username
    return data


def _build_notification_detail(
    draft: NotificationDraft,
    event: Optional[InterviewEvent] = None,
    student: Optional[Student] = None,
    email: Optional[Email] = None,
) -> dict:
    """Build a full detail dict from ORM objects."""
    data = {
        "id": draft.id,
        "interview_event_id": draft.interview_event_id,
        "template_id": draft.template_id,
        "email_subject": draft.email_subject,
        "email_body": draft.email_body,
        "recipient_email": draft.recipient_email,
        "email_status": draft.email_status,
        "auto_send_eligible": draft.auto_send_eligible,
        "missing_fields": draft.missing_fields,
        "reviewed_by": draft.reviewed_by,
        "reviewed_at": draft.reviewed_at,
        "sent_at": draft.sent_at,
        "send_error": draft.send_error,
        "created_at": draft.created_at,
    }
    if event:
        data["sub_type"] = event.sub_type
        data["company_name"] = event.company_name
        data["position_title"] = event.position_title
        data["contact_name"] = event.contact_name
        data["contact_email"] = event.contact_email
        data["interview_date"] = event.interview_date
        data["interview_time"] = event.interview_time
        data["interview_timezone"] = event.interview_timezone
        data["interview_format"] = event.interview_format
        data["confidence"] = event.confidence
        data["is_job_machine"] = event.is_job_machine
        data["email_db_id"] = event.email_id
    if student:
        data["student_name"] = student.full_name
        data["student_username"] = student.username
        data["student_personal_email"] = student.personal_email
        data["student_assigned_gmail"] = student.assigned_gmail
        data["student_phone"] = student.phone_number
    if email:
        data["email_subject_original"] = email.subject
    return data


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/pending", response_model=List[NotificationSummary])
async def get_pending_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Get notification drafts pending review."""
    results = (
        db.query(NotificationDraft, InterviewEvent, Student)
        .join(InterviewEvent, NotificationDraft.interview_event_id == InterviewEvent.id)
        .outerjoin(Student, InterviewEvent.student_id == Student.id)
        .filter(NotificationDraft.email_status.in_(["draft", "approved"]))
        .order_by(desc(NotificationDraft.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [
        _build_notification_summary(draft, event, student)
        for draft, event, student in results
    ]


@router.get("/sent", response_model=List[NotificationSummary])
async def get_sent_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Get sent notification history."""
    results = (
        db.query(NotificationDraft, InterviewEvent, Student)
        .join(InterviewEvent, NotificationDraft.interview_event_id == InterviewEvent.id)
        .outerjoin(Student, InterviewEvent.student_id == Student.id)
        .filter(NotificationDraft.email_status == "sent")
        .order_by(desc(NotificationDraft.sent_at))
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [
        _build_notification_summary(draft, event, student)
        for draft, event, student in results
    ]


@router.get("/{notification_id}", response_model=NotificationDetail)
async def get_notification_detail(
    notification_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Get full details of a notification draft."""
    result = (
        db.query(NotificationDraft, InterviewEvent, Student, Email)
        .join(InterviewEvent, NotificationDraft.interview_event_id == InterviewEvent.id)
        .outerjoin(Student, InterviewEvent.student_id == Student.id)
        .outerjoin(Email, InterviewEvent.email_id == Email.id)
        .filter(NotificationDraft.id == notification_id)
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )

    draft, event, student, email = result
    return _build_notification_detail(draft, event, student, email)


@router.post("/{notification_id}/approve")
async def approve_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Approve and send a notification draft."""
    draft = (
        db.query(NotificationDraft)
        .filter(NotificationDraft.id == notification_id)
        .first()
    )

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )

    if draft.email_status == "sent":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notification already sent",
        )

    # Update status to approved
    draft.email_status = "approved"
    draft.reviewed_by = user.username
    draft.reviewed_at = datetime.utcnow()
    db.commit()

    # Send the email
    from execution.send_notification import send_email

    send_result = send_email(
        recipient_email=draft.recipient_email or "",
        subject=draft.email_subject or "",
        body=draft.email_body or "",
    )

    if send_result["status"] == "sent":
        draft.email_status = "sent"
        draft.sent_at = datetime.utcnow()
    else:
        draft.email_status = "failed"
        draft.send_error = send_result.get("error")

    db.commit()

    return {
        "id": draft.id,
        "email_status": draft.email_status,
        "send_error": draft.send_error,
    }


@router.post("/{notification_id}/edit")
async def edit_notification(
    notification_id: int,
    request: EditDraftRequest,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Edit a notification draft, optionally sending after edit."""
    draft = (
        db.query(NotificationDraft)
        .filter(NotificationDraft.id == notification_id)
        .first()
    )

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )

    if draft.email_status == "sent":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a sent notification",
        )

    # Apply edits
    if request.email_subject is not None:
        draft.email_subject = request.email_subject
    if request.email_body is not None:
        draft.email_body = request.email_body
    if request.recipient_email is not None:
        draft.recipient_email = request.recipient_email

    draft.reviewed_by = user.username
    draft.reviewed_at = datetime.utcnow()
    db.commit()

    result = {
        "id": draft.id,
        "email_status": draft.email_status,
        "email_subject": draft.email_subject,
    }

    # Optionally send after edit
    if request.send_after_edit:
        from execution.send_notification import send_email

        send_result = send_email(
            recipient_email=draft.recipient_email or "",
            subject=draft.email_subject or "",
            body=draft.email_body or "",
        )

        if send_result["status"] == "sent":
            draft.email_status = "sent"
            draft.sent_at = datetime.utcnow()
        else:
            draft.email_status = "failed"
            draft.send_error = send_result.get("error")

        db.commit()
        result["email_status"] = draft.email_status
        result["send_error"] = draft.send_error

    return result


@router.post("/{notification_id}/reject")
async def reject_notification(
    notification_id: int,
    request: RejectRequest,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Reject a notification draft."""
    draft = (
        db.query(NotificationDraft)
        .filter(NotificationDraft.id == notification_id)
        .first()
    )

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )

    draft.email_status = "rejected"
    draft.reviewed_by = user.username
    draft.reviewed_at = datetime.utcnow()
    if request.reason:
        draft.send_error = f"Rejected: {request.reason}"
    db.commit()

    return {
        "id": draft.id,
        "email_status": draft.email_status,
        "reviewed_by": draft.reviewed_by,
    }


# ============================================================================
# Student Endpoints
# ============================================================================


@router.get("/students/list", response_model=List[StudentResponse])
async def list_students(
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """List all students."""
    query = db.query(Student)
    if active_only:
        query = query.filter(Student.is_active == True)
    students = query.order_by(Student.full_name).limit(limit).all()
    return students


@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Get student details."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found",
        )
    return student


@router.get("/by-email/{email_id}")
async def get_notification_by_email(
    email_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user),
):
    """Get notification details for a specific source email.

    Used by the inbox view to show inline interview notification details
    when an interview email is selected.
    """
    result = (
        db.query(NotificationDraft, InterviewEvent, Student)
        .join(InterviewEvent, NotificationDraft.interview_event_id == InterviewEvent.id)
        .outerjoin(Student, InterviewEvent.student_id == Student.id)
        .filter(InterviewEvent.email_id == email_id)
        .order_by(desc(NotificationDraft.created_at))
        .first()
    )

    if not result:
        return None

    draft, event, student = result
    return _build_notification_detail(draft, event, student)

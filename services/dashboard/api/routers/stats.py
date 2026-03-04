"""
Statistics and metrics API endpoints.

Provides processing statistics, trends, and accuracy metrics.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from database import get_db
from auth import get_current_user
from models import ProcessRun, Classification, Approval, Email, UserSession
from integration.process_runner import run_email_processing, get_run_lock_status

router = APIRouter()


# Pydantic models
class SummaryStats(BaseModel):
    today_total_emails: int
    today_interview_requests: int
    today_organized: int
    today_spam_deleted: int
    week_total_emails: int
    week_interview_requests: int
    last_run_timestamp: Optional[datetime]
    pending_approvals: int
    inbox_count: int


class CategoryBreakdown(BaseModel):
    category: str
    count: int


class AccuracyMetrics(BaseModel):
    total_approvals: int
    approved: int
    overridden: int
    rejected: int
    override_rate: float
    avg_confidence: float
    low_confidence_count: int


class EngineeringKPIs(BaseModel):
    ai_cost_today_usd: float
    avg_duration_seconds_7d: Optional[float]
    failure_rate_7d: float       # 0.0–100.0 percent
    run_count_7d: int
    failed_run_count_7d: int


@router.get("/summary", response_model=SummaryStats)
async def get_summary_stats(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get summary statistics for the dashboard home page.

    Returns real-time stats aggregated from ProcessRun records (written after every scheduled run).
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Aggregate today's stats from ProcessRun records (always populated by processing script)
    today_runs = db.query(ProcessRun).filter(
        ProcessRun.run_timestamp >= today_start
    ).all()

    today_total = sum(r.total_emails for r in today_runs)
    today_interview = sum(r.interview_requests for r in today_runs)
    today_organized = sum(r.organized for r in today_runs)
    today_spam = sum(r.spam_deleted for r in today_runs)

    # Week stats from ProcessRun records
    week_runs = db.query(ProcessRun).filter(
        ProcessRun.run_timestamp >= week_ago
    ).all()

    week_total = sum(r.total_emails for r in week_runs)

    week_interview = sum(r.interview_requests for r in week_runs)

    # Last run (still from ProcessRun for countdown timer)
    last_run = db.query(ProcessRun).order_by(
        ProcessRun.run_timestamp.desc()
    ).first()

    # Pending approvals
    pending = db.query(Approval).filter(
        Approval.status == "pending"
    ).count()

    # Current inbox count
    inbox_count = db.query(Email).filter(
        Email.current_folder == "INBOX"
    ).count()

    result = SummaryStats(
        today_total_emails=today_total,
        today_interview_requests=today_interview,
        today_organized=today_organized,
        today_spam_deleted=today_spam,
        week_total_emails=week_total,
        week_interview_requests=week_interview,
        last_run_timestamp=last_run.run_timestamp if last_run else None,
        pending_approvals=pending,
        inbox_count=inbox_count
    )

    return result


@router.get("/categories", response_model=List[CategoryBreakdown])
async def get_category_breakdown(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get category breakdown over a time period.

    Aggregates category counts from ProcessRun.categories_breakdown JSON field.

    Args:
        start_date: Start date for filtering (defaults to 7 days ago)
        end_date: End date for filtering (defaults to now)

    Returns:
        List of categories with counts
    """
    # Parse dates
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = datetime.utcnow() - timedelta(days=7)

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        end = datetime.utcnow()

    # Aggregate from ProcessRun.categories_breakdown JSON
    runs = db.query(ProcessRun).filter(
        and_(
            ProcessRun.run_timestamp >= start,
            ProcessRun.run_timestamp <= end
        )
    ).all()

    aggregated: Dict[str, int] = {}
    for run in runs:
        breakdown = run.categories_breakdown or {}
        for category, count in breakdown.items():
            aggregated[category] = aggregated.get(category, 0) + int(count)

    return [
        CategoryBreakdown(category=cat, count=count)
        for cat, count in sorted(aggregated.items(), key=lambda x: -x[1])
    ]


@router.get("/accuracy", response_model=AccuracyMetrics)
async def get_accuracy_metrics(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get accuracy and approval metrics.

    Returns:
        Metrics about approval override rate, confidence distribution, etc.
    """
    # Total approvals
    total = db.query(Approval).count()

    # Breakdown by status
    approved = db.query(Approval).filter(Approval.status == "approved").count()
    overridden = db.query(Approval).filter(Approval.status == "overridden").count()
    rejected = db.query(Approval).filter(Approval.status == "rejected").count()

    # Override rate
    override_rate = (overridden / total) if total > 0 else 0.0

    # Average confidence
    avg_conf = db.query(
        func.avg(Classification.confidence)
    ).scalar() or 0.0

    # Low confidence count (< 0.70)
    low_conf = db.query(Classification).filter(
        Classification.confidence < 0.70
    ).count()

    return AccuracyMetrics(
        total_approvals=total,
        approved=approved,
        overridden=overridden,
        rejected=rejected,
        override_rate=override_rate,
        avg_confidence=float(avg_conf),
        low_confidence_count=low_conf
    )


@router.get("/engineering-kpis", response_model=EngineeringKPIs)
async def get_engineering_kpis(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Engineering-level KPIs for operational health monitoring.

    Returns:
        - AI cost incurred today (USD)
        - Average processing duration over the last 7 days (seconds)
        - Failure rate over the last 7 days (%)
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # AI Cost Today — sum gpt_cost_usd for all runs since midnight UTC
    today_runs = db.query(ProcessRun).filter(
        ProcessRun.run_timestamp >= today_start
    ).all()
    ai_cost_today = sum(r.gpt_cost_usd or 0.0 for r in today_runs)

    # 7-day window for duration + failure rate
    week_runs = db.query(ProcessRun).filter(
        ProcessRun.run_timestamp >= week_ago
    ).all()

    run_count = len(week_runs)
    failed_count = sum(1 for r in week_runs if r.status != "success")
    failure_rate = (failed_count / run_count * 100.0) if run_count > 0 else 0.0

    durations = [
        r.duration_seconds for r in week_runs
        if r.duration_seconds is not None and r.duration_seconds > 0
    ]
    avg_duration = (sum(durations) / len(durations)) if durations else None

    return EngineeringKPIs(
        ai_cost_today_usd=round(ai_cost_today, 4),
        avg_duration_seconds_7d=round(avg_duration, 1) if avg_duration is not None else None,
        failure_rate_7d=round(failure_rate, 1),
        run_count_7d=run_count,
        failed_run_count_7d=failed_count,
    )


@router.get("/processing-runs")
async def get_processing_runs(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get recent processing runs.

    Args:
        limit: Number of runs to return (1-100)

    Returns:
        List of recent ProcessRun objects
    """
    runs = db.query(ProcessRun).order_by(
        ProcessRun.run_timestamp.desc()
    ).limit(limit).all()

    return [
        {
            "id": run.id,
            "run_timestamp": run.run_timestamp.isoformat() + 'Z',  # Add Z to indicate UTC
            "total_emails": run.total_emails,
            "interview_requests": run.interview_requests,
            "organized": run.organized,
            "spam_deleted": run.spam_deleted,
            "categories_breakdown": run.categories_breakdown,
            "duration_seconds": run.duration_seconds,
            "status": run.status
        }
        for run in runs
    ]


@router.get("/trends")
async def get_trends(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get email processing trends over time.

    Args:
        days: Number of days to analyze (1-30)

    Returns:
        Daily statistics for the specified period
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    runs = db.query(ProcessRun).filter(
        ProcessRun.run_timestamp >= start_date
    ).order_by(
        ProcessRun.run_timestamp.asc()
    ).all()

    # Group by date
    daily_stats = {}
    for run in runs:
        date_key = run.run_timestamp.date().isoformat()
        if date_key not in daily_stats:
            daily_stats[date_key] = {
                "date": date_key,
                "total_emails": 0,
                "interview_requests": 0,
                "organized": 0,
                "spam_deleted": 0,
                "run_count": 0
            }

        daily_stats[date_key]["total_emails"] += run.total_emails
        daily_stats[date_key]["interview_requests"] += run.interview_requests
        daily_stats[date_key]["organized"] += run.organized
        daily_stats[date_key]["spam_deleted"] += run.spam_deleted
        daily_stats[date_key]["run_count"] += 1

    return {"trends": list(daily_stats.values())}


@router.get("/run-processing/status")
async def get_processing_status(
    user: UserSession = Depends(get_current_user)
):
    """
    Return whether a processing run is currently active.

    The frontend uses this to disable the Run Now button and show a spinner
    while a run is in progress.

    Returns:
        { "locked": bool, "lock_info": { pid, started_at, triggered_by, elapsed_seconds } | null }
    """
    lock_info = get_run_lock_status()
    return {
        "locked": lock_info is not None,
        "lock_info": lock_info,
    }


@router.post("/run-processing")
async def trigger_manual_processing(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Manually trigger email processing.

    Returns 409 Conflict if a run is already active (run lock held).
    Runs the process_inbox_auto.py script and imports the results
    into the database.

    Returns:
        Processing results with status, duration, and summary data

    Raises:
        HTTPException 409: If another run is already in progress
        HTTPException 500: If processing fails
    """
    # Guard: reject immediately if a run is already active
    lock_info = get_run_lock_status()
    if lock_info:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"A processing run is already active "
                    f"(triggered by '{lock_info['triggered_by']}', "
                    f"running for {lock_info['elapsed_seconds']:.0f}s)"
                ),
                "lock_info": lock_info,
            }
        )

    try:
        result = run_email_processing(db, triggered_by=user.username)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

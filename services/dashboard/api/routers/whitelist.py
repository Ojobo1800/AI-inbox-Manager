"""
Whitelist management API endpoints.

Handles adding, removing, and viewing whitelisted companies.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from database import get_db
from auth import get_current_user
from models import WhitelistCompany, UserSession
from integration.summary_importer import add_to_whitelist, remove_from_whitelist, get_whitelist

router = APIRouter()


# Pydantic models
class WhitelistResponse(BaseModel):
    id: int
    company_name: str
    added_date: datetime
    added_by: str
    notes: Optional[str]

    class Config:
        from_attributes = True


class AddWhitelistRequest(BaseModel):
    company_name: str
    notes: Optional[str] = None


@router.get("", response_model=List[WhitelistResponse])
async def get_whitelist_companies(
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Get all whitelisted companies.

    Returns companies sorted by added_date (most recent first).
    """
    companies = get_whitelist(db)

    return [
        WhitelistResponse(
            id=company.id,
            company_name=company.company_name,
            added_date=company.added_date,
            added_by=company.added_by,
            notes=company.notes
        )
        for company in companies
    ]


@router.post("", response_model=WhitelistResponse)
async def add_whitelist_company(
    request: AddWhitelistRequest,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Add a company to the whitelist.

    Whitelisted companies are never moved or deleted regardless of AI classification.

    Args:
        request: Company name and optional notes

    Returns:
        Created or existing WhitelistCompany
    """
    company = add_to_whitelist(
        db=db,
        company_name=request.company_name,
        notes=request.notes or f"Added by {user.username} via dashboard",
        added_by=user.username
    )

    return WhitelistResponse(
        id=company.id,
        company_name=company.company_name,
        added_date=company.added_date,
        added_by=company.added_by,
        notes=company.notes
    )


@router.delete("/{company_id}")
async def delete_whitelist_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: UserSession = Depends(get_current_user)
):
    """
    Remove a company from the whitelist.

    Args:
        company_id: ID of the WhitelistCompany to remove

    Returns:
        Success message

    Raises:
        HTTPException: If company not found
    """
    success = remove_from_whitelist(db, company_id)

    if not success:
        raise HTTPException(status_code=404, detail="Company not found in whitelist")

    return {"message": "Company removed from whitelist", "company_id": company_id}

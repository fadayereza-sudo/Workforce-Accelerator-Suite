"""
Organization-related models.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class OrgCreate(BaseModel):
    """Data needed to create an organization."""
    name: str


class Organization(BaseModel):
    """Full organization model from database."""
    id: str
    name: str
    created_by: str
    settings: Dict[str, Any] = {}
    invite_code: str  # Unique code for invite links
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InviteLink(BaseModel):
    """Generated invite link for an organization."""
    url: str
    code: str
    org_name: str

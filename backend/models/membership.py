"""
Membership and access request models.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class MembershipRequestCreate(BaseModel):
    """Data to request membership to an org."""
    invite_code: str
    full_name: str


class MembershipRequest(BaseModel):
    """Pending membership request."""
    id: str
    user_id: str
    org_id: str
    full_name: str
    telegram_username: Optional[str] = None
    status: str  # 'pending', 'approved', 'rejected'
    created_at: datetime

    class Config:
        from_attributes = True


class MembershipRequestResponse(BaseModel):
    """Response when creating a membership request."""
    request_id: str
    org_name: str
    status: str
    message: str


class BotAccess(BaseModel):
    """Bot access grant."""
    bot_id: str
    bot_name: str
    granted: bool = False


class MembershipApproval(BaseModel):
    """Admin approving/rejecting a membership request."""
    request_id: str
    approved: bool
    bot_ids: List[str] = []  # Which bots to grant access to


class Member(BaseModel):
    """Organization member with their access."""
    id: str
    user_id: str
    full_name: str
    telegram_username: Optional[str] = None
    role: str  # 'admin', 'member'
    bot_access: List[BotAccess] = []
    joined_at: datetime
    last_active_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MemberBotsUpdate(BaseModel):
    """Update bot access for a member."""
    bot_ids: List[str]

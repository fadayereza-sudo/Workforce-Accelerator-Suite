"""
Hub Bot API - Organization management endpoints.

Handles:
- User authentication and profile
- Organization creation
- Invite link generation
- Membership requests (join via invite)
- Request approval/rejection by admin
- Bot access management
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks

from models import (
    TelegramUser, User,
    Organization, OrgCreate, InviteLink,
    MembershipRequest, MembershipRequestCreate, MembershipRequestResponse,
    MembershipApproval, Member, BotAccess
)
from services import get_supabase_admin, get_telegram_user
from services.notifications import (
    notify_admin_new_request,
    notify_user_approved,
    notify_user_rejected
)
from config import settings

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# DEPENDENCIES
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(x_telegram_init_data: str = Header(...)) -> TelegramUser:
    """Extract and verify Telegram user from initData header."""
    return get_telegram_user(x_telegram_init_data)


# ─────────────────────────────────────────────────────────────────────────────
# USER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(x_telegram_init_data: str = Header(...)) -> dict:
    """
    Get current user profile and their organization context.
    Creates user if first time.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get or create user
    result = db.table("users").select("*").eq("telegram_id", tg_user.id).execute()

    if result.data:
        user = result.data[0]
    else:
        # Create new user
        user_data = {
            "telegram_id": tg_user.id,
            "telegram_username": tg_user.username,
            "full_name": f"{tg_user.first_name} {tg_user.last_name or ''}".strip(),
            "avatar_url": tg_user.photo_url
        }
        result = db.table("users").insert(user_data).execute()
        user = result.data[0]

    # Get user's memberships
    memberships = db.table("memberships").select(
        "*, organizations(*)"
    ).eq("user_id", user["id"]).execute()

    # Get any pending requests
    pending_requests = db.table("membership_requests").select(
        "*, organizations(name)"
    ).eq("user_id", user["id"]).eq("status", "pending").execute()

    return {
        "user": user,
        "memberships": memberships.data,
        "pending_requests": pending_requests.data
    }


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZATION ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/orgs")
async def create_organization(
    data: OrgCreate,
    x_telegram_init_data: str = Header(...)
) -> Organization:
    """Create a new organization. Creator becomes admin."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get or create user, updating their full name
    user_result = db.table("users").select("id").eq("telegram_id", tg_user.id).execute()

    if user_result.data:
        # Update existing user's name
        user_id = user_result.data[0]["id"]
        db.table("users").update({
            "full_name": data.admin_full_name
        }).eq("id", user_id).execute()
    else:
        # Create new user with provided name
        new_user = db.table("users").insert({
            "telegram_id": tg_user.id,
            "telegram_username": tg_user.username,
            "full_name": data.admin_full_name,
            "avatar_url": tg_user.photo_url
        }).execute()
        user_id = new_user.data[0]["id"]

    # Create org with unique invite code (expires in 24 hours)
    invite_code = secrets.token_urlsafe(8)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    org_data = {
        "name": data.name,
        "created_by": user_id,
        "invite_code": invite_code,
        "invite_code_expires_at": expires_at.isoformat(),
        "settings": {}
    }
    org_result = db.table("organizations").insert(org_data).execute()
    org = org_result.data[0]

    # Add creator as admin member
    membership_data = {
        "user_id": user_id,
        "org_id": org["id"],
        "role": "admin"
    }
    db.table("memberships").insert(membership_data).execute()

    return org


@router.get("/orgs/{org_id}")
async def get_organization(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Get organization details (must be a member)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Verify membership
    user = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    if not user.data:
        raise HTTPException(404, "User not found")

    membership = db.table("memberships").select("*").eq(
        "user_id", user.data["id"]
    ).eq("org_id", org_id).execute()

    if not membership.data:
        raise HTTPException(403, "Not a member of this organization")

    # Get org
    org = db.table("organizations").select("*").eq("id", org_id).single().execute()

    return {
        "organization": org.data,
        "membership": membership.data[0]
    }


# ─────────────────────────────────────────────────────────────────────────────
# INVITE LINK ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/invite-link")
async def get_invite_link(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> InviteLink:
    """Get the invite link for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Verify admin
    user = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    membership = db.table("memberships").select("role").eq(
        "user_id", user.data["id"]
    ).eq("org_id", org_id).single().execute()

    if not membership.data or membership.data["role"] != "admin":
        raise HTTPException(403, "Admin access required")

    # Get org
    org = db.table("organizations").select("name, invite_code, invite_code_expires_at").eq(
        "id", org_id
    ).single().execute()

    # Check expiration
    expires_at = datetime.fromisoformat(org.data["invite_code_expires_at"].replace("Z", "+00:00"))
    is_expired = datetime.now(timezone.utc) > expires_at

    # Generate full URL - this opens the Mini App with the invite code
    # Format: https://t.me/BotUsername/app?startapp=invite_CODE
    bot_username = "apex_org_bot"
    url = f"https://t.me/{bot_username}/app?startapp=invite_{org.data['invite_code']}"

    return InviteLink(
        url=url,
        code=org.data["invite_code"],
        org_name=org.data["name"],
        expires_at=expires_at,
        is_expired=is_expired
    )


@router.post("/orgs/{org_id}/regenerate-invite")
async def regenerate_invite_link(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> InviteLink:
    """Regenerate the invite link for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Verify admin
    user = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    membership = db.table("memberships").select("role").eq(
        "user_id", user.data["id"]
    ).eq("org_id", org_id).single().execute()

    if not membership.data or membership.data["role"] != "admin":
        raise HTTPException(403, "Admin access required")

    # Generate new invite code with 24-hour expiration
    new_code = secrets.token_urlsafe(8)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Update org
    db.table("organizations").update({
        "invite_code": new_code,
        "invite_code_expires_at": expires_at.isoformat()
    }).eq("id", org_id).execute()

    # Get org name
    org = db.table("organizations").select("name").eq("id", org_id).single().execute()

    # Generate URL
    bot_username = "apex_org_bot"
    url = f"https://t.me/{bot_username}/app?startapp=invite_{new_code}"

    return InviteLink(
        url=url,
        code=new_code,
        org_name=org.data["name"],
        expires_at=expires_at,
        is_expired=False
    )


@router.get("/invite/{invite_code}")
async def get_invite_info(invite_code: str) -> dict:
    """Get organization info from invite code (public endpoint)."""
    db = get_supabase_admin()

    org = db.table("organizations").select("id, name, invite_code_expires_at").eq(
        "invite_code", invite_code
    ).execute()

    if not org.data:
        raise HTTPException(404, "Invalid invite code")

    # Check if expired
    expires_at = datetime.fromisoformat(org.data[0]["invite_code_expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(410, "This invite link has expired")

    return {
        "org_id": org.data[0]["id"],
        "org_name": org.data[0]["name"]
    }


# ─────────────────────────────────────────────────────────────────────────────
# MEMBERSHIP REQUEST ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/membership-requests")
async def create_membership_request(
    data: MembershipRequestCreate,
    background_tasks: BackgroundTasks,
    x_telegram_init_data: str = Header(...)
) -> MembershipRequestResponse:
    """
    Request to join an organization via invite code.
    User provides their full name; admin will be notified.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get or create user
    user_result = db.table("users").select("*").eq("telegram_id", tg_user.id).execute()

    if user_result.data:
        user = user_result.data[0]
        # Update name if provided
        if data.full_name:
            db.table("users").update({
                "full_name": data.full_name
            }).eq("id", user["id"]).execute()
    else:
        # Create user
        user_data = {
            "telegram_id": tg_user.id,
            "telegram_username": tg_user.username,
            "full_name": data.full_name,
            "avatar_url": tg_user.photo_url
        }
        user_result = db.table("users").insert(user_data).execute()
        user = user_result.data[0]

    # Find org by invite code
    org = db.table("organizations").select("id, name, created_by, invite_code_expires_at").eq(
        "invite_code", data.invite_code
    ).execute()

    if not org.data:
        raise HTTPException(404, "Invalid invite code")

    org_data = org.data[0]

    # Check if invite code has expired
    expires_at = datetime.fromisoformat(org_data["invite_code_expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(410, "This invite link has expired")

    # Check if already a member
    existing = db.table("memberships").select("id").eq(
        "user_id", user["id"]
    ).eq("org_id", org_data["id"]).execute()

    if existing.data:
        raise HTTPException(400, "Already a member of this organization")

    # Check for existing pending request
    existing_request = db.table("membership_requests").select("id").eq(
        "user_id", user["id"]
    ).eq("org_id", org_data["id"]).eq("status", "pending").execute()

    if existing_request.data:
        return MembershipRequestResponse(
            request_id=existing_request.data[0]["id"],
            org_name=org_data["name"],
            status="pending",
            message="Your request is still pending approval"
        )

    # Create membership request
    request_data = {
        "user_id": user["id"],
        "org_id": org_data["id"],
        "full_name": data.full_name,
        "telegram_username": tg_user.username,
        "status": "pending"
    }
    request_result = db.table("membership_requests").insert(request_data).execute()
    request = request_result.data[0]

    # Notify admin (get admin's telegram_id)
    admin = db.table("users").select("telegram_id").eq(
        "id", org_data["created_by"]
    ).single().execute()

    if admin.data:
        background_tasks.add_task(
            notify_admin_new_request,
            admin.data["telegram_id"],
            data.full_name,
            org_data["name"]
        )

    return MembershipRequestResponse(
        request_id=request["id"],
        org_name=org_data["name"],
        status="pending",
        message="Your request has been sent to the admin"
    )


@router.get("/orgs/{org_id}/membership-requests")
async def list_membership_requests(
    org_id: str,
    status: Optional[str] = "pending",
    x_telegram_init_data: str = Header(...)
) -> List[MembershipRequest]:
    """List membership requests for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Verify admin
    user = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    membership = db.table("memberships").select("role").eq(
        "user_id", user.data["id"]
    ).eq("org_id", org_id).single().execute()

    if not membership.data or membership.data["role"] != "admin":
        raise HTTPException(403, "Admin access required")

    # Get requests
    query = db.table("membership_requests").select("*").eq("org_id", org_id)
    if status:
        query = query.eq("status", status)

    requests = query.order("created_at", desc=True).execute()

    return requests.data


@router.post("/membership-requests/{request_id}/approve")
async def approve_membership_request(
    request_id: str,
    data: MembershipApproval,
    background_tasks: BackgroundTasks,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Approve or reject a membership request (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get the request
    request = db.table("membership_requests").select(
        "*, organizations(name)"
    ).eq("id", request_id).single().execute()

    if not request.data:
        raise HTTPException(404, "Request not found")

    request_data = request.data

    # Verify admin of this org
    user = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    membership = db.table("memberships").select("role").eq(
        "user_id", user.data["id"]
    ).eq("org_id", request_data["org_id"]).single().execute()

    if not membership.data or membership.data["role"] != "admin":
        raise HTTPException(403, "Admin access required")

    if data.approved:
        # Create membership
        membership_data = {
            "user_id": request_data["user_id"],
            "org_id": request_data["org_id"],
            "role": "member"
        }
        new_membership = db.table("memberships").insert(membership_data).execute()

        # Grant bot access
        bot_names = []
        for bot_id in data.bot_ids:
            access_data = {
                "membership_id": new_membership.data[0]["id"],
                "bot_id": bot_id,
                "granted_by": user.data["id"]
            }
            db.table("bot_member_access").insert(access_data).execute()

            # Get bot name for notification
            bot = db.table("bot_registry").select("name").eq("id", bot_id).execute()
            if bot.data:
                bot_names.append(bot.data[0]["name"])

        # Update request status
        db.table("membership_requests").update({
            "status": "approved"
        }).eq("id", request_id).execute()

        # Notify user
        requester = db.table("users").select("telegram_id").eq(
            "id", request_data["user_id"]
        ).single().execute()

        if requester.data:
            background_tasks.add_task(
                notify_user_approved,
                requester.data["telegram_id"],
                request_data["organizations"]["name"],
                bot_names
            )

        return {"status": "approved", "bot_access": bot_names}

    else:
        # Reject
        db.table("membership_requests").update({
            "status": "rejected"
        }).eq("id", request_id).execute()

        # Notify user
        requester = db.table("users").select("telegram_id").eq(
            "id", request_data["user_id"]
        ).single().execute()

        if requester.data:
            background_tasks.add_task(
                notify_user_rejected,
                requester.data["telegram_id"],
                request_data["organizations"]["name"]
            )

        return {"status": "rejected"}


# ─────────────────────────────────────────────────────────────────────────────
# MEMBER MANAGEMENT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/members")
async def list_members(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> List[Member]:
    """List all members of an organization."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Verify membership
    user = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    membership = db.table("memberships").select("*").eq(
        "user_id", user.data["id"]
    ).eq("org_id", org_id).execute()

    if not membership.data:
        raise HTTPException(403, "Not a member of this organization")

    # Get all members with their user info
    members = db.table("memberships").select(
        "*, users(full_name, telegram_username)"
    ).eq("org_id", org_id).execute()

    # Get bot access for each member
    result = []
    for m in members.data:
        access = db.table("bot_member_access").select(
            "bot_id, bot_registry(name)"
        ).eq("membership_id", m["id"]).execute()

        bot_access = [
            BotAccess(
                bot_id=a["bot_id"],
                bot_name=a["bot_registry"]["name"] if a.get("bot_registry") else a["bot_id"],
                granted=True
            )
            for a in access.data
        ]

        result.append(Member(
            id=m["id"],
            user_id=m["user_id"],
            full_name=m["users"]["full_name"],
            telegram_username=m["users"]["telegram_username"],
            role=m["role"],
            bot_access=bot_access,
            joined_at=m["created_at"]
        ))

    return result


@router.get("/bots")
async def list_available_bots(
    x_telegram_init_data: str = Header(...)
) -> List[dict]:
    """List all available bots in the registry."""
    get_telegram_user(x_telegram_init_data)  # Verify auth
    db = get_supabase_admin()

    bots = db.table("bot_registry").select("*").eq("is_active", True).execute()

    return bots.data

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
    Organization, OrgCreate, InviteCode, OrgStats, OrgDetails, OrgUpdate,
    MembershipRequest, MembershipRequestCreate, MembershipRequestResponse,
    MembershipApproval, Member, BotAccess, MemberBotsUpdate, MemberRoleUpdate,
    # Admin models
    ActivityLogCreate, MemberActivity, LeadAgentOverview, TeamAnalytics,
    AgentUsage, AgentAnalytics,
    SubscriptionPlan, OrgSubscription, Invoice, InvoiceList, BillingOverview,
    # Product models
    ProductCreate, ProductUpdate, Product
)
from services import get_supabase_admin, get_telegram_user
from services.cache import cache_get, cache_set, cache_delete, cache_invalidate, cache_invalidate_multi
from services.notifications import (
    notify_admin_new_request,
    notify_user_approved,
    notify_user_rejected,
    send_invite_link_to_admin
)
from config import settings

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# DEPENDENCIES
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(x_telegram_init_data: str = Header(...)) -> TelegramUser:
    """Extract and verify Telegram user from initData header."""
    return get_telegram_user(x_telegram_init_data)


def _cached_get_user_id(telegram_id: int) -> str:
    """Get user ID from telegram_id, with caching."""
    cache_key = f"user:{telegram_id}"
    cached = cache_get("auth", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()
    result = db.table("users").select("id").eq("telegram_id", telegram_id).single().execute()
    if not result.data:
        raise HTTPException(404, "User not found")

    user_id = result.data["id"]
    cache_set("auth", cache_key, user_id)
    return user_id


def _cached_verify_admin(telegram_id: int, org_id: str) -> str:
    """Verify user is admin of org, return user_id. Cached."""
    user_id = _cached_get_user_id(telegram_id)

    cache_key = f"membership:{user_id}:{org_id}"
    cached = cache_get("auth", cache_key)
    if cached is not None:
        if cached.get("role") != "admin":
            raise HTTPException(403, "Admin access required")
        return user_id

    db = get_supabase_admin()
    membership = db.table("memberships").select("role").eq(
        "user_id", user_id
    ).eq("org_id", org_id).single().execute()

    if not membership.data:
        raise HTTPException(403, "Not a member of this organization")

    cache_set("auth", cache_key, membership.data)

    if membership.data["role"] != "admin":
        raise HTTPException(403, "Admin access required")

    return user_id


def _cached_verify_member(telegram_id: int, org_id: str) -> tuple:
    """Verify user is member of org, return (user_id, role). Cached."""
    user_id = _cached_get_user_id(telegram_id)

    cache_key = f"membership:{user_id}:{org_id}"
    cached = cache_get("auth", cache_key)
    if cached is not None:
        return user_id, cached.get("role", "member")

    db = get_supabase_admin()
    membership = db.table("memberships").select("role").eq(
        "user_id", user_id
    ).eq("org_id", org_id).execute()

    if not membership.data:
        raise HTTPException(403, "Not a member of this organization")

    cache_set("auth", cache_key, membership.data[0])
    return user_id, membership.data[0]["role"]


# ─────────────────────────────────────────────────────────────────────────────
# USER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(x_telegram_init_data: str = Header(...)) -> dict:
    """
    Get current user profile and their organization context.

    Users are only created through proper signup flows:
    - Creating an organization (POST /orgs) - becomes admin
    - Joining via invite code (POST /membership-requests) - pending approval

    Returns user: null if the telegram user hasn't signed up yet.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    print(f"[/me] Telegram user: id={tg_user.id}, username={tg_user.username}, name={tg_user.first_name}")

    # Check if user exists - DO NOT create automatically
    result = db.table("users").select("*").eq("telegram_id", tg_user.id).execute()

    if not result.data:
        # User hasn't signed up yet - return null user
        print(f"[/me] User not found - needs to sign up via org creation or invite code")
        return {
            "user": None,
            "memberships": [],
            "pending_requests": []
        }

    user = result.data[0]
    print(f"[/me] Found existing user: id={user['id']}, name={user['full_name']}")

    # Get user's memberships
    memberships = db.table("memberships").select(
        "*, organizations(*)"
    ).eq("user_id", user["id"]).execute()

    print(f"[/me] User {user['id']} has {len(memberships.data)} memberships")
    for m in memberships.data:
        print(f"[/me]   - Membership: id={m['id']}, org={m['organizations']['name']}, role={m['role']}")

    # Update last_active_at for all user's memberships (activity tracking)
    if memberships.data:
        now = datetime.now(timezone.utc).isoformat()
        for m in memberships.data:
            db.table("memberships").update({
                "last_active_at": now
            }).eq("id", m["id"]).execute()

    # Get any pending requests
    pending_requests = db.table("membership_requests").select(
        "*, organizations(name)"
    ).eq("user_id", user["id"]).eq("status", "pending").execute()

    print(f"[/me] User {user['id']} has {len(pending_requests.data)} pending requests")

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

    # Invalidate auth cache for this user (new membership)
    cache_delete("auth", f"user:{tg_user.id}")

    return org


@router.get("/orgs/{org_id}")
async def get_organization(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Get organization details (must be a member)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, role = _cached_verify_member(tg_user.id, org_id)
    db = get_supabase_admin()

    # Get org
    org = db.table("organizations").select("*").eq("id", org_id).single().execute()

    membership = db.table("memberships").select("*").eq(
        "user_id", user_id
    ).eq("org_id", org_id).execute()

    return {
        "organization": org.data,
        "membership": membership.data[0]
    }


@router.get("/orgs/{org_id}/details")
async def get_organization_details(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> OrgDetails:
    """Get organization details with stats (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    # Check cache
    cache_key = f"org_details:{org_id}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Get org
    org = db.table("organizations").select("*").eq("id", org_id).single().execute()
    if not org.data:
        raise HTTPException(404, "Organization not found")

    # Get stats
    members_count = db.table("memberships").select("id", count="exact").eq(
        "org_id", org_id
    ).execute()

    pending_count = db.table("membership_requests").select("id", count="exact").eq(
        "org_id", org_id
    ).eq("status", "pending").execute()

    # Count unique bots with access in this org
    bots_result = db.table("bot_member_access").select(
        "bot_id, memberships!inner(org_id)"
    ).eq("memberships.org_id", org_id).execute()
    unique_bots = len(set(b["bot_id"] for b in bots_result.data)) if bots_result.data else 0

    stats = OrgStats(
        member_count=members_count.count or 0,
        pending_requests_count=pending_count.count or 0,
        active_bots_count=unique_bots
    )

    result = OrgDetails(
        id=org.data["id"],
        name=org.data["name"],
        description=org.data.get("description"),
        created_by=org.data["created_by"],
        created_at=org.data["created_at"],
        stats=stats
    )
    cache_set("org", cache_key, result)
    return result


@router.patch("/orgs/{org_id}")
async def update_organization(
    org_id: str,
    data: OrgUpdate,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Update organization details (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Build update data
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description

    if not update_data:
        raise HTTPException(400, "No fields to update")

    # Update org
    result = db.table("organizations").update(update_data).eq("id", org_id).execute()

    cache_invalidate("org", f"org_details:{org_id}")
    return {"status": "updated", "organization": result.data[0]}


# ─────────────────────────────────────────────────────────────────────────────
# INVITE LINK ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/invite-code")
async def get_invite_code(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> InviteCode:
    """Get the invite code for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    # Check cache
    invite_cache_key = f"invite:{org_id}"
    cached = cache_get("org", invite_cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Get org
    org = db.table("organizations").select("name, invite_code, invite_code_expires_at").eq(
        "id", org_id
    ).single().execute()

    # Check expiration
    expires_at = datetime.fromisoformat(org.data["invite_code_expires_at"].replace("Z", "+00:00"))
    is_expired = datetime.now(timezone.utc) > expires_at

    # Direct mini-app URL for users to open
    bot_username = settings.BOT_USERNAME if hasattr(settings, 'BOT_USERNAME') else "apex_workforce_bot"
    app_shortname = settings.MINI_APP_SHORTNAME if hasattr(settings, 'MINI_APP_SHORTNAME') else "hub"
    app_url = f"https://t.me/{bot_username}/{app_shortname}"

    # Generate text content for the invite file
    text_content = f"""Join {org.data['name']} on Workforce Accelerator

1. Open the app: {app_url}
2. Tap 'Join with Invite Code'
3. Enter this invite code: {org.data['invite_code']}
4. Enter your full name and submit

This code expires in 24 hours."""

    result = InviteCode(
        code=org.data["invite_code"],
        org_name=org.data["name"],
        bot_url=app_url,
        text_content=text_content,
        expires_at=expires_at,
        is_expired=is_expired
    )
    cache_set("org", invite_cache_key, result)
    return result


@router.post("/orgs/{org_id}/regenerate-invite")
async def regenerate_invite_code(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> InviteCode:
    """Regenerate the invite code for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

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

    # Direct mini-app URL for users to open
    bot_username = settings.BOT_USERNAME if hasattr(settings, 'BOT_USERNAME') else "apex_workforce_bot"
    app_shortname = settings.MINI_APP_SHORTNAME if hasattr(settings, 'MINI_APP_SHORTNAME') else "hub"
    app_url = f"https://t.me/{bot_username}/{app_shortname}"

    # Generate text content for the invite file
    text_content = f"""Join {org.data['name']} on Workforce Accelerator

1. Open the app: {app_url}
2. Tap 'Join with Invite Code'
3. Enter this invite code: {new_code}
4. Enter your full name and submit

This code expires in 24 hours."""

    cache_delete("org", f"invite:{org_id}")
    return InviteCode(
        code=new_code,
        org_name=org.data["name"],
        bot_url=app_url,
        text_content=text_content,
        expires_at=expires_at,
        is_expired=False
    )


@router.post("/orgs/{org_id}/send-invite-link")
async def send_invite_link(
    org_id: str,
    background_tasks: BackgroundTasks,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """
    Send the invite link message to the admin via Telegram.
    The admin can then forward this message to invite users.
    If the current code is expired, a new one is generated automatically.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Get org details
    org = db.table("organizations").select("name, invite_code, invite_code_expires_at").eq(
        "id", org_id
    ).single().execute()

    # Check if code is expired and regenerate if needed
    expires_at = datetime.fromisoformat(org.data["invite_code_expires_at"].replace("Z", "+00:00"))
    is_expired = datetime.now(timezone.utc) > expires_at

    if is_expired:
        # Generate new invite code
        new_code = secrets.token_urlsafe(8)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        db.table("organizations").update({
            "invite_code": new_code,
            "invite_code_expires_at": expires_at.isoformat()
        }).eq("id", org_id).execute()
        invite_code = new_code
        cache_delete("org", f"invite:{org_id}")
    else:
        invite_code = org.data["invite_code"]

    # Direct mini-app URL (opens the app directly instead of just the bot chat)
    bot_username = settings.BOT_USERNAME if hasattr(settings, 'BOT_USERNAME') else "apex_workforce_bot"
    app_shortname = settings.MINI_APP_SHORTNAME if hasattr(settings, 'MINI_APP_SHORTNAME') else "hub"
    app_url = f"https://t.me/{bot_username}/{app_shortname}"

    # Calculate hours remaining
    hours_remaining = max(1, int((expires_at - datetime.now(timezone.utc)).total_seconds() / 3600))

    # Send the invite message to admin in background
    background_tasks.add_task(
        send_invite_link_to_admin,
        admin_telegram_id=tg_user.id,
        org_name=org.data["name"],
        invite_code=invite_code,
        app_url=app_url,
        expires_in_hours=hours_remaining
    )

    return {
        "success": True,
        "message": "Invite link sent to your Telegram chat",
        "code_regenerated": is_expired
    }


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

    # Invalidate requests cache for this org
    cache_invalidate("org", f"requests:{org_data['id']}")

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
    _cached_verify_admin(tg_user.id, org_id)

    # Check cache (only for default pending status)
    cache_key = f"requests:{org_id}:{status or 'all'}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Get requests
    query = db.table("membership_requests").select("*").eq("org_id", org_id)
    if status:
        query = query.eq("status", status)

    requests = query.order("created_at", desc=True).execute()

    cache_set("org", cache_key, requests.data)
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
    admin_user_id = _cached_verify_admin(tg_user.id, request_data["org_id"])

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
                "granted_by": admin_user_id
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

        # Invalidate caches: requests, members, org details (member count changed)
        org_id = request_data["org_id"]
        cache_invalidate("org", f"requests:{org_id}")
        cache_invalidate("org", f"members:{org_id}")
        cache_invalidate("org", f"org_details:{org_id}")

        return {"status": "approved", "bot_access": bot_names}

    else:
        # Reject
        db.table("membership_requests").update({
            "status": "rejected"
        }).eq("id", request_id).execute()

        cache_invalidate("org", f"requests:{request_data['org_id']}")

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
    _cached_verify_member(tg_user.id, org_id)

    # Check cache
    cache_key = f"members:{org_id}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

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
            joined_at=m["created_at"],
            last_active_at=m.get("last_active_at")
        ))

    cache_set("org", cache_key, result)
    return result


@router.delete("/orgs/{org_id}/members/{member_id}")
async def remove_member(
    org_id: str,
    member_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Remove a member from an organization (admin only). Cannot remove admins."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Get the target membership
    target = db.table("memberships").select("*, users(full_name)").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    # Cannot remove admins
    if target.data["role"] == "admin":
        raise HTTPException(400, "Cannot remove an admin member")

    # Delete bot access first (cascade should handle this, but being explicit)
    db.table("bot_member_access").delete().eq("membership_id", member_id).execute()

    # Delete membership
    db.table("memberships").delete().eq("id", member_id).execute()

    # Invalidate members and org details caches
    cache_invalidate("org", f"members:{org_id}")
    cache_invalidate("org", f"org_details:{org_id}")
    # Invalidate removed user's auth cache
    cache_invalidate("auth", f"membership:{target.data['user_id']}")

    return {
        "status": "removed",
        "member_name": target.data["users"]["full_name"]
    }


@router.put("/orgs/{org_id}/members/{member_id}/bots")
async def update_member_bots(
    org_id: str,
    member_id: str,
    data: MemberBotsUpdate,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Update bot access for a member (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    admin_user_id = _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Verify target membership exists and belongs to this org
    target = db.table("memberships").select("id").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    # Get current bot access
    current_access = db.table("bot_member_access").select("bot_id").eq(
        "membership_id", member_id
    ).execute()
    current_bot_ids = set(a["bot_id"] for a in current_access.data)
    new_bot_ids = set(data.bot_ids)

    # Remove bots no longer in the list
    to_remove = current_bot_ids - new_bot_ids
    if to_remove:
        for bot_id in to_remove:
            db.table("bot_member_access").delete().eq(
                "membership_id", member_id
            ).eq("bot_id", bot_id).execute()

    # Add new bots
    to_add = new_bot_ids - current_bot_ids
    for bot_id in to_add:
        db.table("bot_member_access").insert({
            "membership_id": member_id,
            "bot_id": bot_id,
            "granted_by": admin_user_id
        }).execute()

    # Get updated bot names
    bot_names = []
    if data.bot_ids:
        bots = db.table("bot_registry").select("id, name").in_("id", data.bot_ids).execute()
        bot_names = [b["name"] for b in bots.data]

    cache_delete("org", f"members:{org_id}")

    return {
        "status": "updated",
        "bot_access": bot_names
    }


@router.put("/orgs/{org_id}/members/{member_id}/role")
async def update_member_role(
    org_id: str,
    member_id: str,
    data: MemberRoleUpdate,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Update role for a member (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Validate role
    if data.role not in ["admin", "member"]:
        raise HTTPException(400, "Invalid role. Must be 'admin' or 'member'")

    # Verify target membership exists and belongs to this org
    target = db.table("memberships").select("id, user_id, users(full_name)").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    # Update the role
    db.table("memberships").update({
        "role": data.role,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", member_id).execute()

    # Invalidate members and org details caches
    cache_delete("org", f"members:{org_id}")
    cache_delete("org", f"orgDetails:{org_id}")

    return {
        "status": "updated",
        "member_id": member_id,
        "new_role": data.role,
        "member_name": target.data["users"]["full_name"]
    }


@router.get("/bots")
async def list_available_bots(
    x_telegram_init_data: str = Header(...)
) -> List[dict]:
    """List all available bots in the registry."""
    get_telegram_user(x_telegram_init_data)  # Verify auth

    # Check cache
    cached = cache_get("catalog", "bots:active")
    if cached is not None:
        return cached

    db = get_supabase_admin()
    bots = db.table("bot_registry").select("*").eq("is_active", True).execute()

    cache_set("catalog", "bots:active", bots.data)
    return bots.data


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD - ACTIVITY TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/activity")
async def log_activity(
    data: ActivityLogCreate,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Log member activity (called from mini-apps)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, _ = _cached_verify_member(tg_user.id, data.org_id)
    db = get_supabase_admin()

    # Get membership id for logging
    membership = db.table("memberships").select("id").eq(
        "user_id", user_id
    ).eq("org_id", data.org_id).single().execute()

    # Log the activity
    activity_data = {
        "membership_id": membership.data["id"],
        "user_id": user_id,
        "org_id": data.org_id,
        "bot_id": data.bot_id,
        "action_type": data.action_type,
        "action_detail": data.action_detail
    }
    db.table("member_activity_log").insert(activity_data).execute()

    # Update last_active_at
    db.table("memberships").update({
        "last_active_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", membership.data["id"]).execute()

    return {"status": "logged"}


@router.get("/orgs/{org_id}/analytics/team")
async def get_team_analytics(
    org_id: str,
    period: str = "week",
    x_telegram_init_data: str = Header(...)
) -> TeamAnalytics:
    """Get team activity analytics (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    # Check cache (keyed by org + period)
    cache_key = f"team_analytics:{org_id}:{period}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Calculate period bounds
    now = datetime.now(timezone.utc)
    if period == "day":
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        period_start = now - timedelta(days=now.weekday())
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        period_start = now - timedelta(days=7)

    period_end = now

    # Get all members with their user info
    members_result = db.table("memberships").select(
        "id, user_id, role, last_active_at, users(full_name, telegram_username)"
    ).eq("org_id", org_id).execute()

    # Get activity counts per member for this period
    activity_counts = {}
    bots_accessed = {}

    for m in members_result.data:
        # Count activities
        activity_result = db.table("member_activity_log").select(
            "id", count="exact"
        ).eq("membership_id", m["id"]).gte(
            "created_at", period_start.isoformat()
        ).execute()
        activity_counts[m["id"]] = activity_result.count or 0

        # Get unique bots accessed
        bots_result = db.table("member_activity_log").select(
            "bot_id"
        ).eq("membership_id", m["id"]).gte(
            "created_at", period_start.isoformat()
        ).not_.is_("bot_id", "null").execute()
        bots_accessed[m["id"]] = list(set(b["bot_id"] for b in bots_result.data if b["bot_id"]))

    # Get leads generated and diary entries per member for this period
    leads_by_user = {}
    diary_by_user = {}

    leads_result = db.table("lead_agent_prospects").select(
        "created_by"
    ).eq("org_id", org_id).gte(
        "created_at", period_start.isoformat()
    ).not_.is_("created_by", "null").execute()

    for p in leads_result.data:
        uid = p["created_by"]
        leads_by_user[uid] = leads_by_user.get(uid, 0) + 1

    # Get all prospect IDs for this org to filter journal entries
    org_prospect_ids = db.table("lead_agent_prospects").select(
        "id"
    ).eq("org_id", org_id).execute()
    prospect_ids = [p["id"] for p in org_prospect_ids.data]

    if prospect_ids:
        diary_result = db.table("lead_agent_journal_entries").select(
            "user_id"
        ).in_("prospect_id", prospect_ids).gte(
            "created_at", period_start.isoformat()
        ).execute()

        for d in diary_result.data:
            uid = d["user_id"]
            diary_by_user[uid] = diary_by_user.get(uid, 0) + 1

    # Build member activity list
    member_activities = []
    active_count = 0
    total_activities = 0

    for m in members_result.data:
        count = activity_counts.get(m["id"], 0)
        total_activities += count

        if count > 0 or (m.get("last_active_at") and
            datetime.fromisoformat(m["last_active_at"].replace("Z", "+00:00")) >= period_start):
            active_count += 1

        member_activities.append(MemberActivity(
            user_id=m["user_id"],
            membership_id=m["id"],
            full_name=m["users"]["full_name"],
            telegram_username=m["users"].get("telegram_username"),
            role=m["role"],
            last_active_at=m.get("last_active_at"),
            activity_count=count,
            bots_accessed=bots_accessed.get(m["id"], []),
            leads_generated=leads_by_user.get(m["user_id"], 0),
            diary_entries=diary_by_user.get(m["user_id"], 0)
        ))

    # Sort by activity count (most active first)
    member_activities.sort(key=lambda x: x.activity_count, reverse=True)

    result = TeamAnalytics(
        period=period,
        period_start=period_start,
        period_end=period_end,
        total_members=len(members_result.data),
        active_members=active_count,
        total_activities=total_activities,
        members=member_activities
    )
    cache_set("analytics", cache_key, result)
    return result


@router.get("/orgs/{org_id}/analytics/agents")
async def get_agent_analytics(
    org_id: str,
    period: str = "week",
    x_telegram_init_data: str = Header(...)
) -> AgentAnalytics:
    """Get agent usage analytics (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    # Check cache
    cache_key = f"agent_analytics:{org_id}:{period}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Calculate period bounds
    now = datetime.now(timezone.utc)
    if period == "day":
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        period_start = now - timedelta(days=now.weekday())
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        period_start = now - timedelta(days=7)

    period_end = now

    # Get all bots
    bots_result = db.table("bot_registry").select("id, name, icon").eq("is_active", True).execute()

    # Get activity stats per bot
    agent_usage = []
    total_tasks = 0

    for bot in bots_result.data:
        # Count task_completed activities for this bot
        tasks_result = db.table("member_activity_log").select(
            "id", count="exact"
        ).eq("org_id", org_id).eq("bot_id", bot["id"]).eq(
            "action_type", "task_completed"
        ).gte("created_at", period_start.isoformat()).execute()

        task_count = tasks_result.count or 0
        total_tasks += task_count

        # Count unique users for this bot
        users_result = db.table("member_activity_log").select(
            "user_id"
        ).eq("org_id", org_id).eq("bot_id", bot["id"]).gte(
            "created_at", period_start.isoformat()
        ).execute()
        unique_users = len(set(u["user_id"] for u in users_result.data))

        agent_usage.append(AgentUsage(
            bot_id=bot["id"],
            bot_name=bot["name"],
            bot_icon=bot.get("icon"),
            task_count=task_count,
            active_users=unique_users
        ))

    # Sort by task count (most used first)
    agent_usage.sort(key=lambda x: x.task_count, reverse=True)

    result = AgentAnalytics(
        period=period,
        period_start=period_start,
        period_end=period_end,
        total_tasks=total_tasks,
        agents=agent_usage
    )
    cache_set("analytics", cache_key, result)
    return result


@router.get("/orgs/{org_id}/analytics/lead-agent-overview")
async def get_lead_agent_overview(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> LeadAgentOverview:
    """Get lead agent overview stats for admin dashboard."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    cache_key = f"la_overview:{org_id}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Count active leads (all statuses except closed)
    prospects = db.table("lead_agent_prospects").select(
        "status"
    ).eq("org_id", org_id).execute()

    active_leads = sum(1 for p in prospects.data if p["status"] != "closed")

    # Count pending scheduled follow-ups
    followups = db.table("lead_agent_scheduled_notifications").select(
        "id", count="exact"
    ).eq("status", "pending").execute()

    # Filter to only this org's prospects
    org_prospect_ids = [p["id"] for p in db.table("lead_agent_prospects").select(
        "id"
    ).eq("org_id", org_id).execute().data]

    scheduled_count = 0
    if org_prospect_ids:
        org_followups = db.table("lead_agent_scheduled_notifications").select(
            "id", count="exact"
        ).eq("status", "pending").in_(
            "prospect_id", org_prospect_ids
        ).execute()
        scheduled_count = org_followups.count or 0

    # Get today's bot task events for lead agent
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    tasks_result = db.table("bot_task_log").select(
        "task_type, task_detail"
    ).eq("org_id", org_id).gte(
        "created_at", today_start.isoformat()
    ).order("created_at", desc=True).limit(20).execute()

    today_events = []
    # Track task types and business names for summary
    task_counts = {}
    businesses = set()
    for t in tasks_result.data:
        task_type = t["task_type"]
        detail = t.get("task_detail")
        biz_name = None
        if isinstance(detail, str):
            today_events.append(f"{task_type}: {detail[:80]}")
            biz_name = detail[:80]
        elif isinstance(detail, dict):
            biz_name = detail.get("business_name") or detail.get("summary", "")
            today_events.append(f"{task_type}: {biz_name[:80]}" if biz_name else task_type)
        else:
            today_events.append(task_type)
        # Collect for summary
        friendly = task_type.replace("_", " ")
        task_counts[friendly] = task_counts.get(friendly, 0) + 1
        if biz_name:
            businesses.add(biz_name.strip()[:40])

    # Build natural language summary
    today_summary = ""
    if task_counts:
        parts = [f"{count} {name}" for name, count in task_counts.items()]
        summary_parts = ", ".join(parts)
        if businesses:
            biz_list = list(businesses)
            if len(biz_list) <= 3:
                biz_str = ", ".join(biz_list[:-1]) + (" and " + biz_list[-1] if len(biz_list) > 1 else biz_list[0])
            else:
                biz_str = ", ".join(biz_list[:3]) + f" and {len(biz_list) - 3} more"
            today_summary = f"{summary_parts} for {biz_str}."
        else:
            today_summary = f"{summary_parts} today."

    result = LeadAgentOverview(
        active_leads=active_leads,
        scheduled_followups=scheduled_count,
        today_events=today_events,
        today_summary=today_summary
    )
    cache_set("analytics", cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD - BILLING
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/plans")
async def list_subscription_plans() -> List[SubscriptionPlan]:
    """List available subscription plans (public)."""
    # Check cache (plans rarely change)
    cached = cache_get("plans", "active_plans")
    if cached is not None:
        return cached

    db = get_supabase_admin()

    result = db.table("subscription_plans").select("*").eq("is_active", True).order("sort_order").execute()

    plans = [SubscriptionPlan(
        id=p["id"],
        name=p["name"],
        description=p.get("description"),
        price_monthly=p["price_monthly"],
        price_yearly=p.get("price_yearly"),
        max_members=p.get("max_members"),
        max_customers=p.get("max_customers"),
        features=p.get("features", []),
        is_active=p["is_active"]
    ) for p in result.data]
    cache_set("plans", "active_plans", plans)
    return plans


@router.get("/orgs/{org_id}/billing")
async def get_billing_overview(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> BillingOverview:
    """Get billing overview for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    # Check cache
    cache_key = f"billing:{org_id}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Get subscription
    sub_result = db.table("org_subscriptions").select(
        "*, subscription_plans(*)"
    ).eq("org_id", org_id).single().execute()

    if not sub_result.data:
        # Create default free subscription if none exists
        plan = db.table("subscription_plans").select("*").eq("id", "free").single().execute()
        default_end = datetime.now(timezone.utc) + timedelta(days=36500)  # 100 years
        new_sub = db.table("org_subscriptions").insert({
            "org_id": org_id,
            "plan_id": "free",
            "current_period_end": default_end.isoformat()
        }).execute()
        sub_result = db.table("org_subscriptions").select(
            "*, subscription_plans(*)"
        ).eq("id", new_sub.data[0]["id"]).single().execute()

    s = sub_result.data
    plan_data = s["subscription_plans"]

    subscription = OrgSubscription(
        id=s["id"],
        org_id=s["org_id"],
        plan_id=s["plan_id"],
        plan=SubscriptionPlan(
            id=plan_data["id"],
            name=plan_data["name"],
            description=plan_data.get("description"),
            price_monthly=plan_data["price_monthly"],
            price_yearly=plan_data.get("price_yearly"),
            max_members=plan_data.get("max_members"),
            max_customers=plan_data.get("max_customers"),
            features=plan_data.get("features", []),
            is_active=plan_data["is_active"]
        ),
        billing_cycle=s["billing_cycle"],
        status=s["status"],
        trial_ends_at=s.get("trial_ends_at"),
        current_period_start=s["current_period_start"],
        current_period_end=s["current_period_end"],
        canceled_at=s.get("canceled_at")
    )

    # Get usage stats
    members_count = db.table("memberships").select("id", count="exact").eq("org_id", org_id).execute()

    usage = {
        "members_used": members_count.count or 0,
        "members_limit": plan_data.get("max_members"),
    }

    # Get recent invoices
    invoices_result = db.table("invoices").select("*").eq("org_id", org_id).order(
        "issue_date", desc=True
    ).limit(10).execute()

    invoices = [Invoice(
        id=i["id"],
        org_id=i["org_id"],
        invoice_number=i["invoice_number"],
        subtotal=i["subtotal"],
        tax=i.get("tax", 0),
        total=i["total"],
        currency=i.get("currency", "USD"),
        status=i["status"],
        issue_date=i["issue_date"],
        due_date=i["due_date"],
        paid_at=i.get("paid_at"),
        line_items=i.get("line_items", []),
        pdf_url=i.get("pdf_url")
    ) for i in invoices_result.data]

    result = BillingOverview(
        subscription=subscription,
        usage=usage,
        invoices=invoices
    )
    cache_set("org", cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD - PRODUCTS & SERVICES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/orgs/{org_id}/products")
async def list_products(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> List[Product]:
    """
    List all products/services for an organization.
    Viewable by all members, but only editable by admins.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_member(tg_user.id, org_id)

    # Check cache
    cache_key = f"products:{org_id}"
    cached = cache_get("catalog", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    # Get all products
    result = db.table("lead_agent_products").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).execute()

    products = [Product(**p) for p in result.data]
    cache_set("catalog", cache_key, products)
    return products


@router.post("/orgs/{org_id}/products")
async def create_product(
    org_id: str,
    data: ProductCreate,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Create a new product/service (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Create product
    product_data = {
        "org_id": org_id,
        "name": data.name,
        "description": data.description,
        "price": str(data.price) if data.price else None,
        "is_active": True
    }

    result = db.table("lead_agent_products").insert(product_data).execute()
    cache_delete("catalog", f"products:{org_id}")
    return Product(**result.data[0])


@router.patch("/orgs/{org_id}/products/{product_id}")
async def update_product(
    org_id: str,
    product_id: str,
    data: ProductUpdate,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Update a product/service (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Verify product belongs to this org
    product_check = db.table("lead_agent_products").select("id").eq(
        "id", product_id
    ).eq("org_id", org_id).execute()

    if not product_check.data:
        raise HTTPException(404, "Product not found")

    # Build update data
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.price is not None:
        update_data["price"] = str(data.price)
    if data.is_active is not None:
        update_data["is_active"] = data.is_active

    if not update_data:
        raise HTTPException(400, "No fields to update")

    result = db.table("lead_agent_products").update(update_data).eq(
        "id", product_id
    ).execute()

    cache_delete("catalog", f"products:{org_id}")
    return Product(**result.data[0])


@router.delete("/orgs/{org_id}/products/{product_id}")
async def delete_product(
    org_id: str,
    product_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a product/service (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    # Verify product belongs to this org and get name for response
    product = db.table("lead_agent_products").select("id, name").eq(
        "id", product_id
    ).eq("org_id", org_id).execute()

    if not product.data:
        raise HTTPException(404, "Product not found")

    # Delete product
    db.table("lead_agent_products").delete().eq("id", product_id).execute()

    cache_delete("catalog", f"products:{org_id}")
    return {"status": "deleted", "product_id": product_id, "name": product.data[0]["name"]}

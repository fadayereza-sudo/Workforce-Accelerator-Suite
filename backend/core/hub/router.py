"""
Core Hub — platform-level routes.

Routes:
- /me — User profile
- /orgs — Organization CRUD
- /orgs/{org_id}/invite-code — Invite management
- /membership-requests — Join flow
- /orgs/{org_id}/members — Member management
- /bots — Bot registry
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks

from core.auth import get_telegram_user, verify_org_member, verify_org_admin, cached_get_user_id
from core.database import get_supabase_admin
from core.cache import cache_get, cache_set, cache_delete, cache_invalidate
from core.notifications import (
    notify_admin_new_request,
    notify_user_approved,
    notify_user_rejected,
    send_invite_link_to_admin
)
from core.models import (
    Organization, OrgCreate, InviteCode, OrgStats, OrgDetails, OrgUpdate,
    MembershipRequest, MembershipRequestCreate, MembershipRequestResponse,
    MembershipApproval, Member, BotAccess, AppAccess, MemberBotsUpdate, MemberAppsUpdate, MemberRoleUpdate,
)
from config import settings

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# USER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(x_telegram_init_data: str = Header(...)) -> dict:
    """Get current user profile and their organization context."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    print(f"[/me] Telegram user: id={tg_user.id}, username={tg_user.username}, name={tg_user.first_name}")

    result = db.table("users").select("*").eq("telegram_id", tg_user.id).execute()

    if not result.data:
        print(f"[/me] User not found - needs to sign up via org creation or invite code")
        return {
            "user": None,
            "memberships": [],
            "pending_requests": []
        }

    user = result.data[0]
    print(f"[/me] Found existing user: id={user['id']}, name={user['full_name']}")

    memberships = db.table("memberships").select(
        "*, organizations(*)"
    ).eq("user_id", user["id"]).execute()

    print(f"[/me] User {user['id']} has {len(memberships.data)} memberships")
    for m in memberships.data:
        print(f"[/me]   - Membership: id={m['id']}, org={m['organizations']['name']}, role={m['role']}")

    if memberships.data:
        now = datetime.now(timezone.utc).isoformat()
        for m in memberships.data:
            db.table("memberships").update({
                "last_active_at": now
            }).eq("id", m["id"]).execute()

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

    user_result = db.table("users").select("id").eq("telegram_id", tg_user.id).execute()

    if user_result.data:
        user_id = user_result.data[0]["id"]
        db.table("users").update({
            "full_name": data.admin_full_name
        }).eq("id", user_id).execute()
    else:
        new_user = db.table("users").insert({
            "telegram_id": tg_user.id,
            "telegram_username": tg_user.username,
            "full_name": data.admin_full_name,
            "avatar_url": tg_user.photo_url
        }).execute()
        user_id = new_user.data[0]["id"]

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

    membership_data = {
        "user_id": user_id,
        "org_id": org["id"],
        "role": "admin"
    }
    db.table("memberships").insert(membership_data).execute()

    cache_delete("auth", f"user:{tg_user.id}")

    return org


@router.get("/orgs/{org_id}")
async def get_organization(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Get organization details (must be a member)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, role = verify_org_member(tg_user.id, org_id)
    db = get_supabase_admin()

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
    verify_org_admin(tg_user.id, org_id)

    cache_key = f"org_details:{org_id}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    org = db.table("organizations").select("*").eq("id", org_id).single().execute()
    if not org.data:
        raise HTTPException(404, "Organization not found")

    members_count = db.table("memberships").select("id", count="exact").eq(
        "org_id", org_id
    ).execute()

    pending_count = db.table("membership_requests").select("id", count="exact").eq(
        "org_id", org_id
    ).eq("status", "pending").execute()

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
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description

    if not update_data:
        raise HTTPException(400, "No fields to update")

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
    verify_org_admin(tg_user.id, org_id)

    invite_cache_key = f"invite:{org_id}"
    cached = cache_get("org", invite_cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    org = db.table("organizations").select("name, invite_code, invite_code_expires_at").eq(
        "id", org_id
    ).single().execute()

    expires_at = datetime.fromisoformat(org.data["invite_code_expires_at"].replace("Z", "+00:00"))
    is_expired = datetime.now(timezone.utc) > expires_at

    bot_username = settings.BOT_USERNAME if hasattr(settings, 'BOT_USERNAME') else "apex_workforce_bot"
    app_shortname = settings.MINI_APP_SHORTNAME if hasattr(settings, 'MINI_APP_SHORTNAME') else "hub"
    app_url = f"https://t.me/{bot_username}/{app_shortname}"

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
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    new_code = secrets.token_urlsafe(8)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    db.table("organizations").update({
        "invite_code": new_code,
        "invite_code_expires_at": expires_at.isoformat()
    }).eq("id", org_id).execute()

    org = db.table("organizations").select("name").eq("id", org_id).single().execute()

    bot_username = settings.BOT_USERNAME if hasattr(settings, 'BOT_USERNAME') else "apex_workforce_bot"
    app_shortname = settings.MINI_APP_SHORTNAME if hasattr(settings, 'MINI_APP_SHORTNAME') else "hub"
    app_url = f"https://t.me/{bot_username}/{app_shortname}"

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
    """Send the invite link message to the admin via Telegram."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    org = db.table("organizations").select("name, invite_code, invite_code_expires_at").eq(
        "id", org_id
    ).single().execute()

    expires_at = datetime.fromisoformat(org.data["invite_code_expires_at"].replace("Z", "+00:00"))
    is_expired = datetime.now(timezone.utc) > expires_at

    if is_expired:
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

    bot_username = settings.BOT_USERNAME if hasattr(settings, 'BOT_USERNAME') else "apex_workforce_bot"
    app_shortname = settings.MINI_APP_SHORTNAME if hasattr(settings, 'MINI_APP_SHORTNAME') else "hub"
    app_url = f"https://t.me/{bot_username}/{app_shortname}"

    hours_remaining = max(1, int((expires_at - datetime.now(timezone.utc)).total_seconds() / 3600))

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
    """Request to join an organization via invite code."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    user_result = db.table("users").select("*").eq("telegram_id", tg_user.id).execute()

    if user_result.data:
        user = user_result.data[0]
        if data.full_name:
            db.table("users").update({
                "full_name": data.full_name
            }).eq("id", user["id"]).execute()
    else:
        user_data = {
            "telegram_id": tg_user.id,
            "telegram_username": tg_user.username,
            "full_name": data.full_name,
            "avatar_url": tg_user.photo_url
        }
        user_result = db.table("users").insert(user_data).execute()
        user = user_result.data[0]

    org = db.table("organizations").select("id, name, created_by, invite_code_expires_at").eq(
        "invite_code", data.invite_code
    ).execute()

    if not org.data:
        raise HTTPException(404, "Invalid invite code")

    org_data = org.data[0]

    expires_at = datetime.fromisoformat(org_data["invite_code_expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(410, "This invite link has expired")

    existing = db.table("memberships").select("id").eq(
        "user_id", user["id"]
    ).eq("org_id", org_data["id"]).execute()

    if existing.data:
        raise HTTPException(400, "Already a member of this organization")

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

    request_data = {
        "user_id": user["id"],
        "org_id": org_data["id"],
        "full_name": data.full_name,
        "telegram_username": tg_user.username,
        "status": "pending"
    }
    request_result = db.table("membership_requests").insert(request_data).execute()
    request = request_result.data[0]

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
    verify_org_admin(tg_user.id, org_id)

    cache_key = f"requests:{org_id}:{status or 'all'}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

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

    request = db.table("membership_requests").select(
        "*, organizations(name)"
    ).eq("id", request_id).single().execute()

    if not request.data:
        raise HTTPException(404, "Request not found")

    request_data = request.data

    admin_user_id = verify_org_admin(tg_user.id, request_data["org_id"])

    if data.approved:
        membership_data = {
            "user_id": request_data["user_id"],
            "org_id": request_data["org_id"],
            "role": "member"
        }
        new_membership = db.table("memberships").insert(membership_data).execute()

        bot_names = []
        for bot_id in data.bot_ids:
            access_data = {
                "membership_id": new_membership.data[0]["id"],
                "bot_id": bot_id,
                "granted_by": admin_user_id
            }
            db.table("bot_member_access").insert(access_data).execute()

            bot = db.table("bot_registry").select("name").eq("id", bot_id).execute()
            if bot.data:
                bot_names.append(bot.data[0]["name"])

        db.table("membership_requests").update({
            "status": "approved"
        }).eq("id", request_id).execute()

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

        org_id = request_data["org_id"]
        cache_invalidate("org", f"requests:{org_id}")
        cache_invalidate("org", f"members:{org_id}")
        cache_invalidate("org", f"org_details:{org_id}")

        return {"status": "approved", "bot_access": bot_names}

    else:
        db.table("membership_requests").update({
            "status": "rejected"
        }).eq("id", request_id).execute()

        cache_invalidate("org", f"requests:{request_data['org_id']}")

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
    verify_org_member(tg_user.id, org_id)

    cache_key = f"members:{org_id}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    members = db.table("memberships").select(
        "*, users(full_name, telegram_username)"
    ).eq("org_id", org_id).execute()

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

        app_access_result = db.table("app_member_access").select(
            "app_id, app_registry(name)"
        ).eq("membership_id", m["id"]).execute()

        app_access = [
            AppAccess(
                app_id=a["app_id"],
                app_name=a["app_registry"]["name"] if a.get("app_registry") else a["app_id"],
                granted=True
            )
            for a in app_access_result.data
        ]

        result.append(Member(
            id=m["id"],
            user_id=m["user_id"],
            full_name=m["users"]["full_name"],
            telegram_username=m["users"]["telegram_username"],
            role=m["role"],
            bot_access=bot_access,
            app_access=app_access,
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
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    target = db.table("memberships").select("*, users(full_name)").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    if target.data["role"] == "admin":
        raise HTTPException(400, "Cannot remove an admin member")

    db.table("bot_member_access").delete().eq("membership_id", member_id).execute()
    db.table("memberships").delete().eq("id", member_id).execute()

    cache_invalidate("org", f"members:{org_id}")
    cache_invalidate("org", f"org_details:{org_id}")
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
    admin_user_id = verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    target = db.table("memberships").select("id").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    current_access = db.table("bot_member_access").select("bot_id").eq(
        "membership_id", member_id
    ).execute()
    current_bot_ids = set(a["bot_id"] for a in current_access.data)
    new_bot_ids = set(data.bot_ids)

    to_remove = current_bot_ids - new_bot_ids
    if to_remove:
        for bot_id in to_remove:
            db.table("bot_member_access").delete().eq(
                "membership_id", member_id
            ).eq("bot_id", bot_id).execute()

    to_add = new_bot_ids - current_bot_ids
    for bot_id in to_add:
        db.table("bot_member_access").insert({
            "membership_id": member_id,
            "bot_id": bot_id,
            "granted_by": admin_user_id
        }).execute()

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
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    if data.role not in ["admin", "member"]:
        raise HTTPException(400, "Invalid role. Must be 'admin' or 'member'")

    target = db.table("memberships").select("id, user_id, users(full_name)").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    db.table("memberships").update({
        "role": data.role,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", member_id).execute()

    cache_delete("org", f"members:{org_id}")
    cache_delete("org", f"orgDetails:{org_id}")

    return {
        "status": "updated",
        "member_id": member_id,
        "new_role": data.role,
        "member_name": target.data["users"]["full_name"]
    }


@router.get("/orgs/{org_id}/apps/{app_id}/members")
async def get_app_members(
    org_id: str,
    app_id: str,
    x_telegram_init_data: str = Header(...)
) -> List[dict]:
    """Get all org members with their access status for a specific app."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    members = db.table("memberships").select(
        "id, user_id, role, users(full_name, telegram_username)"
    ).eq("org_id", org_id).execute()

    access = db.table("app_member_access").select(
        "membership_id"
    ).eq("app_id", app_id).execute()
    granted_membership_ids = set(a["membership_id"] for a in access.data)

    result = []
    for m in members.data:
        has_access = m["role"] == "admin" or m["id"] in granted_membership_ids
        result.append({
            "membership_id": m["id"],
            "user_id": m["user_id"],
            "full_name": m["users"]["full_name"],
            "telegram_username": m["users"].get("telegram_username"),
            "role": m["role"],
            "has_access": has_access,
            "implicit": m["role"] == "admin"
        })

    return result


@router.put("/orgs/{org_id}/members/{member_id}/apps")
async def update_member_apps(
    org_id: str,
    member_id: str,
    data: MemberAppsUpdate,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Update app access for a member (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    admin_user_id = verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    target = db.table("memberships").select("id").eq(
        "id", member_id
    ).eq("org_id", org_id).single().execute()

    if not target.data:
        raise HTTPException(404, "Member not found")

    subs = db.table("org_app_subscriptions").select("app_id").eq(
        "org_id", org_id
    ).eq("active", True).execute()
    subscribed_app_ids = set(s["app_id"] for s in subs.data)

    for app_id in data.app_ids:
        if app_id not in subscribed_app_ids:
            raise HTTPException(400, f"App {app_id} is not subscribed")

    current = db.table("app_member_access").select("app_id").eq(
        "membership_id", member_id
    ).execute()
    current_ids = set(a["app_id"] for a in current.data)
    new_ids = set(data.app_ids)

    for app_id in (current_ids - new_ids):
        db.table("app_member_access").delete().eq(
            "membership_id", member_id
        ).eq("app_id", app_id).execute()

    for app_id in (new_ids - current_ids):
        db.table("app_member_access").insert({
            "membership_id": member_id,
            "app_id": app_id,
            "granted_by": admin_user_id
        }).execute()

    app_names = []
    if data.app_ids:
        apps = db.table("app_registry").select("id, name").in_("id", data.app_ids).execute()
        app_names = [a["name"] for a in apps.data]

    cache_delete("org", f"members:{org_id}")

    return {
        "status": "updated",
        "app_access": app_names
    }


@router.get("/bots")
async def list_available_bots(
    x_telegram_init_data: str = Header(...)
) -> List[dict]:
    """List all available bots in the registry."""
    get_telegram_user(x_telegram_init_data)

    cached = cache_get("catalog", "bots:active")
    if cached is not None:
        return cached

    db = get_supabase_admin()
    bots = db.table("bot_registry").select("*").eq("is_active", True).execute()

    cache_set("catalog", "bots:active", bots.data)
    return bots.data


# ─────────────────────────────────────────────────────────────────────────────
# APP CATALOG & SUBSCRIPTIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/apps/catalog")
async def list_app_catalog(
    x_telegram_init_data: str = Header(...)
) -> List[dict]:
    """List all available apps on the platform."""
    get_telegram_user(x_telegram_init_data)

    cached = cache_get("catalog", "apps:active")
    if cached is not None:
        return cached

    db = get_supabase_admin()
    result = db.table("app_registry").select(
        "id, name, description, icon, monthly_price, annual_price"
    ).eq("is_active", True).order("sort_order").execute()

    cache_set("catalog", "apps:active", result.data)
    return result.data


@router.get("/orgs/{org_id}/apps")
async def list_org_apps(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> List[dict]:
    """List apps the organization is subscribed to."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    cache_key = f"org_apps:{org_id}"
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()
    subs = db.table("org_app_subscriptions").select(
        "app_id, app_registry(id, name, description, icon)"
    ).eq("org_id", org_id).eq("active", True).execute()

    apps = [s["app_registry"] for s in subs.data if s.get("app_registry")]
    cache_set("org", cache_key, apps)
    return apps


@router.post("/orgs/{org_id}/apps/{app_id}/subscribe")
async def subscribe_to_app(
    org_id: str,
    app_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Subscribe organization to an app (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    app = db.table("app_registry").select("id, name").eq(
        "id", app_id
    ).eq("is_active", True).execute()

    if not app.data:
        raise HTTPException(404, "App not found")

    existing = db.table("org_app_subscriptions").select("id, active").eq(
        "org_id", org_id
    ).eq("app_id", app_id).execute()

    if existing.data:
        if existing.data[0]["active"]:
            raise HTTPException(400, "Already subscribed to this app")
        db.table("org_app_subscriptions").update({
            "active": True,
            "canceled_at": None,
            "started_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("org_app_subscriptions").insert({
            "org_id": org_id,
            "app_id": app_id,
            "active": True,
            "billing_cycle": "monthly"
        }).execute()

    cache_delete("org", f"org_apps:{org_id}")

    return {
        "status": "subscribed",
        "app_id": app_id,
        "app_name": app.data[0]["name"]
    }


@router.delete("/orgs/{org_id}/apps/{app_id}/subscribe")
async def unsubscribe_from_app(
    org_id: str,
    app_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Unsubscribe organization from an app (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)
    db = get_supabase_admin()

    sub = db.table("org_app_subscriptions").select("id").eq(
        "org_id", org_id
    ).eq("app_id", app_id).eq("active", True).execute()

    if not sub.data:
        raise HTTPException(404, "No active subscription found for this app")

    db.table("org_app_subscriptions").update({
        "active": False,
        "canceled_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", sub.data[0]["id"]).execute()

    app = db.table("app_registry").select("name").eq("id", app_id).execute()
    app_name = app.data[0]["name"] if app.data else app_id

    cache_delete("org", f"org_apps:{org_id}")

    return {
        "status": "unsubscribed",
        "app_id": app_id,
        "app_name": app_name
    }

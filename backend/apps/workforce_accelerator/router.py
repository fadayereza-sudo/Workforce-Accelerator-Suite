"""
Workforce Accelerator — app-level routes.

These are routes shared across the entire WA app (not agent-specific):
- Product CRUD (used by lead agent and other agents)
- Activity tracking (admin dashboard)
- Team & agent analytics (admin dashboard)
- Lead agent overview (admin dashboard)
- Currency settings
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Header, HTTPException, Query

from core.auth import get_telegram_user, verify_org_member, verify_org_admin
from core.database import get_supabase_admin
from core.cache import cache_get, cache_set, cache_delete

from apps.workforce_accelerator.models import (
    Product, ProductCreate, ProductUpdate, CurrencyUpdate,
    ActivityLogCreate, MemberActivity, TeamAnalytics,
    AgentUsage, AgentAnalytics, LeadAgentOverview
)
from apps.workforce_accelerator.services import get_org_currency

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/products")
async def list_products(
    org_id: str = Query(...),
    x_telegram_init_data: str = Header(...)
) -> List[Product]:
    """List all products for the organization."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    cache_key = f"products:{org_id}"
    cached = cache_get("catalog", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()
    result = db.table("lead_agent_products").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).execute()

    products = [Product(**p) for p in result.data]
    cache_set("catalog", cache_key, products)
    return products


@router.post("/products")
async def create_product(
    org_id: str = Query(...),
    data: ProductCreate = ...,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Create a new product."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()
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


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    data: ProductUpdate,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Update a product."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    product_result = db.table("lead_agent_products").select("org_id").eq(
        "id", product_id
    ).single().execute()

    if not product_result.data:
        raise HTTPException(404, "Product not found")

    verify_org_member(tg_user.id, product_result.data["org_id"])

    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.price is not None:
        update_data["price"] = str(data.price)
    if data.is_active is not None:
        update_data["is_active"] = data.is_active

    result = db.table("lead_agent_products").update(update_data).eq(
        "id", product_id
    ).execute()

    cache_delete("catalog", f"products:{product_result.data['org_id']}")
    return Product(**result.data[0])


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a product."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    product_result = db.table("lead_agent_products").select("org_id").eq(
        "id", product_id
    ).single().execute()

    if not product_result.data:
        raise HTTPException(404, "Product not found")

    verify_org_member(tg_user.id, product_result.data["org_id"])

    db.table("lead_agent_products").delete().eq("id", product_id).execute()

    cache_delete("catalog", f"products:{product_result.data['org_id']}")
    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# CURRENCY SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/currency")
async def update_currency(
    org_id: str = Query(...),
    data: CurrencyUpdate = ...,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Update organization's lead agent currency (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    org_result = db.table("organizations").select("settings").eq(
        "id", org_id
    ).single().execute()

    settings_dict = org_result.data.get("settings", {}) if org_result.data else {}
    settings_dict["lead_agent_currency"] = data.currency.upper()

    db.table("organizations").update({
        "settings": settings_dict
    }).eq("id", org_id).execute()

    return {"currency": data.currency.upper(), "status": "updated"}


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN PRODUCT ENDPOINTS (path-based, used by hub dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/products")
async def list_org_products(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> List[Product]:
    """List all products/services for an organization (any member)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    cache_key = f"products:{org_id}"
    cached = cache_get("catalog", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()
    result = db.table("lead_agent_products").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).execute()

    products = [Product(**p) for p in result.data]
    cache_set("catalog", cache_key, products)
    return products


@router.post("/orgs/{org_id}/products")
async def create_org_product(
    org_id: str,
    data: ProductCreate,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Create a new product/service."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)
    db = get_supabase_admin()

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
async def update_org_product(
    org_id: str,
    product_id: str,
    data: ProductUpdate,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Update a product/service."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)
    db = get_supabase_admin()

    product_check = db.table("lead_agent_products").select("id").eq(
        "id", product_id
    ).eq("org_id", org_id).execute()

    if not product_check.data:
        raise HTTPException(404, "Product not found")

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
async def delete_org_product(
    org_id: str,
    product_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a product/service."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)
    db = get_supabase_admin()

    product = db.table("lead_agent_products").select("id, name").eq(
        "id", product_id
    ).eq("org_id", org_id).execute()

    if not product.data:
        raise HTTPException(404, "Product not found")

    db.table("lead_agent_products").delete().eq("id", product_id).execute()

    cache_delete("catalog", f"products:{org_id}")
    return {"status": "deleted", "product_id": product_id, "name": product.data[0]["name"]}


# ─────────────────────────────────────────────────────────────────────────────
# ACTIVITY TRACKING
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/activity")
async def log_activity(
    data: ActivityLogCreate,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Log member activity (called from mini-apps)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, _ = verify_org_member(tg_user.id, data.org_id)
    db = get_supabase_admin()

    membership = db.table("memberships").select("id").eq(
        "user_id", user_id
    ).eq("org_id", data.org_id).single().execute()

    activity_data = {
        "membership_id": membership.data["id"],
        "user_id": user_id,
        "org_id": data.org_id,
        "bot_id": data.bot_id,
        "action_type": data.action_type,
        "action_detail": data.action_detail
    }
    db.table("member_activity_log").insert(activity_data).execute()

    db.table("memberships").update({
        "last_active_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", membership.data["id"]).execute()

    return {"status": "logged"}


# ─────────────────────────────────────────────────────────────────────────────
# TEAM ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/analytics/team")
async def get_team_analytics(
    org_id: str,
    period: str = "week",
    x_telegram_init_data: str = Header(...)
) -> TeamAnalytics:
    """Get team activity analytics (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    cache_key = f"team_analytics:{org_id}:{period}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

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

    members_result = db.table("memberships").select(
        "id, user_id, role, last_active_at, users(full_name, telegram_username)"
    ).eq("org_id", org_id).execute()

    activity_counts = {}
    bots_accessed = {}

    for m in members_result.data:
        activity_result = db.table("member_activity_log").select(
            "id", count="exact"
        ).eq("membership_id", m["id"]).gte(
            "created_at", period_start.isoformat()
        ).execute()
        activity_counts[m["id"]] = activity_result.count or 0

        bots_result = db.table("member_activity_log").select(
            "bot_id"
        ).eq("membership_id", m["id"]).gte(
            "created_at", period_start.isoformat()
        ).not_.is_("bot_id", "null").execute()
        bots_accessed[m["id"]] = list(set(b["bot_id"] for b in bots_result.data if b["bot_id"]))

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


# ─────────────────────────────────────────────────────────────────────────────
# AGENT ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/analytics/agents")
async def get_agent_analytics(
    org_id: str,
    period: str = "week",
    x_telegram_init_data: str = Header(...)
) -> AgentAnalytics:
    """Get agent usage analytics (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    cache_key = f"agent_analytics:{org_id}:{period}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

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

    bots_result = db.table("bot_registry").select("id, name, icon").eq("is_active", True).execute()

    agent_usage = []
    total_tasks = 0

    for bot in bots_result.data:
        tasks_result = db.table("member_activity_log").select(
            "id", count="exact"
        ).eq("org_id", org_id).eq("bot_id", bot["id"]).eq(
            "action_type", "task_completed"
        ).gte("created_at", period_start.isoformat()).execute()

        task_count = tasks_result.count or 0
        total_tasks += task_count

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


# ─────────────────────────────────────────────────────────────────────────────
# LEAD AGENT OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/analytics/lead-agent-overview")
async def get_lead_agent_overview(
    org_id: str,
    x_telegram_init_data: str = Header(...)
) -> LeadAgentOverview:
    """Get lead agent overview stats for admin dashboard."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    cache_key = f"la_overview:{org_id}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    prospects = db.table("lead_agent_prospects").select(
        "status"
    ).eq("org_id", org_id).execute()

    active_leads = sum(1 for p in prospects.data if p["status"] != "closed")

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

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    tasks_result = db.table("bot_task_log").select(
        "task_type, task_detail"
    ).eq("org_id", org_id).gte(
        "created_at", today_start.isoformat()
    ).order("created_at", desc=True).limit(20).execute()

    today_events = []
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
        friendly = task_type.replace("_", " ")
        task_counts[friendly] = task_counts.get(friendly, 0) + 1
        if biz_name:
            businesses.add(biz_name.strip()[:40])

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

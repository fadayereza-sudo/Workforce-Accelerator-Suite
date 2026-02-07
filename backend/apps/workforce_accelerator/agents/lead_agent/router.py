"""
Lead Agent Bot API — B2B Lead generation and management endpoints.

Handles:
- Prospect scraping from URLs (via GPT-4o-mini)
- AI-powered insights generation (via GPT-4o)
- Prospect status management
- vCard generation for contacts
- Journal entries and AI follow-up scheduling
- Dashboard stats
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks, Query

from core.auth import get_telegram_user, verify_org_member, verify_org_admin
from core.database import get_supabase_admin
from core.cache import cache_get, cache_set, cache_delete
from core.task_logger import TaskLogger, TaskTimer
from config import settings

from apps.workforce_accelerator.models import (
    Product, ProspectManualCreate, ProspectStatusUpdate, ProspectContactUpdate,
    ProspectCard, PainPoint, ScrapeRequest, SearchHistory,
    LeadAgentDashboard, JournalEntryCreate, JournalEntryUpdate, JournalEntry
)
from apps.workforce_accelerator.services import get_org_currency
from apps.workforce_accelerator.agents.lead_agent.scraper import URLScraperService, ScraperError
from apps.workforce_accelerator.agents.lead_agent.service import LeadAgentAI

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────────────────────

async def generate_ai_insights_task(
    prospect_id: str,
    org_id: str,
    business_description: Optional[str] = None
):
    """
    Background task to generate AI insights for a prospect.

    Two-tier LLM pipeline:
    - Tier 1 (GPT-4o-mini): Already extracted business_description from URL (passed in)
    - Tier 2 (GPT-4o): Generate strategic insights, pain points, and call script
    """
    db = get_supabase_admin()

    try:
        prospect_result = db.table("lead_agent_prospects").select("*").eq(
            "id", prospect_id
        ).single().execute()

        if not prospect_result.data:
            return

        prospect_data = prospect_result.data

        products_result = db.table("lead_agent_products").select("*").eq(
            "org_id", org_id
        ).eq("is_active", True).execute()

        products = [Product(**p) for p in products_result.data]

        ai = LeadAgentAI(settings.openai_api_key)

        with TaskTimer() as timer:
            summary, pain_points, call_script = await ai.generate_prospect_insights(
                business_name=prospect_data["business_name"],
                business_address=prospect_data.get("address"),
                business_website=prospect_data.get("website"),
                products=products,
                business_description=business_description
            )

        db.table("lead_agent_prospects").update({
            "business_summary": summary,
            "pain_points": [pp.dict() for pp in pain_points],
            "call_script": call_script,
            "ai_generated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", prospect_id).execute()

        TaskLogger.log(
            org_id=org_id,
            bot_id="lead-agent",
            task_type="insights_generated",
            task_detail={
                "prospect_id": prospect_id,
                "business_name": prospect_data["business_name"],
                "pain_points_count": len(pain_points)
            },
            app_id="workforce-accelerator",
            execution_time_ms=timer.execution_time_ms,
            tokens_used=0
        )

        print(f"[LeadAgent] AI insights generated for prospect {prospect_id}")

    except Exception as e:
        print(f"Error generating AI insights for prospect {prospect_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PROSPECT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/prospects")
async def list_prospects(
    org_id: str = Query(...),
    status: Optional[str] = Query(None),
    search_query: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    x_telegram_init_data: str = Header(...)
) -> List[ProspectCard]:
    """List prospects with optional filters."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    query = db.table("lead_agent_prospects").select("*").eq("org_id", org_id)

    if status:
        query = query.eq("status", status)
    if search_query:
        query = query.eq("search_query", search_query)

    result = query.order("created_at", desc=True).limit(limit).offset(offset).execute()

    cards = []
    for p in result.data:
        pain_points = [PainPoint(**pp) for pp in p.get("pain_points", [])]
        cards.append(ProspectCard(
            id=p["id"],
            business_name=p["business_name"],
            phone=p.get("phone"),
            email=p.get("email"),
            address=p.get("address"),
            website=p.get("website"),
            google_maps_url=p.get("google_maps_url"),
            summary=p.get("business_summary"),
            pain_points=pain_points,
            status=p["status"],
            search_query=p.get("search_query"),
            source=p.get("source", "gemini_search"),
            created_at=p["created_at"]
        ))

    return cards


@router.post("/prospects/scrape")
async def scrape_prospect(
    org_id: str = Query(...),
    data: ScrapeRequest = ...,
    background_tasks: BackgroundTasks = ...,
    x_telegram_init_data: str = Header(...)
) -> ProspectCard:
    """
    Scrape a prospect from a URL.

    Two-tier LLM pipeline:
    1. GPT-4o-mini (cheap): Fetch & extract business info from HTML
    2. GPT-4o (smart): Generate insights & pain points with pattern recognition

    Returns the prospect immediately, AI insights are generated in background.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, _ = verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    products = db.table("lead_agent_products").select("id").eq(
        "org_id", org_id
    ).eq("is_active", True).execute()

    if not products.data:
        raise HTTPException(
            status_code=400,
            detail="Please add at least one product or service before adding leads. The AI needs your products to generate relevant insights."
        )

    scraper = URLScraperService(settings.openai_api_key)

    print(f"[LeadAgent] Scraping URL: {data.url}")
    try:
        with TaskTimer() as scrape_timer:
            business = await scraper.scrape_business(data.url)
    except ScraperError as e:
        print(f"[LeadAgent] Scraper error: {e.technical_detail}")
        raise HTTPException(status_code=400, detail=e.message)

    dedup_hash = business.get_dedup_hash()
    existing = db.table("lead_agent_prospects").select("id").eq(
        "org_id", org_id
    ).eq("dedup_hash", dedup_hash).execute()

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="This business has already been added to your prospects."
        )

    prospect_data = {
        "org_id": org_id,
        "business_name": business.business_name,
        "phone": None,
        "email": None,
        "address": business.address,
        "website": business.website,
        "google_maps_url": business.google_maps_url,
        "dedup_hash": dedup_hash,
        "search_query": None,
        "source": "url_scrape",
        "status": "not_contacted",
        "created_by": user_id
    }

    result = db.table("lead_agent_prospects").insert(prospect_data).execute()
    prospect = result.data[0]

    TaskLogger.log(
        org_id=org_id,
        bot_id="lead-agent",
        task_type="prospect_scraped",
        task_detail={"business_name": business.business_name, "source": "url_scrape"},
        app_id="workforce-accelerator",
        triggered_by=user_id,
        execution_time_ms=scrape_timer.execution_time_ms
    )

    background_tasks.add_task(
        generate_ai_insights_task,
        prospect["id"],
        org_id,
        business.description
    )

    print(f"[LeadAgent] Created prospect: {business.business_name}")

    cache_delete("analytics", f"la_dashboard:{org_id}")

    return ProspectCard(
        id=prospect["id"],
        business_name=prospect["business_name"],
        phone=prospect.get("phone"),
        email=prospect.get("email"),
        address=prospect.get("address"),
        website=prospect.get("website"),
        google_maps_url=prospect.get("google_maps_url"),
        summary=None,
        pain_points=[],
        status=prospect["status"],
        search_query=None,
        source="url_scrape",
        created_at=prospect["created_at"]
    )


@router.post("/prospects/manual")
async def create_prospect_manually(
    org_id: str = Query(...),
    data: ProspectManualCreate = ...,
    background_tasks: BackgroundTasks = ...,
    x_telegram_init_data: str = Header(...)
) -> ProspectCard:
    """Manually create a prospect (for sites that block scraping)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, _ = verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    products = db.table("lead_agent_products").select("id").eq(
        "org_id", org_id
    ).eq("is_active", True).execute()

    if not products.data:
        raise HTTPException(
            status_code=400,
            detail="Please add at least one product or service before adding leads. The AI needs your products to generate relevant insights."
        )

    import hashlib
    website = data.website or ""
    dedup_key = f"{data.business_name.lower().strip()}:{website.lower().strip()}"
    dedup_hash = hashlib.sha256(dedup_key.encode()).hexdigest()[:32]

    existing = db.table("lead_agent_prospects").select("id").eq(
        "org_id", org_id
    ).eq("dedup_hash", dedup_hash).execute()

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="This business has already been added to your prospects."
        )

    prospect_data = {
        "org_id": org_id,
        "business_name": data.business_name,
        "phone": data.phone,
        "email": data.email,
        "address": data.address,
        "website": data.website,
        "google_maps_url": data.google_maps_url,
        "dedup_hash": dedup_hash,
        "search_query": None,
        "source": "manual",
        "status": "not_contacted",
        "created_by": user_id
    }

    result = db.table("lead_agent_prospects").insert(prospect_data).execute()
    prospect = result.data[0]

    background_tasks.add_task(
        generate_ai_insights_task,
        prospect["id"],
        org_id,
        data.description
    )

    print(f"[LeadAgent] Manually created prospect: {data.business_name}")

    cache_delete("analytics", f"la_dashboard:{org_id}")

    return ProspectCard(
        id=prospect["id"],
        business_name=prospect["business_name"],
        phone=prospect.get("phone"),
        email=prospect.get("email"),
        address=prospect.get("address"),
        website=prospect.get("website"),
        google_maps_url=prospect.get("google_maps_url"),
        summary=None,
        pain_points=[],
        status=prospect["status"],
        search_query=None,
        source="manual",
        created_at=prospect["created_at"]
    )


# NOTE: More specific routes (with sub-paths) must be defined BEFORE
# the generic /prospects/{prospect_id} route to ensure correct routing.

@router.get("/prospects/{prospect_id}/call-script")
async def get_call_script(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
):
    """Get the call script for a prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not result.data:
        raise HTTPException(404, "Prospect not found")

    prospect = result.data
    org_id = prospect["org_id"]

    verify_org_member(tg_user.id, org_id)

    call_script = prospect.get("call_script", [])

    if call_script:
        return {
            "business_name": prospect["business_name"],
            "script_items": call_script
        }

    pain_points = prospect.get("pain_points", [])
    if not pain_points:
        raise HTTPException(
            status_code=400,
            detail="No pain points available yet. Please wait for AI insights to be generated."
        )

    products_result = db.table("lead_agent_products").select("*").eq(
        "org_id", org_id
    ).eq("is_active", True).execute()

    products = [Product(**p) for p in products_result.data] if products_result.data else []

    ai = LeadAgentAI(api_key=settings.openai_api_key)

    with TaskTimer() as script_timer:
        script_items = await ai.generate_call_script(
            business_name=prospect["business_name"],
            pain_points=pain_points,
            products=products
        )

    if not script_items:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate call script. Please try again."
        )

    db.table("lead_agent_prospects").update({
        "call_script": script_items
    }).eq("id", prospect_id).execute()

    user_result = db.table("users").select("id").eq("telegram_id", tg_user.id).single().execute()
    user_id = user_result.data["id"] if user_result.data else None

    TaskLogger.log(
        org_id=org_id,
        bot_id="lead-agent",
        task_type="call_script_created",
        task_detail={"prospect_id": prospect_id, "business_name": prospect["business_name"]},
        app_id="workforce-accelerator",
        triggered_by=user_id,
        execution_time_ms=script_timer.execution_time_ms,
        tokens_used=0
    )

    return {
        "business_name": prospect["business_name"],
        "script_items": script_items
    }


@router.get("/prospects/{prospect_id}")
async def get_prospect(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> ProspectCard:
    """Get a single prospect with full details."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not result.data:
        raise HTTPException(404, "Prospect not found")

    prospect = result.data

    verify_org_member(tg_user.id, prospect["org_id"])

    pain_points = [PainPoint(**pp) for pp in prospect.get("pain_points", [])]
    call_script = prospect.get("call_script", [])

    next_follow_up = None
    notif_result = db.table("lead_agent_scheduled_notifications").select(
        "scheduled_for, message, ai_reasoning"
    ).eq("prospect_id", prospect_id).eq(
        "status", "pending"
    ).order("scheduled_for", desc=False).limit(1).execute()

    if notif_result.data:
        n = notif_result.data[0]
        next_follow_up = {
            "date": n["scheduled_for"],
            "message": n["message"],
            "reasoning": n.get("ai_reasoning", "")
        }

    return ProspectCard(
        id=prospect["id"],
        business_name=prospect["business_name"],
        phone=prospect.get("phone"),
        email=prospect.get("email"),
        address=prospect.get("address"),
        website=prospect.get("website"),
        google_maps_url=prospect.get("google_maps_url"),
        summary=prospect.get("business_summary"),
        pain_points=pain_points,
        call_script=call_script,
        ai_overview=prospect.get("ai_overview"),
        next_follow_up=next_follow_up,
        status=prospect["status"],
        search_query=prospect.get("search_query"),
        source=prospect.get("source", "gemini_search"),
        created_at=prospect["created_at"]
    )


@router.patch("/prospects/{prospect_id}/status")
async def update_prospect_status(
    prospect_id: str,
    data: ProspectStatusUpdate,
    x_telegram_init_data: str = Header(...)
) -> ProspectCard:
    """Update the status of a prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    prospect_result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect_result.data:
        raise HTTPException(404, "Prospect not found")

    verify_org_member(tg_user.id, prospect_result.data["org_id"])

    result = db.table("lead_agent_prospects").update({
        "status": data.status
    }).eq("id", prospect_id).execute()

    cache_delete("analytics", f"la_dashboard:{prospect_result.data['org_id']}")

    prospect = result.data[0]
    return ProspectCard(
        id=prospect["id"],
        business_name=prospect["business_name"],
        phone=prospect.get("phone"),
        email=prospect.get("email"),
        address=prospect.get("address"),
        website=prospect.get("website"),
        google_maps_url=prospect.get("google_maps_url"),
        summary=prospect.get("business_summary"),
        pain_points=prospect.get("pain_points") or [],
        status=prospect["status"],
        search_query=prospect.get("search_query"),
        source=prospect.get("source") or "url_scrape",
        created_at=prospect["created_at"]
    )


@router.patch("/prospects/{prospect_id}/contact")
async def update_prospect_contact(
    prospect_id: str,
    data: ProspectContactUpdate,
    x_telegram_init_data: str = Header(...)
) -> ProspectCard:
    """Update the contact information of a prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    prospect_result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect_result.data:
        raise HTTPException(404, "Prospect not found")

    verify_org_member(tg_user.id, prospect_result.data["org_id"])

    update_data = {}
    if data.phone is not None:
        update_data["phone"] = data.phone
    if data.email is not None:
        update_data["email"] = data.email

    result = db.table("lead_agent_prospects").update(update_data).eq(
        "id", prospect_id
    ).execute()

    prospect = result.data[0]
    return ProspectCard(
        id=prospect["id"],
        business_name=prospect["business_name"],
        phone=prospect.get("phone"),
        email=prospect.get("email"),
        address=prospect.get("address"),
        website=prospect.get("website"),
        google_maps_url=prospect.get("google_maps_url"),
        summary=prospect.get("business_summary"),
        pain_points=prospect.get("pain_points") or [],
        status=prospect["status"],
        search_query=prospect.get("search_query"),
        source=prospect.get("source") or "url_scrape",
        created_at=prospect["created_at"]
    )


@router.delete("/prospects/{prospect_id}")
async def delete_prospect(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    prospect_result = db.table("lead_agent_prospects").select("org_id").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect_result.data:
        raise HTTPException(404, "Prospect not found")

    verify_org_member(tg_user.id, prospect_result.data["org_id"])

    db.table("lead_agent_prospects").delete().eq("id", prospect_id).execute()

    cache_delete("analytics", f"la_dashboard:{prospect_result.data['org_id']}")

    return {"status": "deleted"}


@router.get("/prospects/{prospect_id}/vcard")
async def get_prospect_vcard(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Generate vCard data for the prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not result.data:
        raise HTTPException(404, "Prospect not found")

    prospect = result.data

    verify_org_member(tg_user.id, prospect["org_id"])

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{prospect['business_name']}",
        f"ORG:{prospect['business_name']}",
    ]

    if prospect.get("phone"):
        lines.append(f"TEL;TYPE=WORK,VOICE:{prospect['phone']}")

    if prospect.get("email"):
        lines.append(f"EMAIL;TYPE=WORK:{prospect['email']}")

    if prospect.get("address"):
        lines.append(f"ADR;TYPE=WORK:;;{prospect['address']};;;;")

    if prospect.get("website"):
        lines.append(f"URL:{prospect['website']}")

    if prospect.get("google_maps_url"):
        lines.append(f"NOTE:Google Maps: {prospect['google_maps_url']}")

    lines.append("END:VCARD")

    vcard_data = "\n".join(lines)

    return {
        "vcard": vcard_data,
        "filename": f"{prospect['business_name'].replace(' ', '_')}.vcf"
    }


# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL ENTRY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/prospects/{prospect_id}/journal")
async def list_journal_entries(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> List[JournalEntry]:
    """List all journal entries for a prospect (sorted by newest first)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    prospect = db.table("lead_agent_prospects").select("org_id").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect.data:
        raise HTTPException(404, "Prospect not found")

    verify_org_member(tg_user.id, prospect.data["org_id"])

    result = db.table("lead_agent_journal_entries").select("*").eq(
        "prospect_id", prospect_id
    ).order("created_at", desc=True).execute()

    org_id = prospect.data["org_id"]
    user_ids = list({e["user_id"] for e in result.data})
    name_map = {}
    if user_ids:
        members = db.table("memberships").select(
            "user_id, users(full_name)"
        ).eq("org_id", org_id).in_("user_id", user_ids).execute()
        name_map = {m["user_id"]: m["users"]["full_name"] for m in members.data}

    entries = []
    for e in result.data:
        entry = JournalEntry(**e)
        entry.author_name = name_map.get(e["user_id"])
        entries.append(entry)

    return entries


@router.post("/prospects/{prospect_id}/journal")
async def create_journal_entry(
    prospect_id: str,
    data: JournalEntryCreate,
    background_tasks: BackgroundTasks,
    x_telegram_init_data: str = Header(...)
) -> JournalEntry:
    """Create a new journal entry and trigger AI notification scheduling."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    prospect = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect.data:
        raise HTTPException(404, "Prospect not found")

    user_id, _ = verify_org_member(tg_user.id, prospect.data["org_id"])

    entry_data = {
        "prospect_id": prospect_id,
        "user_id": user_id,
        "content": data.content,
        "interaction_type": data.interaction_type
    }

    result = db.table("lead_agent_journal_entries").insert(entry_data).execute()
    entry = result.data[0]

    from apps.workforce_accelerator.agents.timekeeping.service import process_timekeeping_agent
    background_tasks.add_task(
        process_timekeeping_agent,
        prospect_id=prospect_id,
        user_id=user_id,
        entry_id=entry["id"]
    )

    return JournalEntry(**entry)


@router.put("/prospects/{prospect_id}/journal/{entry_id}")
async def update_journal_entry(
    prospect_id: str,
    entry_id: str,
    data: JournalEntryUpdate,
    background_tasks: BackgroundTasks,
    x_telegram_init_data: str = Header(...)
) -> JournalEntry:
    """Update a journal entry and re-trigger AI notification scheduling."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    entry_result = db.table("lead_agent_journal_entries").select("*").eq(
        "id", entry_id
    ).eq("prospect_id", prospect_id).single().execute()

    if not entry_result.data:
        raise HTTPException(404, "Journal entry not found")

    prospect = db.table("lead_agent_prospects").select("org_id").eq(
        "id", prospect_id
    ).single().execute()

    user_id, _ = verify_org_member(tg_user.id, prospect.data["org_id"])

    if entry_result.data["user_id"] != user_id:
        raise HTTPException(403, "You can only edit your own entries")

    update_data = {}
    if data.content is not None:
        update_data["content"] = data.content
    if data.interaction_type is not None:
        update_data["interaction_type"] = data.interaction_type

    if not update_data:
        return JournalEntry(**entry_result.data)

    result = db.table("lead_agent_journal_entries").update(update_data).eq(
        "id", entry_id
    ).execute()

    from apps.workforce_accelerator.agents.timekeeping.service import process_timekeeping_agent
    background_tasks.add_task(
        process_timekeeping_agent,
        prospect_id=prospect_id,
        user_id=user_id,
        entry_id=entry_id
    )

    return JournalEntry(**result.data[0])


@router.delete("/prospects/{prospect_id}/journal/{entry_id}")
async def delete_journal_entry(
    prospect_id: str,
    entry_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a journal entry."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    entry_result = db.table("lead_agent_journal_entries").select("user_id").eq(
        "id", entry_id
    ).eq("prospect_id", prospect_id).single().execute()

    if not entry_result.data:
        raise HTTPException(404, "Journal entry not found")

    prospect = db.table("lead_agent_prospects").select("org_id").eq(
        "id", prospect_id
    ).single().execute()

    user_id, _ = verify_org_member(tg_user.id, prospect.data["org_id"])

    if entry_result.data["user_id"] != user_id:
        raise HTTPException(403, "You can only delete your own entries")

    db.table("lead_agent_journal_entries").delete().eq("id", entry_id).execute()

    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD & SEARCH HISTORY
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    org_id: str = Query(...),
    x_telegram_init_data: str = Header(...)
) -> LeadAgentDashboard:
    """Get dashboard statistics."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    cache_key = f"la_dashboard:{org_id}"
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    org_result = db.table("organizations").select("settings").eq("id", org_id).single().execute()
    org_settings = org_result.data.get("settings", {}) if org_result.data else {}
    currency = get_org_currency(org_settings)

    prospects = db.table("lead_agent_prospects").select("status").eq(
        "org_id", org_id
    ).execute()

    by_status = {
        "not_contacted": 0,
        "contacted": 0,
        "ongoing_conversations": 0,
        "closed": 0
    }

    for p in prospects.data:
        status = p["status"]
        by_status[status] = by_status.get(status, 0) + 1

    products = db.table("lead_agent_products").select("id", count="exact").eq(
        "org_id", org_id
    ).eq("is_active", True).execute()

    searches_result = db.table("lead_agent_searches").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).limit(5).execute()

    recent_searches = [SearchHistory(**s) for s in searches_result.data]

    result = LeadAgentDashboard(
        total_prospects=len(prospects.data),
        by_status=by_status,
        products_count=products.count or 0,
        recent_searches=recent_searches,
        currency=currency
    )
    cache_set("analytics", cache_key, result)
    return result


@router.get("/searches")
async def get_searches(
    org_id: str = Query(...),
    limit: int = Query(20, le=100),
    x_telegram_init_data: str = Header(...)
) -> List[SearchHistory]:
    """List past searches."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    result = db.table("lead_agent_searches").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).limit(limit).execute()

    return [SearchHistory(**s) for s in result.data]

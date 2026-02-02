"""
Lead Agent Bot API - B2B Lead generation and management endpoints.

Handles:
- Product/service management
- Prospect search and discovery (via Gemini)
- AI-powered insights generation (via OpenAI)
- Prospect status management
- vCard generation for contacts
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks, Query

from models import (
    TelegramUser,
    ProductCreate, ProductUpdate, Product,
    ProspectCreate, ProspectStatusUpdate, Prospect, ProspectCard,
    PainPoint, SearchRequest, SearchResult, SearchHistory,
    LeadAgentDashboard, CurrencyUpdate
)
from services import get_supabase_admin, get_telegram_user
from services.lead_discovery import LeadDiscoveryService, ScrapedBusiness
from services.ai_lead_agent import LeadAgentAI
from config import settings

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(x_telegram_init_data: str = Header(...)) -> TelegramUser:
    """Extract and verify Telegram user from initData header."""
    return get_telegram_user(x_telegram_init_data)


async def verify_org_member(user_telegram_id: int, org_id: str) -> tuple[str, str]:
    """
    Verify user is a member of the organization.
    Returns (user_id, role).
    """
    db = get_supabase_admin()

    # Get user
    user_result = db.table("users").select("id").eq(
        "telegram_id", user_telegram_id
    ).execute()

    if not user_result.data:
        raise HTTPException(404, "User not found")

    user_id = user_result.data[0]["id"]

    # Check membership
    membership = db.table("memberships").select("role").eq(
        "user_id", user_id
    ).eq("org_id", org_id).execute()

    if not membership.data:
        raise HTTPException(403, "Not a member of this organization")

    return user_id, membership.data[0]["role"]


async def verify_org_admin(user_telegram_id: int, org_id: str) -> str:
    """
    Verify user is an admin of the organization.
    Returns user_id.
    """
    user_id, role = await verify_org_member(user_telegram_id, org_id)
    if role != "admin":
        raise HTTPException(403, "Admin access required")
    return user_id


def get_org_currency(org_settings: dict) -> str:
    """Get organization's lead agent currency from settings."""
    return org_settings.get("lead_agent_currency", "USD")


async def generate_ai_insights_task(prospect_id: str, org_id: str):
    """Background task to generate AI insights for a prospect."""
    db = get_supabase_admin()

    try:
        # Get prospect
        prospect_result = db.table("lead_agent_prospects").select("*").eq(
            "id", prospect_id
        ).single().execute()

        if not prospect_result.data:
            return

        prospect_data = prospect_result.data

        # Get org's products
        products_result = db.table("lead_agent_products").select("*").eq(
            "org_id", org_id
        ).eq("is_active", True).execute()

        products = [Product(**p) for p in products_result.data]

        # Generate insights
        ai = LeadAgentAI(settings.openai_api_key)
        summary, pain_points = await ai.generate_prospect_insights(
            business_name=prospect_data["business_name"],
            business_address=prospect_data.get("address"),
            business_website=prospect_data.get("website"),
            products=products
        )

        # Update prospect with AI-generated content
        db.table("lead_agent_prospects").update({
            "business_summary": summary,
            "pain_points": [pp.dict() for pp in pain_points],
            "ai_generated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", prospect_id).execute()

    except Exception as e:
        print(f"Error generating AI insights for prospect {prospect_id}: {e}")


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
    await verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()
    result = db.table("lead_agent_products").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).execute()

    return [Product(**p) for p in result.data]


@router.post("/products")
async def create_product(
    org_id: str = Query(...),
    data: ProductCreate = ...,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Create a new product (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    await verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()
    product_data = {
        "org_id": org_id,
        "name": data.name,
        "description": data.description,
        "price": str(data.price) if data.price else None,
        "is_active": True
    }

    result = db.table("lead_agent_products").insert(product_data).execute()
    return Product(**result.data[0])


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    data: ProductUpdate,
    x_telegram_init_data: str = Header(...)
) -> Product:
    """Update a product (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get product to verify org ownership
    product_result = db.table("lead_agent_products").select("org_id").eq(
        "id", product_id
    ).single().execute()

    if not product_result.data:
        raise HTTPException(404, "Product not found")

    await verify_org_admin(tg_user.id, product_result.data["org_id"])

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

    result = db.table("lead_agent_products").update(update_data).eq(
        "id", product_id
    ).execute()

    return Product(**result.data[0])


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a product (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get product to verify org ownership
    product_result = db.table("lead_agent_products").select("org_id").eq(
        "id", product_id
    ).single().execute()

    if not product_result.data:
        raise HTTPException(404, "Product not found")

    await verify_org_admin(tg_user.id, product_result.data["org_id"])

    db.table("lead_agent_products").delete().eq("id", product_id).execute()

    return {"status": "deleted"}


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
    await verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    # Build query
    query = db.table("lead_agent_prospects").select("*").eq("org_id", org_id)

    if status:
        query = query.eq("status", status)
    if search_query:
        query = query.eq("search_query", search_query)

    result = query.order("created_at", desc=True).limit(limit).offset(offset).execute()

    # Convert to ProspectCard
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
            search_query=p["search_query"],
            created_at=p["created_at"]
        ))

    return cards


@router.post("/prospects/search")
async def search_prospects(
    org_id: str = Query(...),
    data: SearchRequest = ...,
    background_tasks: BackgroundTasks = ...,
    x_telegram_init_data: str = Header(...)
) -> SearchResult:
    """
    Search for new prospects using Gemini.
    Deduplicates against existing prospects and queues AI generation.
    """
    tg_user = get_telegram_user(x_telegram_init_data)
    user_id, _ = await verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    # Initialize lead discovery service
    discovery = LeadDiscoveryService(settings.gemini_api_key)

    # Search for businesses
    businesses = await discovery.search_businesses(data.query, max_results=10)

    new_prospects = []
    skipped_duplicates = 0

    for business in businesses:
        dedup_hash = business.get_dedup_hash()

        # Check if prospect already exists
        existing = db.table("lead_agent_prospects").select("id").eq(
            "org_id", org_id
        ).eq("dedup_hash", dedup_hash).execute()

        if existing.data:
            skipped_duplicates += 1
            continue

        # Insert new prospect
        prospect_data = {
            "org_id": org_id,
            "business_name": business.business_name,
            "phone": business.phone,
            "email": business.email,
            "address": business.address,
            "website": business.website,
            "google_maps_url": business.google_maps_url,
            "dedup_hash": dedup_hash,
            "search_query": data.query,
            "source": "gemini_search",
            "status": "not_contacted",
            "created_by": user_id
        }

        result = db.table("lead_agent_prospects").insert(prospect_data).execute()
        prospect = result.data[0]

        # Queue AI insights generation
        background_tasks.add_task(generate_ai_insights_task, prospect["id"], org_id)

        # Add to new prospects list
        new_prospects.append(ProspectCard(
            id=prospect["id"],
            business_name=prospect["business_name"],
            phone=prospect.get("phone"),
            email=prospect.get("email"),
            address=prospect.get("address"),
            website=prospect.get("website"),
            google_maps_url=prospect.get("google_maps_url"),
            summary=None,  # AI generation pending
            pain_points=[],  # AI generation pending
            status=prospect["status"],
            search_query=prospect["search_query"],
            created_at=prospect["created_at"]
        ))

    # Record search history
    search_data = {
        "org_id": org_id,
        "user_id": user_id,
        "query": data.query,
        "results_count": len(businesses),
        "new_prospects_count": len(new_prospects),
        "skipped_duplicates_count": skipped_duplicates
    }
    search_result = db.table("lead_agent_searches").insert(search_data).execute()
    search_id = search_result.data[0]["id"]

    return SearchResult(
        search_id=search_id,
        query=data.query,
        total_found=len(businesses),
        new_prospects=len(new_prospects),
        skipped_duplicates=skipped_duplicates,
        prospects=new_prospects
    )


@router.get("/prospects/{prospect_id}")
async def get_prospect(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> ProspectCard:
    """Get a single prospect with full details."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get prospect
    result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not result.data:
        raise HTTPException(404, "Prospect not found")

    prospect = result.data

    # Verify org membership
    await verify_org_member(tg_user.id, prospect["org_id"])

    # Convert to ProspectCard
    pain_points = [PainPoint(**pp) for pp in prospect.get("pain_points", [])]

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
        status=prospect["status"],
        search_query=prospect["search_query"],
        created_at=prospect["created_at"]
    )


@router.patch("/prospects/{prospect_id}/status")
async def update_prospect_status(
    prospect_id: str,
    data: ProspectStatusUpdate,
    x_telegram_init_data: str = Header(...)
) -> Prospect:
    """Update the status of a prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get prospect
    prospect_result = db.table("lead_agent_prospects").select("org_id").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect_result.data:
        raise HTTPException(404, "Prospect not found")

    # Verify org membership
    await verify_org_member(tg_user.id, prospect_result.data["org_id"])

    # Update status
    result = db.table("lead_agent_prospects").update({
        "status": data.status
    }).eq("id", prospect_id).execute()

    return Prospect(**result.data[0])


@router.delete("/prospects/{prospect_id}")
async def delete_prospect(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Delete a prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get prospect
    prospect_result = db.table("lead_agent_prospects").select("org_id").eq(
        "id", prospect_id
    ).single().execute()

    if not prospect_result.data:
        raise HTTPException(404, "Prospect not found")

    # Verify org membership
    await verify_org_member(tg_user.id, prospect_result.data["org_id"])

    # Delete prospect
    db.table("lead_agent_prospects").delete().eq("id", prospect_id).execute()

    return {"status": "deleted"}


@router.get("/prospects/{prospect_id}/vcard")
async def get_prospect_vcard(
    prospect_id: str,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Generate vCard data for the prospect."""
    tg_user = get_telegram_user(x_telegram_init_data)
    db = get_supabase_admin()

    # Get prospect
    result = db.table("lead_agent_prospects").select("*").eq(
        "id", prospect_id
    ).single().execute()

    if not result.data:
        raise HTTPException(404, "Prospect not found")

    prospect = result.data

    # Verify org membership
    await verify_org_member(tg_user.id, prospect["org_id"])

    # Generate vCard
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
# DASHBOARD & SEARCH HISTORY
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    org_id: str = Query(...),
    x_telegram_init_data: str = Header(...)
) -> LeadAgentDashboard:
    """Get dashboard statistics."""
    tg_user = get_telegram_user(x_telegram_init_data)
    await verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    # Get org settings for currency
    org_result = db.table("organizations").select("settings").eq("id", org_id).single().execute()
    org_settings = org_result.data.get("settings", {}) if org_result.data else {}
    currency = get_org_currency(org_settings)

    # Count prospects by status
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

    # Count products
    products = db.table("lead_agent_products").select("id", count="exact").eq(
        "org_id", org_id
    ).eq("is_active", True).execute()

    # Get recent searches
    searches_result = db.table("lead_agent_searches").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).limit(5).execute()

    recent_searches = [SearchHistory(**s) for s in searches_result.data]

    return LeadAgentDashboard(
        total_prospects=len(prospects.data),
        by_status=by_status,
        products_count=products.count or 0,
        recent_searches=recent_searches,
        currency=currency
    )


@router.get("/searches")
async def get_searches(
    org_id: str = Query(...),
    limit: int = Query(20, le=100),
    x_telegram_init_data: str = Header(...)
) -> List[SearchHistory]:
    """List past searches."""
    tg_user = get_telegram_user(x_telegram_init_data)
    await verify_org_member(tg_user.id, org_id)

    db = get_supabase_admin()

    result = db.table("lead_agent_searches").select("*").eq(
        "org_id", org_id
    ).order("created_at", desc=True).limit(limit).execute()

    return [SearchHistory(**s) for s in result.data]


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
    await verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    # Get current settings
    org_result = db.table("organizations").select("settings").eq(
        "id", org_id
    ).single().execute()

    settings_dict = org_result.data.get("settings", {}) if org_result.data else {}
    settings_dict["lead_agent_currency"] = data.currency.upper()

    # Update settings
    db.table("organizations").update({
        "settings": settings_dict
    }).eq("id", org_id).execute()

    return {"currency": data.currency.upper(), "status": "updated"}

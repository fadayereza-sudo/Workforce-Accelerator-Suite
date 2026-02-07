"""
Core Hub — Billing routes.

Routes:
- /plans — List subscription plans (public)
- /orgs/{org_id}/billing — Billing overview (admin only)
"""
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Header, HTTPException

from core.auth import get_telegram_user, verify_org_admin
from core.database import get_supabase_admin
from core.cache import cache_get, cache_set
from core.models.billing import (
    SubscriptionPlan, OrgSubscription, Invoice, BillingOverview
)

router = APIRouter()


@router.get("/plans")
async def list_subscription_plans() -> List[SubscriptionPlan]:
    """List available subscription plans (public)."""
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
    verify_org_admin(tg_user.id, org_id)

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

"""
Report Agent API — Activity monitoring and LLM-generated report endpoints.

Handles:
- Retrieving stored activity reports
- On-demand report generation
- Bot task log queries
"""
from datetime import timedelta
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, BackgroundTasks

from core.models.reports import (
    ActivityReport, ReportListItem, ReportsList,
    GenerateReportRequest, ReportSummaryResponse,
    BotTaskLogEntry
)
from core.auth import get_telegram_user, verify_org_admin
from core.database import get_supabase_admin
from core.cache import cache_get, cache_set, cache_delete
from apps.workforce_accelerator.agents.report_agent.tasks import (
    generate_team_report, generate_agent_report
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# REPORT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/reports")
async def list_reports(
    org_id: str,
    report_type: Optional[str] = Query(None),
    period_type: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    x_telegram_init_data: str = Header(...)
) -> ReportsList:
    """List activity reports for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    query = db.table("activity_reports").select(
        "id, report_type, period_type, period_start, period_end, bot_id, created_at, bot_registry(name)",
        count="exact"
    ).eq("org_id", org_id)

    if report_type:
        query = query.eq("report_type", report_type)
    if period_type:
        query = query.eq("period_type", period_type)
    if bot_id:
        query = query.eq("bot_id", bot_id)

    result = query.order("period_start", desc=True).range(offset, offset + limit - 1).execute()

    reports = []
    for r in result.data:
        reports.append(ReportListItem(
            id=r["id"],
            report_type=r["report_type"],
            period_type=r["period_type"],
            period_start=r["period_start"],
            period_end=r["period_end"],
            bot_id=r.get("bot_id"),
            bot_name=r["bot_registry"]["name"] if r.get("bot_registry") else None,
            created_at=r["created_at"]
        ))

    return ReportsList(reports=reports, total=result.count or 0)


@router.get("/orgs/{org_id}/reports/latest")
async def get_latest_reports(
    org_id: str,
    period_type: str = Query("weekly"),
    x_telegram_init_data: str = Header(...)
) -> ReportSummaryResponse:
    """Get the latest team and agent reports for dashboard display (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    cache_key = f"latest_reports:{org_id}:{period_type}"
    cached = cache_get("reports", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()

    team_result = db.table("activity_reports").select("*").eq(
        "org_id", org_id
    ).eq("report_type", "team").eq(
        "period_type", period_type
    ).is_("user_id", "null").order(
        "period_start", desc=True
    ).limit(1).execute()

    team_report = None
    if team_result.data:
        team_report = ActivityReport(**team_result.data[0])

    agent_result = db.table("activity_reports").select("*").eq(
        "org_id", org_id
    ).eq("report_type", "agent").eq(
        "period_type", period_type
    ).order("period_start", desc=True).execute()

    seen_bots = set()
    agent_reports = []
    for r in agent_result.data:
        if r["bot_id"] not in seen_bots:
            agent_reports.append(ActivityReport(**r))
            seen_bots.add(r["bot_id"])

    result = ReportSummaryResponse(
        team_report=team_report,
        agent_reports=agent_reports,
        has_data=team_report is not None or len(agent_reports) > 0
    )
    cache_set("reports", cache_key, result)
    return result


@router.get("/orgs/{org_id}/reports/{report_id}")
async def get_report(
    org_id: str,
    report_id: str,
    x_telegram_init_data: str = Header(...)
) -> ActivityReport:
    """Get a specific activity report (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    result = db.table("activity_reports").select("*").eq(
        "id", report_id
    ).eq("org_id", org_id).single().execute()

    if not result.data:
        raise HTTPException(404, "Report not found")

    return ActivityReport(**result.data)


@router.post("/orgs/{org_id}/reports/generate")
async def generate_report_on_demand(
    org_id: str,
    data: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    x_telegram_init_data: str = Header(...)
) -> dict:
    """Generate a report on-demand (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    org = db.table("organizations").select("name").eq("id", org_id).single().execute()
    if not org.data:
        raise HTTPException(404, "Organization not found")

    org_name = org.data["name"]

    if data.period_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "Invalid period_type. Must be 'daily', 'weekly', or 'monthly'")

    if data.period_type == "daily":
        period_end = data.period_start
    elif data.period_type == "weekly":
        period_end = data.period_start + timedelta(days=6)
    elif data.period_type == "monthly":
        next_month = data.period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1) - timedelta(days=1)
    else:
        raise HTTPException(400, "Invalid period_type")

    if data.report_type == "team":
        background_tasks.add_task(
            generate_team_report,
            org_id, org_name, data.period_type, data.period_start, period_end
        )
    elif data.report_type == "agent":
        if not data.bot_id:
            raise HTTPException(400, "bot_id required for agent reports")

        bot = db.table("bot_registry").select("name").eq("id", data.bot_id).single().execute()
        if not bot.data:
            raise HTTPException(404, "Bot not found")

        background_tasks.add_task(
            generate_agent_report,
            org_id, org_name, data.bot_id, bot.data["name"],
            data.period_type, data.period_start, period_end
        )
    else:
        raise HTTPException(400, "Invalid report_type. Must be 'team' or 'agent'")

    cache_delete("reports", f"latest_reports:{org_id}:{data.period_type}")

    return {
        "status": "generating",
        "message": f"Report generation started for {data.period_type} {data.report_type} report"
    }


# ─────────────────────────────────────────────────────────────────────────────
# BOT TASK LOG ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/bot-tasks")
async def list_bot_tasks(
    org_id: str,
    bot_id: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    x_telegram_init_data: str = Header(...)
) -> List[BotTaskLogEntry]:
    """List bot task logs for an organization (admin only)."""
    tg_user = get_telegram_user(x_telegram_init_data)
    verify_org_admin(tg_user.id, org_id)

    db = get_supabase_admin()

    query = db.table("bot_task_log").select("*").eq("org_id", org_id)

    if bot_id:
        query = query.eq("bot_id", bot_id)
    if task_type:
        query = query.eq("task_type", task_type)

    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return [BotTaskLogEntry(**t) for t in result.data]

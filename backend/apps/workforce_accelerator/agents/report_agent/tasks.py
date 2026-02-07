"""
Report Agent — scheduled tasks (periodic report generation).
"""
import time
from datetime import datetime, timezone, timedelta, date

from core.database import get_supabase_admin
from config import settings
from apps.workforce_accelerator.agents.report_agent.service import (
    ReportGenerator, TeamReportMetrics, AgentReportMetrics
)


async def process_due_reports():
    """Check and generate any due reports for all organizations."""
    db = get_supabase_admin()
    now = datetime.now(timezone.utc)
    today = now.date()

    orgs = db.table("organizations").select("id, name").execute()

    for org in orgs.data:
        org_id = org["id"]
        org_name = org["name"]

        if now.hour >= 6:
            yesterday = today - timedelta(days=1)
            await generate_report_if_needed(org_id, org_name, "daily", yesterday)

        if now.weekday() == 0 and now.hour >= 6:
            last_week_start = today - timedelta(days=7)
            await generate_report_if_needed(org_id, org_name, "weekly", last_week_start)

        if today.day == 1 and now.hour >= 6:
            last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            await generate_report_if_needed(org_id, org_name, "monthly", last_month_start)


async def generate_report_if_needed(
    org_id: str,
    org_name: str,
    period_type: str,
    period_start: date
):
    """Generate reports if they don't already exist."""
    db = get_supabase_admin()

    if period_type == "daily":
        period_end = period_start
    elif period_type == "weekly":
        period_end = period_start + timedelta(days=6)
    elif period_type == "monthly":
        next_month = period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1) - timedelta(days=1)
    else:
        return

    existing = db.table("activity_reports").select("id").eq(
        "org_id", org_id
    ).eq("report_type", "team").eq(
        "period_type", period_type
    ).eq("period_start", period_start.isoformat()).is_("user_id", "null").execute()

    if not existing.data:
        await generate_team_report(org_id, org_name, period_type, period_start, period_end)

    bots = db.table("bot_registry").select("id, name").eq("is_active", True).execute()

    for bot in bots.data:
        existing_bot = db.table("activity_reports").select("id").eq(
            "org_id", org_id
        ).eq("report_type", "agent").eq(
            "period_type", period_type
        ).eq("period_start", period_start.isoformat()).eq(
            "bot_id", bot["id"]
        ).execute()

        if not existing_bot.data:
            await generate_agent_report(
                org_id, org_name, bot["id"], bot["name"],
                period_type, period_start, period_end
            )


async def generate_team_report(
    org_id: str,
    org_name: str,
    period_type: str,
    period_start: date,
    period_end: date
):
    """Generate and store a team activity report."""
    db = get_supabase_admin()
    generator = ReportGenerator(settings.openai_api_key)

    start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    members = db.table("memberships").select("id, user_id, users(full_name)").eq(
        "org_id", org_id
    ).execute()

    activities = db.table("member_activity_log").select("*").eq(
        "org_id", org_id
    ).gte("created_at", start_dt.isoformat()).lte(
        "created_at", end_dt.isoformat()
    ).execute()

    activities_by_type = {}
    activities_by_user = {}
    bots_by_user = {}

    for a in activities.data:
        atype = a["action_type"]
        activities_by_type[atype] = activities_by_type.get(atype, 0) + 1

        uid = a["user_id"]
        activities_by_user[uid] = activities_by_user.get(uid, 0) + 1

        if a["bot_id"]:
            if uid not in bots_by_user:
                bots_by_user[uid] = set()
            bots_by_user[uid].add(a["bot_id"])

    user_name_map = {m["user_id"]: m["users"]["full_name"] for m in members.data if m.get("users")}
    top_performers = []
    for uid, count in activities_by_user.items():
        top_performers.append({
            "name": user_name_map.get(uid, "Unknown"),
            "activity_count": count,
            "bots_used": list(bots_by_user.get(uid, []))
        })

    top_performers.sort(key=lambda x: x["activity_count"], reverse=True)

    bots_accessed = {}
    for uid, bots in bots_by_user.items():
        for bot in bots:
            bots_accessed[bot] = bots_accessed.get(bot, 0) + 1

    metrics = TeamReportMetrics(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        total_members=len(members.data),
        active_members=len(activities_by_user),
        total_activities=len(activities.data),
        activities_by_type=activities_by_type,
        top_performers=top_performers[:5],
        bots_accessed=bots_accessed
    )

    if metrics.total_activities == 0:
        print(f"[ReportScheduler] No team activity for {org_name} ({period_type}: {period_start}), skipping")
        return

    try:
        start_time = time.perf_counter()
        result = await generator.generate_team_report(metrics, org_name)
        generation_time = int((time.perf_counter() - start_time) * 1000)

        report_data = {
            "org_id": org_id,
            "report_type": "team",
            "period_type": period_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "raw_metrics": {
                "total_members": metrics.total_members,
                "active_members": metrics.active_members,
                "total_activities": metrics.total_activities,
                "activities_by_type": metrics.activities_by_type,
                "top_performers": metrics.top_performers,
                "bots_accessed": metrics.bots_accessed
            },
            "summary_text": result["summary_text"],
            "highlights": result.get("highlights", []),
            "recommendations": result.get("recommendations", []),
            "tokens_used": result.get("tokens_used"),
            "generation_time_ms": generation_time
        }

        db.table("activity_reports").insert(report_data).execute()
        print(f"[ReportScheduler] Generated team report for {org_name} ({period_type}: {period_start})")

    except Exception as e:
        print(f"[ReportScheduler] Error generating team report for {org_id}: {e}")


async def generate_agent_report(
    org_id: str,
    org_name: str,
    bot_id: str,
    bot_name: str,
    period_type: str,
    period_start: date,
    period_end: date
):
    """Generate and store an agent activity report."""
    db = get_supabase_admin()
    generator = ReportGenerator(settings.openai_api_key)

    start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    tasks = db.table("bot_task_log").select("*").eq(
        "org_id", org_id
    ).eq("bot_id", bot_id).gte(
        "created_at", start_dt.isoformat()
    ).lte("created_at", end_dt.isoformat()).execute()

    if not tasks.data:
        print(f"[ReportScheduler] No tasks for {bot_name} in {org_name} ({period_type}: {period_start}), skipping")
        return

    tasks_by_type = {}
    unique_users = set()
    total_exec_time = 0
    total_tokens = 0
    highlights = []

    for t in tasks.data:
        ttype = t["task_type"]
        tasks_by_type[ttype] = tasks_by_type.get(ttype, 0) + 1

        if t.get("triggered_by"):
            unique_users.add(t["triggered_by"])

        if t.get("execution_time_ms"):
            total_exec_time += t["execution_time_ms"]

        if t.get("tokens_used"):
            total_tokens += t["tokens_used"]

        detail = t.get("task_detail", {})
        if detail.get("business_name") and ttype == "insights_generated":
            highlights.append({
                "type": "insight",
                "description": f"Generated AI insights for {detail['business_name']}"
            })

    metrics = AgentReportMetrics(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        bot_id=bot_id,
        bot_name=bot_name,
        total_tasks=len(tasks.data),
        tasks_by_type=tasks_by_type,
        unique_users=len(unique_users),
        total_execution_time_ms=total_exec_time,
        total_tokens_used=total_tokens,
        highlights=highlights[:10]
    )

    try:
        start_time = time.perf_counter()
        result = await generator.generate_agent_report(metrics, org_name)
        generation_time = int((time.perf_counter() - start_time) * 1000)

        report_data = {
            "org_id": org_id,
            "report_type": "agent",
            "period_type": period_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "bot_id": bot_id,
            "raw_metrics": {
                "bot_name": metrics.bot_name,
                "total_tasks": metrics.total_tasks,
                "tasks_by_type": metrics.tasks_by_type,
                "unique_users": metrics.unique_users,
                "total_execution_time_ms": metrics.total_execution_time_ms,
                "total_tokens_used": metrics.total_tokens_used
            },
            "summary_text": result["summary_text"],
            "highlights": result.get("highlights", []),
            "tokens_used": result.get("tokens_used"),
            "generation_time_ms": generation_time
        }

        db.table("activity_reports").insert(report_data).execute()
        print(f"[ReportScheduler] Generated agent report for {bot_name} in {org_name} ({period_type}: {period_start})")

    except Exception as e:
        print(f"[ReportScheduler] Error generating agent report for {bot_id} in {org_id}: {e}")

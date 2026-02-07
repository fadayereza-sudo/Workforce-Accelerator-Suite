"""
Lead Agent — scheduled tasks (notification delivery).
"""
from datetime import datetime, timezone

from core.database import get_supabase_admin
from core.notifications import send_journal_reminder


async def has_pending_notifications() -> bool:
    """Condition check: are there any due notifications to send?"""
    db = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    result = db.table("lead_agent_scheduled_notifications").select(
        "id", count="exact"
    ).eq("status", "pending").lte("scheduled_for", now).limit(1).execute()

    return (result.count or 0) > 0


async def process_due_notifications():
    """Process all notifications that are due to be sent."""
    db = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    result = db.table("lead_agent_scheduled_notifications").select(
        "id, message, user_id, prospect_id"
    ).eq("status", "pending").lte("scheduled_for", now).limit(50).execute()

    if not result.data:
        return

    print(f"[NotificationScheduler] Processing {len(result.data)} due notifications")

    for notification in result.data:
        try:
            user_result = db.table("users").select("telegram_id").eq(
                "id", notification["user_id"]
            ).single().execute()

            if not user_result.data:
                print(f"[NotificationScheduler] User {notification['user_id']} not found")
                continue

            prospect_result = db.table("lead_agent_prospects").select(
                "business_name"
            ).eq("id", notification["prospect_id"]).single().execute()

            business_name = prospect_result.data["business_name"] if prospect_result.data else "Unknown"

            success = await send_journal_reminder(
                user_telegram_id=user_result.data["telegram_id"],
                business_name=business_name,
                message=notification["message"]
            )

            db.table("lead_agent_scheduled_notifications").update({
                "status": "sent" if success else "pending",
                "sent_at": datetime.now(timezone.utc).isoformat() if success else None
            }).eq("id", notification["id"]).execute()

            if success:
                print(f"[NotificationScheduler] Sent notification {notification['id']}")
            else:
                print(f"[NotificationScheduler] Failed to send notification {notification['id']}")

        except Exception as e:
            print(f"[NotificationScheduler] Error processing notification {notification['id']}: {e}")

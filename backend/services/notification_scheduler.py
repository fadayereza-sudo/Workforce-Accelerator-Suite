"""
Notification Scheduler - Background polling loop for sending due notifications.

Runs as a background task in FastAPI, checking for and sending due notifications
from the lead_agent_scheduled_notifications table.
"""
import asyncio
from datetime import datetime, timezone

from services import get_supabase_admin
from services.notifications import send_journal_reminder


async def notification_scheduler_loop(poll_interval_seconds: int = 60):
    """
    Background loop that checks for and sends due notifications.

    Args:
        poll_interval_seconds: How often to check for due notifications (default: 60s)
    """
    print(f"[NotificationScheduler] Starting with poll interval: {poll_interval_seconds}s")

    while True:
        try:
            await process_due_notifications()
        except Exception as e:
            print(f"[NotificationScheduler] Error in loop: {e}")

        await asyncio.sleep(poll_interval_seconds)


async def process_due_notifications():
    """Process all notifications that are due to be sent."""
    db = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    # Get all pending notifications that are due
    result = db.table("lead_agent_scheduled_notifications").select(
        "id, message, user_id, prospect_id"
    ).eq("status", "pending").lte("scheduled_for", now).limit(50).execute()

    if not result.data:
        return

    print(f"[NotificationScheduler] Processing {len(result.data)} due notifications")

    for notification in result.data:
        try:
            # Get user's telegram_id
            user_result = db.table("users").select("telegram_id").eq(
                "id", notification["user_id"]
            ).single().execute()

            if not user_result.data:
                print(f"[NotificationScheduler] User {notification['user_id']} not found")
                continue

            # Get prospect name for the notification
            prospect_result = db.table("lead_agent_prospects").select(
                "business_name"
            ).eq("id", notification["prospect_id"]).single().execute()

            business_name = prospect_result.data["business_name"] if prospect_result.data else "Unknown"

            # Send the notification
            success = await send_journal_reminder(
                user_telegram_id=user_result.data["telegram_id"],
                business_name=business_name,
                message=notification["message"]
            )

            # Update notification status
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

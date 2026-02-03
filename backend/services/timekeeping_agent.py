"""
Timekeeping Agent - AI-powered notification scheduling for prospect follow-ups.

Uses GPT-4o-mini to analyze journal entries and determine optimal follow-up times.
The agent schedules notifications that are sent via Telegram to remind users to
follow up with their prospects at the right time.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from openai import AsyncOpenAI

from services import get_supabase_admin
from config import settings


class TimekeepingAgent:
    """AI agent that schedules follow-up notifications based on journal entries."""

    def __init__(self, api_key: str):
        """Initialize with OpenAI API key."""
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_and_schedule(
        self,
        prospect_name: str,
        journal_entries: list[dict],
    ) -> Optional[dict]:
        """
        Analyze all journal entries and determine notification schedule.

        Args:
            prospect_name: Name of the business prospect
            journal_entries: List of all journal entries (chronological order)

        Returns:
            dict with keys: should_notify, scheduled_for, message, reasoning
            None if analysis fails
        """
        # Format entries for the prompt
        entries_text = "\n".join([
            f"[{e['created_at'][:10]}] ({e['interaction_type'].upper()}) {e['content']}"
            for e in journal_entries
        ])

        current_time = datetime.now(timezone.utc)

        prompt = f"""You are a B2B sales assistant helping a salesperson manage their follow-ups with prospects.

PROSPECT: {prospect_name}

INTERACTION HISTORY (oldest to newest):
{entries_text}

CURRENT DATE/TIME: {current_time.strftime('%Y-%m-%d %H:%M')} UTC

YOUR TASK:
Analyze the interaction history and determine:
1. Is this prospect worth following up with? (interested vs not interested)
2. When should the salesperson be reminded to follow up?
3. What should the reminder message say?

SCHEDULING GUIDELINES:
- If they said "not interested" or rejected: Schedule reminder for 6-12 months from now (people change)
- If awaiting response after sending info: Schedule reminder for 5-7 days
- If had positive call/meeting: Schedule reminder for 2-3 days
- If ongoing negotiation: Schedule reminder for 1-2 days
- If very interested/hot lead: Schedule reminder for same day or next day
- If no clear signal: Default to 1 week

NOTIFICATION MESSAGE GUIDELINES:
- Keep it short and actionable (max 2 sentences)
- Reference the last interaction naturally
- Sound like a helpful assistant, not a robot
- Example: "Time to follow up with Acme Corp - you sent them pricing details 5 days ago."

Respond ONLY with valid JSON:
{{
    "should_notify": true,
    "days_from_now": 7,
    "message": "notification message here",
    "reasoning": "brief explanation of your decision"
}}

If should_notify is false, set days_from_now to 0 and message to empty string."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales assistant that helps schedule follow-up reminders. You analyze interaction history and provide smart scheduling recommendations. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=300
            )

            result = json.loads(response.choices[0].message.content)

            # Calculate actual scheduled time
            days = min(max(result.get("days_from_now", 7), 0), 365)
            scheduled_for = current_time + timedelta(days=days)

            return {
                "should_notify": result.get("should_notify", True),
                "scheduled_for": scheduled_for.isoformat(),
                "message": result.get("message", ""),
                "reasoning": result.get("reasoning", "")
            }

        except Exception as e:
            print(f"[TimekeepingAgent] Error analyzing entries: {e}")
            return None


async def process_timekeeping_agent(
    prospect_id: str,
    user_id: str,
    entry_id: str
):
    """
    Background task to process journal entry and schedule notification.

    Called when a journal entry is created or updated.
    """
    db = get_supabase_admin()

    try:
        # Get prospect info
        prospect_result = db.table("lead_agent_prospects").select(
            "business_name"
        ).eq("id", prospect_id).single().execute()

        if not prospect_result.data:
            print(f"[TimekeepingAgent] Prospect {prospect_id} not found")
            return

        prospect_name = prospect_result.data["business_name"]

        # Get all journal entries for this prospect by this user (oldest first)
        entries_result = db.table("lead_agent_journal_entries").select("*").eq(
            "prospect_id", prospect_id
        ).eq("user_id", user_id).order("created_at", desc=False).execute()

        if not entries_result.data:
            print(f"[TimekeepingAgent] No entries found for prospect {prospect_id}")
            return

        # Run AI analysis
        agent = TimekeepingAgent(settings.openai_api_key)
        result = await agent.analyze_and_schedule(
            prospect_name=prospect_name,
            journal_entries=entries_result.data,
        )

        if not result:
            print(f"[TimekeepingAgent] AI analysis failed for prospect {prospect_id}")
            return

        # Cancel existing pending notification for this user/prospect
        db.table("lead_agent_scheduled_notifications").update({
            "status": "cancelled"
        }).eq("prospect_id", prospect_id).eq(
            "user_id", user_id
        ).eq("status", "pending").execute()

        # Create new notification if AI recommends it
        if result["should_notify"] and result["message"]:
            notification_data = {
                "prospect_id": prospect_id,
                "user_id": user_id,
                "message": result["message"],
                "scheduled_for": result["scheduled_for"],
                "status": "pending",
                "ai_reasoning": result["reasoning"],
                "triggered_by_entry_id": entry_id
            }

            db.table("lead_agent_scheduled_notifications").insert(
                notification_data
            ).execute()

            print(f"[TimekeepingAgent] Scheduled notification for {prospect_name} at {result['scheduled_for']}")
        else:
            print(f"[TimekeepingAgent] No notification needed for {prospect_name}")

    except Exception as e:
        print(f"[TimekeepingAgent] Error processing entry {entry_id}: {e}")

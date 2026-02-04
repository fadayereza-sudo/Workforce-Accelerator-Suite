"""
Bot Task Logger - Centralized logging for AI agent activities.

Provides helper functions to log bot tasks with consistent structure.
Call these from bot endpoints/background tasks when agents complete work.
"""
import time
from typing import Optional, Dict, Any

from services import get_supabase_admin


class BotTaskLogger:
    """Log AI agent tasks to bot_task_log table."""

    @staticmethod
    def log_task(
        org_id: str,
        bot_id: str,
        task_type: str,
        task_detail: Dict[str, Any] = None,
        triggered_by: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None
    ) -> str:
        """
        Log a bot task to the database.

        Args:
            org_id: Organization UUID
            bot_id: Bot ID from bot_registry (e.g., 'lead-agent')
            task_type: Type of task (e.g., 'prospect_scraped', 'insights_generated')
            task_detail: Optional dict with task-specific data
            triggered_by: Optional user UUID who triggered this task
            execution_time_ms: Optional execution time in milliseconds
            tokens_used: Optional LLM tokens consumed

        Returns:
            The created task log ID
        """
        db = get_supabase_admin()

        log_data = {
            "org_id": org_id,
            "bot_id": bot_id,
            "task_type": task_type,
            "task_detail": task_detail or {},
            "triggered_by": triggered_by,
            "execution_time_ms": execution_time_ms,
            "tokens_used": tokens_used
        }

        result = db.table("bot_task_log").insert(log_data).execute()
        return result.data[0]["id"]

    @staticmethod
    def log_lead_agent_scrape(
        org_id: str,
        user_id: str,
        business_name: str,
        source: str,
        execution_time_ms: int
    ) -> str:
        """Log a lead agent URL scrape task."""
        return BotTaskLogger.log_task(
            org_id=org_id,
            bot_id="lead-agent",
            task_type="prospect_scraped",
            task_detail={
                "business_name": business_name,
                "source": source
            },
            triggered_by=user_id,
            execution_time_ms=execution_time_ms
        )

    @staticmethod
    def log_lead_agent_insights(
        org_id: str,
        prospect_id: str,
        business_name: str,
        pain_points_count: int,
        tokens_used: int,
        execution_time_ms: int
    ) -> str:
        """Log AI insights generation for a prospect."""
        return BotTaskLogger.log_task(
            org_id=org_id,
            bot_id="lead-agent",
            task_type="insights_generated",
            task_detail={
                "prospect_id": prospect_id,
                "business_name": business_name,
                "pain_points_count": pain_points_count
            },
            triggered_by=None,  # Autonomous background task
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used
        )

    @staticmethod
    def log_lead_agent_call_script(
        org_id: str,
        prospect_id: str,
        business_name: str,
        user_id: Optional[str],
        tokens_used: int,
        execution_time_ms: int
    ) -> str:
        """Log call script generation."""
        return BotTaskLogger.log_task(
            org_id=org_id,
            bot_id="lead-agent",
            task_type="call_script_created",
            task_detail={
                "prospect_id": prospect_id,
                "business_name": business_name
            },
            triggered_by=user_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used
        )


class TaskTimer:
    """Context manager for timing task execution."""

    def __init__(self):
        self.start_time = None
        self.execution_time_ms = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.execution_time_ms = int((time.perf_counter() - self.start_time) * 1000)

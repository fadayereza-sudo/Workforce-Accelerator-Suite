"""
Generic task logger for AI agent activities.

Provides the base TaskLogger and TaskTimer. Apps build agent-specific
convenience methods on top of this.
"""
import time
from typing import Optional, Dict, Any

from core.database import get_supabase_admin


class TaskLogger:
    """Log AI agent tasks to bot_task_log table."""

    @staticmethod
    def log(
        org_id: str,
        bot_id: str,
        task_type: str,
        task_detail: Dict[str, Any] = None,
        app_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None
    ) -> str:
        """
        Log an agent task to the database.

        Args:
            org_id: Organization UUID
            bot_id: Bot/agent ID (e.g., 'lead-agent')
            task_type: Type of task (e.g., 'prospect_scraped', 'insights_generated')
            task_detail: Optional dict with task-specific data
            app_id: Optional app ID (e.g., 'workforce-accelerator')
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

        if app_id:
            log_data["app_id"] = app_id

        result = db.table("bot_task_log").insert(log_data).execute()
        return result.data[0]["id"]


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

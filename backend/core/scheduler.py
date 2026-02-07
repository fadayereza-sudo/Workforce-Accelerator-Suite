"""
Unified task scheduler for the app ecosystem.

Replaces the individual polling loops (notification_scheduler, report_scheduler)
with a single scheduler that collects tasks from all apps and runs them
with condition checks to avoid unnecessary work.
"""
import asyncio
import importlib
from datetime import datetime, timezone
from typing import Callable, Optional
from dataclasses import dataclass, field


@dataclass
class ScheduledTask:
    """A registered scheduled task from an app or agent."""
    name: str
    func_path: str               # Dotted path: 'module.path:function_name'
    interval_seconds: int         # How often to run
    condition_path: Optional[str] = None  # Optional condition check before running
    app_id: str = ""
    agent_id: Optional[str] = None
    last_run: Optional[datetime] = None
    enabled: bool = True


class TaskScheduler:
    """Unified scheduler for all apps. Tasks only run when conditions are met."""

    def __init__(self):
        self.tasks: list[ScheduledTask] = []
        self._running = False

    def register(self, task: ScheduledTask):
        """Register a task to be scheduled."""
        self.tasks.append(task)
        print(f"[Scheduler] Registered: {task.name} (every {task.interval_seconds}s)")

    async def start(self):
        """Main scheduler loop. Checks all tasks on their intervals."""
        self._running = True
        print(f"[Scheduler] Started with {len(self.tasks)} tasks")

        while self._running:
            now = datetime.now(timezone.utc)

            for task in self.tasks:
                if not task.enabled:
                    continue

                # Check if enough time has passed since last run
                if task.last_run:
                    elapsed = (now - task.last_run).total_seconds()
                    if elapsed < task.interval_seconds:
                        continue

                # Check condition (if any) before running
                if task.condition_path:
                    try:
                        condition_fn = _resolve_func(task.condition_path)
                        should_run = await condition_fn()
                        if not should_run:
                            task.last_run = now
                            continue
                    except Exception as e:
                        print(f"[Scheduler] Condition check failed for {task.name}: {e}")
                        task.last_run = now
                        continue

                # Run the task
                try:
                    task_fn = _resolve_func(task.func_path)
                    await task_fn()
                    task.last_run = now
                except Exception as e:
                    print(f"[Scheduler] Task {task.name} failed: {e}")
                    task.last_run = now  # Don't retry immediately

            await asyncio.sleep(10)  # Base tick: check every 10 seconds

    async def stop(self):
        """Stop the scheduler."""
        self._running = False


def _resolve_func(dotted_path: str) -> Callable:
    """Resolve 'module.path:function_name' to actual function."""
    module_path, func_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


# Global scheduler instance
scheduler = TaskScheduler()

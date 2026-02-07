"""
Timekeeping Agent — AI-powered follow-up scheduling from journal entries.
"""
from apps import AgentManifest


AGENT_ID = "timekeeping"
AGENT_NAME = "Timekeeping Agent"


def get_agent_manifest() -> AgentManifest:
    return AgentManifest(
        agent_id=AGENT_ID,
        name=AGENT_NAME,
        description="AI-powered notification scheduling for prospect follow-ups based on journal entries.",
        router_module=None,  # No direct routes — triggered by lead agent journal entries
        scheduled_tasks=[],
    )

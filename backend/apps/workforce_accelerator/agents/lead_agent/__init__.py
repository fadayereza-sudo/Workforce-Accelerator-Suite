"""
B2B Lead Agent — AI-powered prospect scraping, insights, and call scripts.
"""
from apps import AgentManifest


AGENT_ID = "lead-agent"
AGENT_NAME = "B2B Lead Agent"


def get_agent_manifest() -> AgentManifest:
    return AgentManifest(
        agent_id=AGENT_ID,
        name=AGENT_NAME,
        description="AI-powered B2B lead generation with prospect scraping, insights, and call script generation.",
        router_module="apps.workforce_accelerator.agents.lead_agent.router",
        scheduled_tasks=[
            {
                "name": "wa:lead-agent:notifications",
                "func_path": "apps.workforce_accelerator.agents.lead_agent.tasks:process_due_notifications",
                "interval_seconds": 60,
                "condition_path": "apps.workforce_accelerator.agents.lead_agent.tasks:has_pending_notifications",
            }
        ],
    )

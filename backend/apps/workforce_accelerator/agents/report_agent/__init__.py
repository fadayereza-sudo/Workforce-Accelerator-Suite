"""
Report Agent — LLM-generated activity and performance reports.
"""
from apps import AgentManifest


AGENT_ID = "report-agent"
AGENT_NAME = "Report Agent"


def get_agent_manifest() -> AgentManifest:
    return AgentManifest(
        agent_id=AGENT_ID,
        name=AGENT_NAME,
        description="LLM-powered activity reporting with team and agent performance summaries.",
        router_module="apps.workforce_accelerator.agents.report_agent.router",
        scheduled_tasks=[
            {
                "name": "wa:report-agent:reports",
                "func_path": "apps.workforce_accelerator.agents.report_agent.tasks:process_due_reports",
                "interval_seconds": 3600,
            }
        ],
    )

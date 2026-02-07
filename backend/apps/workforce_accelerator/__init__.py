"""
Workforce Accelerator — B2B sales productivity app.

Agents:
- Lead Agent: AI-powered prospect scraping, insights, call scripts
- Timekeeping Agent: Smart follow-up scheduling from journal entries
- Report Agent: LLM-generated activity and performance reports
"""
from apps import AppManifest, AgentManifest


APP_ID = "workforce-accelerator"
APP_NAME = "Workforce Accelerator"


def get_manifest() -> AppManifest:
    # Collect agent manifests
    from apps.workforce_accelerator.agents import get_agent_manifests
    agents = get_agent_manifests()

    return AppManifest(
        app_id=APP_ID,
        name=APP_NAME,
        description="B2B sales productivity suite with AI-powered lead generation, smart follow-ups, and automated reporting.",
        icon="briefcase",
        router_module="apps.workforce_accelerator.router",
        agents=agents,
        cache_pools=[
            # App-specific cache pools (core pools are registered automatically)
        ],
    )

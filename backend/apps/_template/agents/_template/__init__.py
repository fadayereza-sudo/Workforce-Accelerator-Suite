"""
Agent template — copy this directory to create a new agent.

Rename the directory and update AGENT_ID and AGENT_NAME below.
"""
from apps import AgentManifest


AGENT_ID = "my-agent"
AGENT_NAME = "My Agent"


def get_agent_manifest() -> AgentManifest:
    return AgentManifest(
        agent_id=AGENT_ID,
        name=AGENT_NAME,
        description="Description of your agent",
        router_module=None,
        scheduled_tasks=[],
    )

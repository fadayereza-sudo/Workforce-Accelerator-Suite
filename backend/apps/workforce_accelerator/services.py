"""
Workforce Accelerator — shared app-level helpers.
"""


def get_org_currency(org_settings: dict) -> str:
    """Get organization's lead agent currency from settings."""
    return org_settings.get("lead_agent_currency", "USD")

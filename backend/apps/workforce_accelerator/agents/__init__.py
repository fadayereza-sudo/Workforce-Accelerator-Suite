"""
Workforce Accelerator agents — auto-discovery.
"""
import importlib
import pkgutil
from typing import List
from apps import AgentManifest


def get_agent_manifests() -> List[AgentManifest]:
    """Discover all agents in this directory."""
    manifests = []

    import apps.workforce_accelerator.agents as agents_pkg

    for importer, modname, ispkg in pkgutil.iter_modules(agents_pkg.__path__):
        if not ispkg or modname.startswith("_"):
            continue

        try:
            mod = importlib.import_module(f"apps.workforce_accelerator.agents.{modname}")
            if hasattr(mod, "get_agent_manifest"):
                manifests.append(mod.get_agent_manifest())
        except Exception as e:
            print(f"[WA/Agents] Error loading {modname}: {e}")

    return manifests

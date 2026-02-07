"""
App ecosystem — auto-discovery and manifest system.

Each app in backend/apps/<name>/ exposes a get_manifest() function
that returns an AppManifest. The discover_apps() function scans for
all apps and returns their manifests for router registration.
"""
import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import List, Optional, Callable


@dataclass
class AgentManifest:
    """Describes a single AI agent within an app."""
    agent_id: str                          # e.g. 'lead-agent'
    name: str                              # e.g. 'B2B Lead Agent'
    description: str = ""
    router_module: Optional[str] = None    # Dotted path to module with `router` attribute
    scheduled_tasks: list = field(default_factory=list)  # List of ScheduledTask dicts


@dataclass
class AppManifest:
    """Describes a single app in the ecosystem."""
    app_id: str                            # e.g. 'workforce-accelerator'
    name: str                              # e.g. 'Workforce Accelerator'
    description: str = ""
    icon: str = ""
    router_module: Optional[str] = None    # Dotted path to module with `router` attribute
    agents: List[AgentManifest] = field(default_factory=list)
    cache_pools: list = field(default_factory=list)  # [{name, maxsize, ttl}]


def discover_apps() -> List[AppManifest]:
    """
    Scan backend/apps/ for app packages and collect their manifests.

    Each app package must have a get_manifest() function in its __init__.py.
    Packages starting with '_' are skipped (templates, helpers).
    """
    manifests = []

    # Import the apps package itself
    import apps

    for importer, modname, ispkg in pkgutil.iter_modules(apps.__path__):
        if not ispkg or modname.startswith("_"):
            continue

        try:
            mod = importlib.import_module(f"apps.{modname}")
            if hasattr(mod, "get_manifest"):
                manifest = mod.get_manifest()
                manifests.append(manifest)
                print(f"[Apps] Discovered: {manifest.name} ({manifest.app_id})")
            else:
                print(f"[Apps] Warning: apps.{modname} has no get_manifest()")
        except Exception as e:
            print(f"[Apps] Error loading apps.{modname}: {e}")

    return manifests

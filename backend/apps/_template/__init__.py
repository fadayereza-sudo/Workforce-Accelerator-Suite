"""
App template — copy this directory to create a new app.

Rename the directory to your app name (snake_case) and update:
1. APP_ID and APP_NAME below
2. models.py with your app's Pydantic models
3. router.py with app-level routes
4. agents/ with your AI agents
"""
from apps import AppManifest


APP_ID = "my-app"
APP_NAME = "My App"


def get_manifest() -> AppManifest:
    return AppManifest(
        app_id=APP_ID,
        name=APP_NAME,
        description="Description of your app",
        router_module="apps._template.router",
        agents=[],
        cache_pools=[],
    )

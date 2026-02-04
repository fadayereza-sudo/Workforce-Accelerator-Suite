"""
Application configuration from environment variables.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings

# .env is in the project root (parent of backend/)
ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""  # anon key for client
    supabase_service_key: str = ""  # service key for admin ops

    # Telegram Bots
    bot_hub_token: str = ""
    BOT_USERNAME: str = "apex_workforce_bot"
    MINI_APP_SHORTNAME: str = "hub"  # The shortname configured in BotFather for the Web App

    # AI Services
    openai_api_key: str = ""  # For URL scraping and business insights generation

    # App settings
    app_url: str = "http://localhost:8000"  # For generating invite links
    debug: bool = True

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

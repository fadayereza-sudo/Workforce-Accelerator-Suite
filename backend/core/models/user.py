"""
User-related models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TelegramUser(BaseModel):
    """User data from Telegram initData."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    photo_url: Optional[str] = None


class UserCreate(BaseModel):
    """Data needed to create a user."""
    telegram_id: int
    telegram_username: Optional[str] = None
    full_name: str
    avatar_url: Optional[str] = None


class User(BaseModel):
    """Full user model from database."""
    id: str
    telegram_id: int
    telegram_username: Optional[str] = None
    full_name: str
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

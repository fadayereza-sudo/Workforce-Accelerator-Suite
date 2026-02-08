"""
Lead Agent models for products, prospects, and search operations.
"""
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT MODELS
# ─────────────────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    """Create a new product/service."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[Decimal] = Field(None, ge=0)


class ProductUpdate(BaseModel):
    """Update an existing product."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None


class Product(BaseModel):
    """Full product model from database."""
    id: str
    org_id: str
    name: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# PROSPECT MODELS
# ─────────────────────────────────────────────────────────────────────────────

class PainPoint(BaseModel):
    """A single pain point that products can solve (legacy format)."""
    title: str
    description: str
    relevant_product: Optional[str] = None


class SalesToolkitItem(BaseModel):
    """Complete sales toolkit for a single pain point."""
    title: str
    description: str
    relevant_product: Optional[str] = None
    revenue_rank: int                          # 1 = most revenue potential for prospect
    solution_summary: str                      # How our product solves this
    question: str                              # Pain point rephrased as a simple question
    opposition_points: List[dict] = []         # 5x {opposition_statement, disarming_key_point}
    key_points: List[str] = []                 # Disarming points (visible to user)
    urgency_statement: str = ""                # Ambition-oriented time pressure
    whatsapp_message: str = ""                 # Ready-to-send message


class ProspectCreate(BaseModel):
    """Create a prospect (internal, from scraping)."""
    business_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    search_query: str
    source: str = "gemini_search"


class ProspectManualCreate(BaseModel):
    """Manually create a prospect (user input)."""
    business_name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    google_maps_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)


class ProspectStatusUpdate(BaseModel):
    """Update prospect status."""
    status: str = Field(
        ...,
        pattern="^(not_contacted|contacted|ongoing_conversations|closed)$"
    )


class ProspectContactUpdate(BaseModel):
    """Update prospect contact information."""
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)


class Prospect(BaseModel):
    """Full prospect model from database."""
    id: str
    org_id: str
    business_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    search_query: str
    source: str
    business_summary: Optional[str] = None
    pain_points: List[PainPoint] = []
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CallScriptItem(BaseModel):
    """A single Q&A item in the call script."""
    question: str
    answer: str


class ProspectCard(BaseModel):
    """Prospect data formatted as a cue card for display."""
    id: str
    business_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    summary: Optional[str] = None
    pain_points: List[PainPoint] = []
    sales_toolkit: List[dict] = []             # Enriched pain points with scripts
    call_script: List[CallScriptItem] = []     # Legacy
    ai_overview: Optional[str] = None
    next_follow_up: Optional[dict] = None
    status: str
    search_query: Optional[str] = None  # Optional for URL-scraped prospects
    source: str = "gemini_search"
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH MODELS
# ─────────────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Request to search for prospects."""
    query: str = Field(..., min_length=3, max_length=200)


class ScrapeRequest(BaseModel):
    """Request to scrape a business from a URL."""
    url: str = Field(..., min_length=10, max_length=500)


class SearchResult(BaseModel):
    """Result of a prospect search."""
    search_id: str
    query: str
    total_found: int
    new_prospects: int
    skipped_duplicates: int
    prospects: List[ProspectCard]


class SearchHistory(BaseModel):
    """Historical search record."""
    id: str
    query: str
    results_count: int
    new_prospects_count: int
    skipped_duplicates_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD MODELS
# ─────────────────────────────────────────────────────────────────────────────

class LeadAgentDashboard(BaseModel):
    """Dashboard statistics for lead agent."""
    total_prospects: int
    by_status: dict  # {"not_contacted": 5, "contacted": 3, ...}
    products_count: int
    recent_searches: List[SearchHistory]
    currency: str


# ─────────────────────────────────────────────────────────────────────────────
# CURRENCY SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

class CurrencyUpdate(BaseModel):
    """Update organization's lead agent currency."""
    currency: str = Field(..., min_length=3, max_length=3)


class OrgSettingsUpdate(BaseModel):
    """Update organization's lead agent settings."""
    website: Optional[str] = Field(None, max_length=500)
    instagram: Optional[str] = Field(None, max_length=200)
    achievements: Optional[str] = Field(None, max_length=2000)
    partnerships: Optional[str] = Field(None, max_length=2000)
    outstanding_facts: Optional[str] = Field(None, max_length=2000)
    growth_metrics: Optional[str] = Field(None, max_length=2000)


# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL ENTRY MODELS
# ─────────────────────────────────────────────────────────────────────────────

class JournalEntryCreate(BaseModel):
    """Create a new journal entry."""
    content: str = Field(..., min_length=1, max_length=2000)
    interaction_type: str = Field(
        default="note",
        pattern="^(call|email|whatsapp|meeting|text|note|other)$"
    )


class JournalEntryUpdate(BaseModel):
    """Update an existing journal entry."""
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    interaction_type: Optional[str] = Field(
        None,
        pattern="^(call|email|whatsapp|meeting|text|note|other)$"
    )


class JournalEntry(BaseModel):
    """Full journal entry model from database."""
    id: str
    prospect_id: str
    user_id: str
    content: str
    interaction_type: str
    author_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

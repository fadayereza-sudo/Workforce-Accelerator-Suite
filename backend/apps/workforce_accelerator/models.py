"""
Workforce Accelerator models — Products, Prospects, Journal Entries,
Customers, Team Analytics, Agent Analytics.

These are app-specific models. Core models (User, Org, Membership, Billing,
Reports) live in core.models.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCT MODELS
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# PROSPECT MODELS
# ═══════════════════════════════════════════════════════════════════════════

class PainPoint(BaseModel):
    """A single pain point that products can solve."""
    title: str
    description: str
    relevant_product: Optional[str] = None


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
    call_script: List[CallScriptItem] = []
    ai_overview: Optional[str] = None
    next_follow_up: Optional[dict] = None
    status: str
    search_query: Optional[str] = None
    source: str = "gemini_search"
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# SEARCH MODELS
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD MODELS
# ═══════════════════════════════════════════════════════════════════════════

class LeadAgentDashboard(BaseModel):
    """Dashboard statistics for lead agent."""
    total_prospects: int
    by_status: dict
    products_count: int
    recent_searches: List[SearchHistory]
    currency: str


# ═══════════════════════════════════════════════════════════════════════════
# CURRENCY SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

class CurrencyUpdate(BaseModel):
    """Update organization's lead agent currency."""
    currency: str = Field(..., min_length=3, max_length=3)


# ═══════════════════════════════════════════════════════════════════════════
# JOURNAL ENTRY MODELS
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITY TRACKING (Admin dashboard)
# ═══════════════════════════════════════════════════════════════════════════

class ActivityLogCreate(BaseModel):
    """Log activity for a member."""
    org_id: str
    bot_id: Optional[str] = None
    action_type: str
    action_detail: Dict[str, Any] = {}


class MemberActivity(BaseModel):
    """Member with activity summary."""
    user_id: str
    membership_id: str
    full_name: str
    telegram_username: Optional[str] = None
    role: str
    last_active_at: Optional[datetime] = None
    activity_count: int = 0
    bots_accessed: List[str] = []
    leads_generated: int = 0
    diary_entries: int = 0

    class Config:
        from_attributes = True


class TeamAnalytics(BaseModel):
    """Team activity analytics response."""
    period: str
    period_start: datetime
    period_end: datetime
    total_members: int
    active_members: int
    total_activities: int
    members: List[MemberActivity]


class LeadAgentOverview(BaseModel):
    """Lead agent overview stats for admin dashboard."""
    active_leads: int = 0
    scheduled_followups: int = 0
    today_events: List[str] = []
    today_summary: str = ""


class AgentUsage(BaseModel):
    """Agent usage stats."""
    bot_id: str
    bot_name: str
    bot_icon: Optional[str] = None
    task_count: int = 0
    active_users: int = 0


class AgentAnalytics(BaseModel):
    """Agent analytics response."""
    period: str
    period_start: datetime
    period_end: datetime
    total_tasks: int
    agents: List[AgentUsage]


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOMER DATABASE
# ═══════════════════════════════════════════════════════════════════════════

class CustomerCreate(BaseModel):
    """Create a new customer."""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "US"
    status: str = "active"
    customer_type: str = "individual"
    tags: List[str] = []
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Update a customer."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    customer_type: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class Customer(BaseModel):
    """Customer record."""
    id: str
    org_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    status: str
    customer_type: str
    lifetime_value: Decimal = Decimal("0")
    tags: List[str] = []
    notes: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerList(BaseModel):
    """Paginated customer list response."""
    customers: List[Customer]
    total: int
    limit: int
    offset: int


class ImportJobCreate(BaseModel):
    """Create import job."""
    file_name: str


class ImportJobResponse(BaseModel):
    """Import job status response."""
    job_id: str
    status: str
    total_rows: int
    imported_count: int
    skipped_count: int
    error_count: int
    message: str

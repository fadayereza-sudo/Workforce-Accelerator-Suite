"""
Admin dashboard models for analytics, customers, and billing.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel


# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITY TRACKING
# ═══════════════════════════════════════════════════════════════════════════

class ActivityLogCreate(BaseModel):
    """Log activity for a member."""
    org_id: str
    bot_id: Optional[str] = None
    action_type: str  # 'page_view', 'task_completed', 'search', 'create', 'update', 'delete'
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
    period: str  # 'day', 'week', 'month'
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


# ═══════════════════════════════════════════════════════════════════════════
# BILLING
# ═══════════════════════════════════════════════════════════════════════════

class SubscriptionPlan(BaseModel):
    """Available subscription plan."""
    id: str
    name: str
    description: Optional[str] = None
    price_monthly: int  # cents
    price_yearly: Optional[int] = None
    max_members: Optional[int] = None  # None = unlimited
    max_customers: Optional[int] = None
    features: List[str] = []
    is_active: bool = True

    class Config:
        from_attributes = True


class OrgSubscription(BaseModel):
    """Organization's current subscription."""
    id: str
    org_id: str
    plan_id: str
    plan: SubscriptionPlan
    billing_cycle: str  # 'monthly', 'yearly'
    status: str  # 'active', 'canceled', 'past_due', 'trialing'
    trial_ends_at: Optional[datetime] = None
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionUpgrade(BaseModel):
    """Upgrade subscription request."""
    plan_id: str
    billing_cycle: str = "monthly"


class InvoiceLineItem(BaseModel):
    """Invoice line item."""
    description: str
    quantity: int = 1
    unit_price: int  # cents
    amount: int  # cents


class Invoice(BaseModel):
    """Invoice record."""
    id: str
    org_id: str
    invoice_number: str
    subtotal: int  # cents
    tax: int = 0
    total: int  # cents
    currency: str = "USD"
    status: str  # 'draft', 'open', 'paid', 'void', 'uncollectible'
    issue_date: date
    due_date: date
    paid_at: Optional[datetime] = None
    line_items: List[InvoiceLineItem] = []
    pdf_url: Optional[str] = None

    class Config:
        from_attributes = True


class InvoiceList(BaseModel):
    """Invoice list response."""
    invoices: List[Invoice]
    total: int


class BillingOverview(BaseModel):
    """Billing overview for dashboard."""
    subscription: OrgSubscription
    usage: Dict[str, Any]  # {members_used, members_limit, customers_used, customers_limit}
    invoices: List[Invoice]

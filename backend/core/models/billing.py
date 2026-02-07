"""
Billing models - subscription plans, org subscriptions, invoices.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


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

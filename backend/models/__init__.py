"""
Pydantic models — compatibility shim.

Core models re-exported from core.models.*.
App-specific models remain in their local files until Phase 2 migration.
"""
# ── Core models (from core.models) ──────────────────────────────────────────
from core.models.user import TelegramUser, User, UserCreate
from core.models.org import Organization, OrgCreate, InviteCode, OrgStats, OrgDetails, OrgUpdate
from core.models.membership import (
    MembershipRequest,
    MembershipRequestCreate,
    MembershipRequestResponse,
    MembershipApproval,
    Member,
    BotAccess,
    AppAccess,
    MemberBotsUpdate,
    MemberAppsUpdate,
    MemberRoleUpdate
)
from core.models.billing import (
    SubscriptionPlan,
    OrgSubscription,
    SubscriptionUpgrade,
    Invoice,
    InvoiceLineItem,
    InvoiceList,
    BillingOverview
)
from core.models.reports import (
    BotTaskLogEntry,
    ActivityReport,
    ReportListItem,
    ReportsList,
    GenerateReportRequest,
    ReportSummaryResponse
)

# ── App-specific models (stay local until Phase 2) ──────────────────────────
from .lead_agent import (
    ProductCreate,
    ProductUpdate,
    Product,
    PainPoint,
    SalesToolkitItem,
    ProspectCreate,
    ProspectManualCreate,
    ProspectStatusUpdate,
    ProspectContactUpdate,
    Prospect,
    ProspectCard,
    SearchRequest,
    ScrapeRequest,
    SearchResult,
    SearchHistory,
    LeadAgentDashboard,
    CurrencyUpdate,
    OrgSettingsUpdate,
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntry
)
from .admin import (
    ActivityLogCreate,
    MemberActivity,
    LeadAgentOverview,
    TeamAnalytics,
    AgentUsage,
    AgentAnalytics,
    CustomerCreate,
    CustomerUpdate,
    Customer,
    CustomerList,
    ImportJobCreate,
    ImportJobResponse,
)

__all__ = [
    # Core — User
    "TelegramUser", "User", "UserCreate",
    # Core — Org
    "Organization", "OrgCreate", "InviteCode", "OrgStats", "OrgDetails", "OrgUpdate",
    # Core — Membership
    "MembershipRequest", "MembershipRequestCreate", "MembershipRequestResponse",
    "MembershipApproval", "Member", "BotAccess", "AppAccess", "MemberBotsUpdate", "MemberAppsUpdate", "MemberRoleUpdate",
    # Core — Billing
    "SubscriptionPlan", "OrgSubscription", "SubscriptionUpgrade",
    "Invoice", "InvoiceLineItem", "InvoiceList", "BillingOverview",
    # Core — Reports
    "BotTaskLogEntry", "ActivityReport", "ReportListItem", "ReportsList",
    "GenerateReportRequest", "ReportSummaryResponse",
    # App — Lead Agent
    "ProductCreate", "ProductUpdate", "Product", "PainPoint", "SalesToolkitItem",
    "ProspectCreate", "ProspectManualCreate", "ProspectStatusUpdate", "ProspectContactUpdate",
    "Prospect", "ProspectCard", "SearchRequest", "ScrapeRequest",
    "SearchResult", "SearchHistory", "LeadAgentDashboard", "CurrencyUpdate", "OrgSettingsUpdate",
    "JournalEntryCreate", "JournalEntryUpdate", "JournalEntry",
    # App — Admin
    "ActivityLogCreate", "MemberActivity", "LeadAgentOverview",
    "TeamAnalytics", "AgentUsage", "AgentAnalytics",
    "CustomerCreate", "CustomerUpdate", "Customer", "CustomerList",
    "ImportJobCreate", "ImportJobResponse",
]

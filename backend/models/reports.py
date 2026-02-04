"""
Report models for activity monitoring and LLM-generated reports.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ═══════════════════════════════════════════════════════════════════════════
# BOT TASK LOG
# ═══════════════════════════════════════════════════════════════════════════

class BotTaskLogEntry(BaseModel):
    """Single bot task log entry."""
    id: str
    org_id: str
    bot_id: str
    task_type: str
    task_detail: Dict[str, Any] = {}
    triggered_by: Optional[str] = None
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITY REPORTS
# ═══════════════════════════════════════════════════════════════════════════

class ActivityReport(BaseModel):
    """Activity report with LLM-generated summary."""
    id: str
    org_id: str
    report_type: str  # 'team', 'agent', 'combined'
    period_type: str  # 'daily', 'weekly', 'monthly'
    period_start: date
    period_end: date
    user_id: Optional[str] = None
    bot_id: Optional[str] = None
    raw_metrics: Dict[str, Any] = {}
    summary_text: str
    highlights: List[str] = []
    recommendations: List[str] = []
    generated_by: str = "gpt-4o-mini"
    tokens_used: Optional[int] = None
    generation_time_ms: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportListItem(BaseModel):
    """Lightweight report item for listing."""
    id: str
    report_type: str
    period_type: str
    period_start: date
    period_end: date
    bot_id: Optional[str] = None
    bot_name: Optional[str] = None
    created_at: datetime


class ReportsList(BaseModel):
    """Paginated list of reports."""
    reports: List[ReportListItem]
    total: int


class GenerateReportRequest(BaseModel):
    """Request to generate a report on-demand."""
    report_type: str  # 'team' or 'agent'
    period_type: str  # 'daily', 'weekly', 'monthly'
    period_start: date
    bot_id: Optional[str] = None  # Required for agent reports


class ReportSummaryResponse(BaseModel):
    """Summary response for dashboard widgets."""
    team_report: Optional[ActivityReport] = None
    agent_reports: List[ActivityReport] = []
    has_data: bool = False

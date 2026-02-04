"""
Report Generator Service - LLM-powered activity report generation.

Uses GPT-4o-mini for cost-effective summarization of activity data.
Generates compelling business-friendly reports from raw metrics.
"""
import json
from datetime import date, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
from openai import AsyncOpenAI


@dataclass
class TeamReportMetrics:
    """Raw metrics for team activity report."""
    period_type: str
    period_start: date
    period_end: date
    total_members: int
    active_members: int
    total_activities: int
    activities_by_type: Dict[str, int]
    top_performers: List[Dict[str, Any]]  # [{name, activity_count, bots_used}]
    bots_accessed: Dict[str, int]  # bot_id -> user_count


@dataclass
class AgentReportMetrics:
    """Raw metrics for agent/bot activity report."""
    period_type: str
    period_start: date
    period_end: date
    bot_id: str
    bot_name: str
    total_tasks: int
    tasks_by_type: Dict[str, int]
    unique_users: int
    total_execution_time_ms: int
    total_tokens_used: int
    highlights: List[Dict[str, Any]]  # Specific achievements


class ReportGenerator:
    """Generate LLM-powered activity reports."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_team_report(
        self,
        metrics: TeamReportMetrics,
        org_name: str
    ) -> Dict[str, Any]:
        """
        Generate a team activity report summary.

        Returns:
            {
                "summary_text": "...",
                "highlights": [...],
                "recommendations": [...],
                "tokens_used": int
            }
        """
        period_label = self._get_period_label(metrics.period_type, metrics.period_start)

        # Build context for LLM
        top_performers_text = "\n".join([
            f"- {p['name']}: {p['activity_count']} activities, used {len(p.get('bots_used', []))} agents"
            for p in metrics.top_performers[:5]
        ]) or "No activity recorded"

        bots_text = "\n".join([
            f"- {bot_id}: {count} users"
            for bot_id, count in metrics.bots_accessed.items()
        ]) or "No agent usage recorded"

        prompt = f"""You are a business analytics assistant writing a team productivity report for "{org_name}".

PERIOD: {period_label}

RAW METRICS:
- Total team members: {metrics.total_members}
- Active members this period: {metrics.active_members} ({self._calc_percentage(metrics.active_members, metrics.total_members)}% engagement)
- Total activities logged: {metrics.total_activities}
- Activities by type: {json.dumps(metrics.activities_by_type)}

TOP PERFORMERS:
{top_performers_text}

AI AGENT USAGE:
{bots_text}

TASK:
Write a professional but engaging summary (2-3 paragraphs) that:
1. Highlights team productivity and engagement
2. Celebrates top contributors without being excessive
3. Notes which AI agents are driving value
4. Sounds impressive to business stakeholders while being factual

Also provide 3-5 KEY HIGHLIGHTS as brief bullet points (achievements, milestones).

Respond ONLY with valid JSON:
{{
    "summary_text": "...",
    "highlights": ["highlight 1", "highlight 2", ...],
    "recommendations": ["suggestion 1", "suggestion 2", ...]
}}"""

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analytics assistant. Write clear, factual, and professional reports. Avoid hype but make achievements sound meaningful. Respond only with valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=800
        )

        result = json.loads(response.choices[0].message.content)
        result["tokens_used"] = response.usage.total_tokens

        return result

    async def generate_agent_report(
        self,
        metrics: AgentReportMetrics,
        org_name: str
    ) -> Dict[str, Any]:
        """
        Generate an AI agent activity report summary.

        Returns:
            {
                "summary_text": "...",
                "highlights": [...],
                "tokens_used": int
            }
        """
        period_label = self._get_period_label(metrics.period_type, metrics.period_start)

        # Build task breakdown
        tasks_text = "\n".join([
            f"- {task_type}: {count} times"
            for task_type, count in metrics.tasks_by_type.items()
        ]) or "No tasks recorded"

        # Build highlights text
        highlights_text = "\n".join([
            f"- {h.get('description', str(h))}"
            for h in metrics.highlights[:5]
        ]) or "No specific highlights"

        # Format execution time nicely
        exec_seconds = metrics.total_execution_time_ms / 1000
        if exec_seconds > 3600:
            exec_time_str = f"{exec_seconds / 3600:.1f} hours"
        elif exec_seconds > 60:
            exec_time_str = f"{exec_seconds / 60:.1f} minutes"
        else:
            exec_time_str = f"{exec_seconds:.1f} seconds"

        prompt = f"""You are a business analytics assistant writing an AI agent performance report for "{org_name}".

AGENT: {metrics.bot_name}
PERIOD: {period_label}

RAW METRICS:
- Total tasks completed: {metrics.total_tasks}
- Unique team members using this agent: {metrics.unique_users}
- Total processing time: {exec_time_str}
- AI tokens consumed: {metrics.total_tokens_used:,}

TASK BREAKDOWN:
{tasks_text}

NOTABLE ACHIEVEMENTS:
{highlights_text}

TASK:
Write a compelling summary (2-3 paragraphs) that:
1. Quantifies the value this AI agent delivered
2. Highlights autonomous work the agent performed
3. Shows ROI through time saved or leads generated
4. Impresses business stakeholders while sticking to facts

Also provide 3-5 KEY HIGHLIGHTS as brief achievement bullet points.

Respond ONLY with valid JSON:
{{
    "summary_text": "...",
    "highlights": ["highlight 1", "highlight 2", ...]
}}"""

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analytics assistant specializing in AI productivity metrics. Write factual, impressive reports that demonstrate ROI. Respond only with valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=600
        )

        result = json.loads(response.choices[0].message.content)
        result["tokens_used"] = response.usage.total_tokens

        return result

    def _get_period_label(self, period_type: str, period_start: date) -> str:
        """Get human-readable period label."""
        if period_type == "daily":
            return period_start.strftime("%A, %B %d, %Y")
        elif period_type == "weekly":
            end = period_start + timedelta(days=6)
            return f"Week of {period_start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
        elif period_type == "monthly":
            return period_start.strftime("%B %Y")
        return str(period_start)

    def _calc_percentage(self, part: int, whole: int) -> int:
        """Calculate percentage safely."""
        if whole == 0:
            return 0
        return round((part / whole) * 100)

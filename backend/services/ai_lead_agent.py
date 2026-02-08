"""
AI service for lead agent - generates business summaries and sales toolkits using OpenAI GPT-4o.

This is the second tier of our two-tier LLM pipeline:
1. GPT-4o-mini (cheap) - Extract & summarize business info from HTML
2. GPT-4o (smart) - Generate insights, pain points, and complete sales toolkits
"""
import json
from typing import List, Optional
from openai import AsyncOpenAI

from models.lead_agent import Product


SYSTEM_PROMPT = (
    "You are a B2B sales intelligence and outreach assistant. "
    "Your purpose is to help users generate highly targeted first-contact sales scripts (phone + WhatsApp) "
    "for cold prospects, using insights derived from the prospect's website and the user's available products/services. "
    "This is always a first-time interaction with the prospect. "
    "Your goal is not manipulation. Your goal is service-driven selling: identify what the prospect likely wants or needs, "
    "then help the user present a relevant solution respectfully and efficiently. "
    "Sales is defined as helping people get what they want. "
    "If a proof point is not provided, do NOT invent it — use generic credibility framing instead. "
    "Never invent achievements, partnerships, facts, or growth metrics. "
    "Never reveal opposition statements to the user. "
    "Never sound robotic or salesy. Never overwhelm with information. "
    "Assume low trust (cold outreach). Optimize for real human conversation, not scripts. "
    "Respond only with valid JSON."
)


class LeadAgentAI:
    """AI-powered lead analysis using OpenAI GPT-4o for stronger reasoning."""

    def __init__(self, api_key: str):
        """Initialize with OpenAI API key."""
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_prospect_insights(
        self,
        business_name: str,
        business_address: Optional[str],
        business_website: Optional[str],
        products: List[Product],
        business_description: Optional[str] = None,
        org_website: Optional[str] = None,
        org_instagram: Optional[str] = None,
        achievements: Optional[str] = None,
        partnerships: Optional[str] = None,
        outstanding_facts: Optional[str] = None,
        growth_metrics: Optional[str] = None
    ) -> tuple[str, list]:
        """
        Generate business summary and complete sales toolkit for a prospect.

        Args:
            business_name: Name of the business
            business_address: Business address (optional)
            business_website: Business website (optional)
            products: List of organization's products/services
            business_description: Pre-extracted description from website (optional)
            org_website: Organization's website URL (optional)
            org_instagram: Organization's Instagram handle/URL (optional)
            achievements: Company achievements - proof points, milestones, awards, outcomes (optional)
            partnerships: Significant partnerships - recognizable partners, clients, institutions (optional)
            outstanding_facts: Notable verifiable claims about the company (optional)
            growth_metrics: Measurements of growth/success - numbers, percentages, timeframes (optional)

        Returns:
            tuple: (business_summary, sales_toolkit_items)
        """
        # Build products context
        if products:
            products_context = "\n".join([
                f"- {p.name}: {p.description or 'No description'} "
                f"(Price: {p.price} per unit)" if p.price else f"- {p.name}: {p.description or 'No description'}"
                for p in products
            ])
        else:
            products_context = "No products defined yet."

        # Include business description if available (from URL scraper)
        description_context = ""
        if business_description:
            description_context = f"\n- About: {business_description}"

        # Build org contact context
        org_contact_parts = []
        if org_website:
            org_contact_parts.append(f"- Website: {org_website}")
        if org_instagram:
            org_contact_parts.append(f"- Instagram: {org_instagram}")
        org_contact = "\n".join(org_contact_parts) if org_contact_parts else "No contact info provided."

        # Build structured credibility context
        credibility_parts = []
        if achievements:
            credibility_parts.append(f"Company Achievements:\n{achievements}")
        if partnerships:
            credibility_parts.append(f"Significant Partnerships:\n{partnerships}")
        if outstanding_facts:
            credibility_parts.append(f"Outstanding Facts:\n{outstanding_facts}")
        if growth_metrics:
            credibility_parts.append(f"Measurements of Growth/Success:\n{growth_metrics}")
        credibility_context = "\n\n".join(credibility_parts) if credibility_parts else "No credibility data provided."

        prompt = f"""Analyze this business prospect and generate a complete sales toolkit.

PROSPECT INFORMATION:
- Business Name: {business_name}
- Address: {business_address or 'Unknown'}
- Website: {business_website or 'Unknown'}{description_context}

OUR PRODUCTS/SERVICES:
{products_context}

OUR COMPANY CONTACT:
{org_contact}

OUR CREDIBILITY DATA:
{credibility_context}

TASKS:

1. WEBSITE ANALYSIS & BUSINESS SUMMARY:
   - Understand what the prospect does, their business model and customers
   - Infer operational context and extract realistic commercial signals
   - Write a 2-3 sentence summary of the prospect's business, target market, and potential needs

2. PAIN POINT IDENTIFICATION:
   Generate the TOP 3 most likely business pain points that:
   - Are genuinely plausible based on the prospect's website/description
   - Can be solved by our products/services
   - Are ranked from highest to lowest potential financial impact for the prospect
   Each pain point must be practical, revenue-related, actionable, and aligned with our offerings.
   Never invent unrealistic problems.

3. For EACH pain point, generate the following:

a) PAIN POINT: A short title (max 6 words) and 1-2 sentence description.

b) RELEVANT PRODUCT: Which of our products/services solves this. Use the exact product name or null.

c) SOLUTION SUMMARY: 1-2 sentences explaining how our product resolves this pain point.

d) QUESTION: Convert the pain point into a simple, respectful, non-condescending yes/no question suitable for cold outreach. Rules:
   - Extremely simple language. Matter-of-fact tone.
   - No intelligence-insulting phrasing. No open-ended questions.
   - No pressure. No assumptions.
   - Under 15 words.
   - NEVER use words like "struggle", "challenge", "difficult", "hard" — these are condescending.
   - Pattern: "Would you be interested in X?" NOT "Are you struggling with X?"

   EXAMPLE (for a sports club, pain point "hard to find talented players"):
   BAD: "Do you find it hard to identify sports talent in the UAE?" (implies incompetence)
   GOOD: "Would you guys be interested in taking on some extra players?" (inviting, simple)

e) OPPOSITION STATEMENTS: Generate exactly 5 realistic internal opposition statements representing the prospect's natural skepticism (e.g. "it's probably too expensive", "sounds like a scam", "they're probably desperate for clients", "I doubt they can deliver", "waste of my time"). These are NEVER shown to the user.

f) DISARMING KEY POINTS: For EACH opposition statement, generate a conversational counter-frame using credibility, transparency, proof, brevity, respect for their time, and value signaling.

   MANDATORY: Use the credibility data fields to strengthen these points when relevant:
   - Company Achievements
   - Significant Partnerships
   - Outstanding Facts
   - Measurements of Growth/Success

   Rules:
   - Only use proof points that were explicitly provided
   - Never fabricate numbers, partner names, awards, or outcomes
   - Prefer concise proof points that sound natural in conversation
   - If no proof exists for a point, use a neutral version (transparency, process clarity, low-friction next step)

   Extract these as 3-5 concise key points for the sales rep to reference during the call. These naturally address concerns WITHOUT mentioning the opposition statements themselves.

g) URGENCY STATEMENT: Create an ambition-oriented urgency statement. NEVER use fear, fake scarcity, or false claims. Instead use ambition-oriented time pressure: signal demand, standards, momentum, selectivity.

   MANDATORY: Leverage provided credibility fields where applicable:
   - Company Achievements
   - Significant Partnerships
   - Outstanding Facts
   - Measurements of Growth/Success

   Rules:
   - Do not claim limited availability unless inputs support it
   - If no numeric or partner proof exists, use softer urgency
   - Keep it human, calm, and earned
   - End with a clear call to action

h) WHATSAPP MESSAGE: Compose a professional WhatsApp message (under 150 words) that:
   - Opens with a friendly, personalized greeting mentioning their business name
   - Focuses ONLY on this specific pain point
   - Explains the solution
   - Naturally incorporates the same disarming key points
   - Includes urgency
   - Ends with a clear next step
   - Includes our website and/or Instagram for credibility (if provided)
   - Written in normal paragraph form (not bullets)
   - Sounds human and warm, not templated or robotic
   - Focuses ONLY on this one pain point — do not mention other pain points

Respond ONLY with valid JSON in this exact format:
{{
    "business_summary": "...",
    "sales_toolkit": [
        {{
            "title": "...",
            "description": "...",
            "relevant_product": "product name or null",
            "revenue_rank": 1,
            "solution_summary": "...",
            "question": "...",
            "opposition_points": [
                {{
                    "opposition_statement": "...",
                    "disarming_key_point": "..."
                }},
                {{
                    "opposition_statement": "...",
                    "disarming_key_point": "..."
                }},
                {{
                    "opposition_statement": "...",
                    "disarming_key_point": "..."
                }},
                {{
                    "opposition_statement": "...",
                    "disarming_key_point": "..."
                }},
                {{
                    "opposition_statement": "...",
                    "disarming_key_point": "..."
                }}
            ],
            "key_points": [
                "concise talking point 1",
                "concise talking point 2",
                "concise talking point 3",
                "concise talking point 4",
                "concise talking point 5"
            ],
            "urgency_statement": "...",
            "whatsapp_message": "..."
        }},
        {{
            "title": "...",
            "description": "...",
            "relevant_product": "product name or null",
            "revenue_rank": 2,
            "solution_summary": "...",
            "question": "...",
            "opposition_points": [ ... ],
            "key_points": [ ... ],
            "urgency_statement": "...",
            "whatsapp_message": "..."
        }},
        {{
            "title": "...",
            "description": "...",
            "relevant_product": "product name or null",
            "revenue_rank": 3,
            "solution_summary": "...",
            "question": "...",
            "opposition_points": [ ... ],
            "key_points": [ ... ],
            "urgency_statement": "...",
            "whatsapp_message": "..."
        }}
    ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4000
            )

            result = json.loads(response.choices[0].message.content)

            business_summary = result.get("business_summary", "")

            # Extract and validate sales toolkit
            sales_toolkit = []
            for item in result.get("sales_toolkit", [])[:3]:
                toolkit_item = {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "relevant_product": item.get("relevant_product"),
                    "revenue_rank": item.get("revenue_rank", len(sales_toolkit) + 1),
                    "solution_summary": item.get("solution_summary", ""),
                    "question": item.get("question", ""),
                    "opposition_points": item.get("opposition_points", [])[:5],
                    "key_points": item.get("key_points", [])[:5],
                    "urgency_statement": item.get("urgency_statement", ""),
                    "whatsapp_message": item.get("whatsapp_message", "")
                }
                sales_toolkit.append(toolkit_item)

            # Sort by revenue_rank
            sales_toolkit.sort(key=lambda x: x.get("revenue_rank", 99))

            return business_summary, sales_toolkit

        except Exception as e:
            print(f"Error generating AI insights: {e}")
            return "", []

"""
AI service for lead agent - generates business summaries and unified sales scripts using OpenAI GPT-4o.

This is the second tier of our two-tier LLM pipeline:
1. GPT-4o-mini (cheap) - Extract & summarize business info from HTML
2. GPT-4o (smart) - Generate insights and a unified sales script
"""
import json
from typing import List, Optional
from openai import AsyncOpenAI

from apps.workforce_accelerator.models import Product


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
    ) -> tuple[str, dict]:
        """
        Generate business summary and a unified sales script for a prospect.

        Returns:
            tuple: (business_summary, script_data) where script_data is
                   {"type": "unified_script", "sales_script": str, "whatsapp_messages": list}
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

        prompt = f"""Analyze this business prospect and generate a unified sales call script.

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

1. BUSINESS SUMMARY:
   - Understand what the prospect does, their business model and customers
   - Write a 2-3 sentence summary of the prospect's business, target market, and potential needs

2. PAIN POINT IDENTIFICATION (internal step — do not output separately):
   Identify the TOP 3 most likely business pain points that:
   - Are genuinely plausible based on the prospect's website/description
   - Can be solved by our products/services
   - Are ranked from highest to lowest potential financial impact for the prospect
   Each pain point must be practical, revenue-related, actionable, and aligned with our offerings.

   For each pain point, also internally generate:
   - 5 realistic opposition statements (the prospect's natural skepticism)
   - Conversational counter-frames using the credibility data to disarm each objection
   - An ambition-oriented urgency statement

3. UNIFIED SALES SCRIPT:
   Write ONE continuous, flowing sales call script that covers all 3 pain points in sequence. This script is a conversation guide the sales rep reads top to bottom during a cold call.

   STRUCTURE — for each of the 3 pain points, the script flows through these stages:
   a) QUESTION: Open with the pain point phrased as a simple, respectful question.
      - Extremely simple language. Matter-of-fact tone. Under 15 words.
      - NEVER use words like "struggle", "challenge", "difficult", "hard" — these are condescending.
      - Pattern: "Would you be interested in X?" NOT "Are you struggling with X?"
   b) PRODUCT PITCH: Immediately after the question, transition into explaining the product/service that resolves this pain point. Reference the exact product name. Keep it 2-3 sentences.
   c) DISARMING: Weave in credibility proof points (achievements, partnerships, facts, growth metrics) to preemptively handle objections. This should feel like natural conversation, not a list of achievements. Only use proof points explicitly provided — never fabricate.
   d) URGENCY: Close this section with an ambition-oriented urgency statement. Signal demand, standards, momentum, selectivity. Never use fear, fake scarcity, or false claims. End with a clear call to action.

   Then flow naturally into the next pain point's question.

   CRITICAL RULES for the script:
   - ABSOLUTELY NO BULLET POINTS. No dashes, no numbered lists, no "•" characters. Write in flowing paragraphs only.
   - Each pain point section should be separated by a blank line for readability.
   - The script should sound like a human conversation guide, not a template.
   - Use simple, warm language. Sound like someone who genuinely cares.
   - The entire script should be one continuous piece of text that a rep can follow top to bottom.

4. WHATSAPP MESSAGES:
   Generate 3 separate WhatsApp messages, one for each pain point. Each message is self-contained and covers:
   - Friendly, personalized opening mentioning the prospect's business name
   - The specific pain point presented as a natural observation or question
   - The product/service that addresses it
   - Credibility proof points woven in naturally (achievements, partnerships, facts, growth metrics)
   - An urgency statement
   - A clear CTA (call to action)
   - Our website and/or Instagram for credibility (if provided)

   Rules for each WhatsApp message:
   - Under 150 words
   - Written in normal paragraph form (NO bullets)
   - Sounds human and warm, not templated or robotic
   - Focuses ONLY on its specific pain point
   - Only use proof points explicitly provided — never fabricate

Respond ONLY with valid JSON in this exact format:
{{
    "business_summary": "2-3 sentence summary of the prospect's business",
    "sales_script": "The complete flowing sales call script covering all 3 pain points. No bullet points. Flowing paragraphs separated by blank lines.",
    "whatsapp_messages": [
        {{
            "label": "Short pain point label (max 4 words)",
            "message": "Complete WhatsApp message for pain point 1..."
        }},
        {{
            "label": "Short pain point label (max 4 words)",
            "message": "Complete WhatsApp message for pain point 2..."
        }},
        {{
            "label": "Short pain point label (max 4 words)",
            "message": "Complete WhatsApp message for pain point 3..."
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

            script_data = {
                "type": "unified_script",
                "sales_script": result.get("sales_script", ""),
                "whatsapp_messages": result.get("whatsapp_messages", [])[:3]
            }

            return business_summary, script_data

        except Exception as e:
            print(f"Error generating AI insights: {e}")
            return "", {}

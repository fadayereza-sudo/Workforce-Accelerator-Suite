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
        credibility_facts: Optional[str] = None
    ) -> tuple[str, list]:
        """
        Generate business summary and complete sales toolkit for a prospect.

        Each pain point gets a full toolkit: question, opposition analysis,
        disarming key points, urgency statement, and WhatsApp message.

        Args:
            business_name: Name of the business
            business_address: Business address (optional)
            business_website: Business website (optional)
            products: List of organization's products/services
            business_description: Pre-extracted description from website (optional)
            org_website: Organization's website URL (optional)
            org_instagram: Organization's Instagram handle/URL (optional)
            credibility_facts: Partnerships, awards, stats for credibility (optional)

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

        # Build org credibility context
        org_context_parts = []
        if org_website:
            org_context_parts.append(f"- Website: {org_website}")
        if org_instagram:
            org_context_parts.append(f"- Instagram: {org_instagram}")
        if credibility_facts:
            org_context_parts.append(f"- Credibility & achievements: {credibility_facts}")
        org_context = "\n".join(org_context_parts) if org_context_parts else "No company info provided."

        prompt = f"""Analyze this business prospect and generate a complete sales toolkit.

PROSPECT INFORMATION:
- Business Name: {business_name}
- Address: {business_address or 'Unknown'}
- Website: {business_website or 'Unknown'}{description_context}

OUR PRODUCTS/SERVICES:
{products_context}

OUR COMPANY INFO:
{org_context}

TASKS:

1. BUSINESS SUMMARY: Write a 2-3 sentence summary of the prospect's business, their target market, and potential needs. If we have their website description, use that information. Be concise and focused.

2. SALES TOOLKIT: Identify the TOP 3 pain points this business is most likely facing that our products/services can solve. Rank them by REVENUE POTENTIAL for the prospect — the pain point that, if resolved, would bring the MOST revenue for their business should be ranked #1. Remember: sales is about helping people get what they want.

For EACH pain point, generate the following:

a) PAIN POINT: A short title (max 6 words) and 1-2 sentence description.

b) RELEVANT PRODUCT: Which of our products/services solves this. Use the exact product name or null.

c) SOLUTION SUMMARY: 1-2 sentences explaining how our product resolves this pain point. Reference specific product features.

d) QUESTION: Rephrase the pain point as a simple, non-condescending question to ask over the phone. Rules:
   - Invite their opinion. NEVER assume a problem or imply incompetence.
   - Sound like a person who genuinely cares, not a salesperson.
   - Make the value obvious so they think "of course I want that".
   - Under 15 words. Matter-of-fact. Simple. Open and inviting.
   - NEVER use words like "struggle", "challenge", "difficult", "hard" — these are condescending.

   EXAMPLE (for a sports club, pain point "hard to find talented players"):
   BAD: "Do you find it hard to identify sports talent in the UAE?" (implies incompetence)
   GOOD: "Would you guys be interested in taking on some extra players?" (inviting, simple, no judgment)

   ANOTHER EXAMPLE (pain point "difficulty tracking athlete progress"):
   BAD: "Are you struggling to track your athletes' progress?" (condescending)
   GOOD: "Would you guys be interested in learning more about your athletes' performance?" (inviting, respectful)

e) OPPOSITION STATEMENTS: Generate exactly 5 realistic opposition statements a prospect might have against the solution. These are the natural skeptical thoughts people have before accepting any offer (e.g. "it's probably too expensive", "sounds like a scam", "they're probably desperate for clients", "I doubt they can deliver", "waste of my time"). These are internal — the prospect won't say them out loud.

f) DISARMING KEY POINTS: For EACH opposition statement, write a disarming key point — a brief statement or approach that neutralises the concern. Examples:
   - "it's too expensive" → disarmed by pricing transparency and ROI framing
   - "sounds like a scam" → disarmed by mentioning partners, awards, credibility
   - "they're desperate" → disarmed by showing evidence of high demand
   - "can they deliver?" → disarmed by proof of past results
   - "waste of my time" → disarmed by being brief and using phrases like "I'm sure you're busy, I had a quick question…"

   Extract these as a bullet-point list of 3-5 concise key points for the sales rep to reference during the call. These are the talking points that naturally address concerns WITHOUT mentioning the opposition statements themselves.

g) URGENCY STATEMENT: Create an ambition-oriented urgency statement. This is NOT about false scarcity or fear tactics. It's about communicating: "our offer is so good that I can't guarantee it'll still be available if you don't act." The statement must:
   - Explain WHY the service is valuable and in-demand
   - Use real credibility facts if provided (partnerships, awards, demand)
   - Sound polite but confident — "we know our value"
   - End with a clear call to action
   - Feel genuine, not manufactured

   EXAMPLE: "Sportify Academy has recently partnered with Emirates Hospital Dubai to offer the sports talent identification test for free, so we've naturally experienced increased demand for this service from other sports clubs as well. If you are interested in our services, please let me know as soon as possible so we can book you into a session with one of our team."

h) WHATSAPP MESSAGE: Compose a professional WhatsApp message (under 150 words) that:
   - Opens with a friendly, personalized greeting mentioning their business name
   - Briefly states the opportunity (the pain point reframed positively)
   - Mentions 1-2 key selling points from the solution
   - Includes the urgency angle naturally
   - Ends with our website and/or Instagram for credibility (if provided)
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
                "concise talking point 3"
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
                        "content": (
                            "You are a B2B sales intelligence assistant that generates complete sales toolkits. "
                            "You identify business pain points ranked by revenue potential for the prospect and match them to solutions. "
                            "For call scripts, you help sales reps sound like someone who genuinely cares — not a salesperson. "
                            "You frame questions positively to invite opinion, never assuming problems or incompetence. "
                            "You understand opposition psychology: people have natural resistance to offers, and the way to "
                            "overcome that is through credibility, transparency, and genuine value — never manipulation. "
                            "Respond only with valid JSON."
                        )
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

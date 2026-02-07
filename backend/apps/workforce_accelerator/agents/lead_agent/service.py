"""
AI service for lead agent — generates business summaries and pain points using OpenAI GPT-4o.

This is the second tier of our two-tier LLM pipeline:
1. GPT-4o-mini (cheap) - Extract & summarize business info from HTML
2. GPT-4o (smart) - Generate insights & pain points with pattern recognition
"""
import json
from typing import List, Optional
from openai import AsyncOpenAI

from apps.workforce_accelerator.models import PainPoint, Product


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
        business_description: Optional[str] = None
    ) -> tuple[str, List[PainPoint], list]:
        """
        Generate business summary, pain points, and call script for a prospect.

        Returns:
            tuple: (business_summary, list_of_pain_points, call_script_items)
        """
        if products:
            products_context = "\n".join([
                f"- {p.name}: {p.description or 'No description'} "
                f"(Price: {p.price} per unit)" if p.price else f"- {p.name}: {p.description or 'No description'}"
                for p in products
            ])
        else:
            products_context = "No products defined yet."

        description_context = ""
        if business_description:
            description_context = f"\n- About: {business_description}"

        prompt = f"""You are a B2B sales intelligence assistant. Analyze this business prospect and generate insights.

PROSPECT INFORMATION:
- Business Name: {business_name}
- Address: {business_address or 'Unknown'}
- Website: {business_website or 'Unknown'}{description_context}

OUR PRODUCTS/SERVICES:
{products_context}

TASKS:
1. Generate a brief business summary (2-3 sentences) about what this business does, their target market, and potential needs. If we have their website description, use that information. Be concise and focused.

2. Identify the TOP 3 pain points this business might have that our products/services could solve. For each pain point:
   - Give it a short, clear title (max 6 words)
   - Explain the pain point in 1-2 sentences
   - If applicable, mention which of our products would help (use exact product name or null)

3. Create a CALL SCRIPT with 3 conversational Q&A's based on the pain points.

Each Q&A has 3 parts:
   a) YOUR OPENING QUESTION - Frame it positively, inviting their opinion. Never assume a problem or imply incompetence. Sound like you're asking a loved one their take on something. Keep it simple, straight to the point, and genuinely curious. The question should make them think "of course I want that, it's a no-brainer".
   b) THEIR EXPECTED RESPONSE - What the prospect will likely say back (a short, natural reply).
   c) OUR VALUE RESPONSE - How we deliver value in response. Reference our specific product/service. Keep it conversational and benefit-focused.

EXAMPLE (for a fitness club prospect, pain point: "hard to identify sports talent"):
   BAD question: "Do you find it hard to identify sports talent in the UAE?"
   (This implies they're not competent. People expect strangers to help them, not question them.)

   GOOD question: "Would you guys be interested in finding new players?"
   Their response: "Sure, what kind of players?"
   Our response: "We use rigorous testing methods to identify talented young players in Dubai and when we know which sport they are good at, we send them to you."

   WHY THIS WORKS: It doesn't sound salesy. It doesn't sound scripted. It sounds like something a person who cares about you would ask. It immediately brings down a person's guard and invites them to engage.

RULES FOR CALL SCRIPT:
- Never assume the person will run away - no emotionally sticky opening lines
- Questions should invite their opinion, not point out a weakness
- Frame questions so the value is obvious: "would you be interested in X?"
- Keep questions under 15 words
- Sound like a person who genuinely cares, not a salesperson

Respond ONLY with valid JSON in this exact format:
{{
    "business_summary": "...",
    "pain_points": [
        {{
            "title": "...",
            "description": "...",
            "relevant_product": "product name or null"
        }},
        {{
            "title": "...",
            "description": "...",
            "relevant_product": "product name or null"
        }},
        {{
            "title": "...",
            "description": "...",
            "relevant_product": "product name or null"
        }}
    ],
    "call_script": [
        {{
            "question": "Would you guys be interested in...?",
            "answer": "We use... to help you..."
        }},
        {{
            "question": "...",
            "answer": "..."
        }},
        {{
            "question": "...",
            "answer": "..."
        }}
    ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales intelligence assistant. You identify business pain points and match them to solutions. For call scripts, you help sales reps sound like someone who genuinely cares - not a salesperson. You frame questions positively to invite opinion, never assuming problems or incompetence. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1100
            )

            result = json.loads(response.choices[0].message.content)

            business_summary = result.get("business_summary", "")

            pain_points = []
            for pp in result.get("pain_points", [])[:3]:
                pain_points.append(PainPoint(
                    title=pp.get("title", ""),
                    description=pp.get("description", ""),
                    relevant_product=pp.get("relevant_product")
                ))

            call_script = result.get("call_script", [])[:3]

            return business_summary, pain_points, call_script

        except Exception as e:
            print(f"Error generating AI insights: {e}")
            return "", [], []

    async def generate_call_script(
        self,
        business_name: str,
        pain_points: list,
        products: List[Product]
    ) -> list:
        """
        Generate a conversational call script based on pain points.

        Returns:
            List of script items with question and answer
        """
        if not pain_points:
            return []

        if products:
            products_context = "\n".join([
                f"- {p.name}: {p.description or 'No description'}"
                for p in products
            ])
        else:
            products_context = "No products defined yet."

        pain_points_text = "\n".join([
            f"{i+1}. {pp.get('title', pp.title) if isinstance(pp, dict) else pp.title}: "
            f"{pp.get('description', pp.description) if isinstance(pp, dict) else pp.description}"
            for i, pp in enumerate(pain_points[:3])
        ])

        prompt = f"""Transform these pain points into a conversational call script for reaching out to a prospect.

PROSPECT: {business_name}

PAIN POINTS:
{pain_points_text}

OUR PRODUCTS/SERVICES:
{products_context}

TASK:
For each pain point, create a Q&A pair:

- QUESTION: Frame it positively, inviting their opinion. Never assume a problem or imply incompetence. Sound like you're asking a loved one their take on something. Make them think "of course I want that". Keep it under 15 words.

- ANSWER: How we deliver value. Reference our product/service. Keep it conversational (1-2 sentences).

EXAMPLE (pain point: "hard to identify sports talent"):
   BAD question: "Do you find it hard to identify sports talent?" (implies incompetence)
   GOOD question: "Would you guys be interested in finding new players?"
   Answer: "We use rigorous testing methods to identify talented young players in Dubai and when we know which sport they're good at, we send them to you."

RULES:
- Never assume the person will run away
- Questions invite opinion, not point out weakness
- Simple and straight to the point
- Sound like someone who genuinely cares, not a salesperson

Respond ONLY with valid JSON:
{{
    "script_items": [
        {{
            "question": "Would you guys be interested in...?",
            "answer": "We use... to help you..."
        }},
        {{
            "question": "...",
            "answer": "..."
        }},
        {{
            "question": "...",
            "answer": "..."
        }}
    ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales coach. You help reps sound like someone who genuinely cares - not a salesperson. You frame questions positively to invite opinion, never assuming problems. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
                max_tokens=700
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("script_items", [])

        except Exception as e:
            print(f"Error generating call script: {e}")
            return []

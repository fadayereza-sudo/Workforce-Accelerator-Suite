"""
AI service for lead agent - generates business summaries and pain points using OpenAI.
"""
import json
from typing import List, Optional
from openai import AsyncOpenAI

from models.lead_agent import PainPoint, Product


class LeadAgentAI:
    """AI-powered lead analysis using OpenAI GPT."""

    def __init__(self, api_key: str):
        """Initialize with OpenAI API key."""
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_prospect_insights(
        self,
        business_name: str,
        business_address: Optional[str],
        business_website: Optional[str],
        products: List[Product]
    ) -> tuple[str, List[PainPoint]]:
        """
        Generate business summary and pain points for a prospect.

        Args:
            business_name: Name of the business
            business_address: Business address (optional)
            business_website: Business website (optional)
            products: List of organization's products/services

        Returns:
            tuple: (business_summary, list_of_pain_points)
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

        prompt = f"""You are a B2B sales intelligence assistant. Analyze this business prospect and generate insights.

PROSPECT INFORMATION:
- Business Name: {business_name}
- Address: {business_address or 'Unknown'}
- Website: {business_website or 'Unknown'}

OUR PRODUCTS/SERVICES:
{products_context}

TASKS:
1. Generate a brief business summary (2-3 sentences) about what this business likely does, their target market, and potential needs. Be concise and focused.

2. Identify the TOP 3 pain points this business might have that our products/services could solve. For each pain point:
   - Give it a short, clear title (max 6 words)
   - Explain the pain point in 1-2 sentences
   - If applicable, mention which of our products would help (use exact product name or null)

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
    ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective for this use case
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales intelligence assistant. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=500
            )

            result = json.loads(response.choices[0].message.content)

            # Extract and validate data
            business_summary = result.get("business_summary", "")

            pain_points = []
            for pp in result.get("pain_points", [])[:3]:
                pain_points.append(PainPoint(
                    title=pp.get("title", ""),
                    description=pp.get("description", ""),
                    relevant_product=pp.get("relevant_product")
                ))

            return business_summary, pain_points

        except Exception as e:
            print(f"Error generating AI insights: {e}")
            # Return empty fallback
            return "", []

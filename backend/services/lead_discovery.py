"""
Lead discovery service using Google Gemini with Search Grounding.
"""
import json
import hashlib
from typing import List, Optional
from dataclasses import dataclass

import google.generativeai as genai


@dataclass
class ScrapedBusiness:
    """Business information scraped via Gemini search grounding."""
    business_name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    website: Optional[str]
    google_maps_url: Optional[str]

    def get_dedup_hash(self) -> str:
        """
        Generate hash for deduplication.
        Uses business_name + phone/address as unique identifier.
        """
        phone_part = self.phone or ""
        address_part = self.address or ""
        key = f"{self.business_name.lower().strip()}:{phone_part}:{address_part}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]


class LeadDiscoveryService:
    """
    Lead discovery using Google Gemini 2.0 Flash with Search Grounding.

    Instead of manual web scraping, this service leverages Gemini's real-time
    access to Google Search to find businesses, extract contact details, and
    return structured data.
    """

    def __init__(self, api_key: str):
        """Initialize the service with Gemini API key."""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            tools="google_search_retrieval"
        )

    async def search_businesses(
        self,
        query: str,
        max_results: int = 10
    ) -> List[ScrapedBusiness]:
        """
        Search for businesses using Gemini with Google Search grounding.

        Args:
            query: Search query (e.g., "basketball clubs in dubai")
            max_results: Maximum number of results to return (default 10)

        Returns:
            List of ScrapedBusiness objects with extracted contact information
        """
        prompt = f"""Find up to {max_results} businesses matching this search query: "{query}"

For each business, extract the following information:
- Business Name
- Phone Number (if available)
- Email Address (if available)
- Physical Address (if available)
- Website URL (if available)
- Google Maps URL (if available)

Return the results as a JSON array with this exact structure:
{{
    "businesses": [
        {{
            "business_name": "Example Business",
            "phone": "+1234567890",
            "email": "contact@example.com",
            "address": "123 Main St, City, Country",
            "website": "https://example.com",
            "google_maps_url": "https://maps.google.com/..."
        }}
    ]
}}

Important:
- Use null for fields that are not available
- Ensure phone numbers are in international format when possible
- Include complete addresses with city and country
- Return actual businesses, not directories or listing sites
- Focus on real, operational businesses"""

        try:
            # Generate content with search grounding
            response = self.model.generate_content(prompt)

            # Parse the JSON response
            response_text = response.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            data = json.loads(response_text)

            # Convert to ScrapedBusiness objects
            businesses = []
            for item in data.get("businesses", [])[:max_results]:
                businesses.append(ScrapedBusiness(
                    business_name=item.get("business_name", ""),
                    phone=item.get("phone"),
                    email=item.get("email"),
                    address=item.get("address"),
                    website=item.get("website"),
                    google_maps_url=item.get("google_maps_url")
                ))

            return businesses

        except json.JSONDecodeError as e:
            # Fallback: try to extract structured data from text
            print(f"JSON parse error: {e}")
            print(f"Response text: {response_text}")
            return []
        except Exception as e:
            print(f"Error during lead discovery: {e}")
            return []

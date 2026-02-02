"""
Lead discovery service using Google Gemini 2.0 Flash with Search Grounding.
"""
import json
import hashlib
from typing import List, Optional
from dataclasses import dataclass

from google import genai
from google.genai import types


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

    This service leverages Gemini's real-time access to Google Search
    to find businesses, extract contact details, and return structured data.
    """

    def __init__(self, api_key: str):
        """Initialize the service with Gemini API key."""
        self.client = genai.Client(api_key=api_key)

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
        # Use "Search for:" pattern to trigger search grounding
        prompt = f"""Search for: {query}

Find up to {max_results} real businesses matching this search query.

For each business found, extract:
- Business Name
- Phone Number (in international format if available)
- Email Address (if available)
- Physical Address (complete with city and country)
- Website URL (if available)
- Google Maps URL (if available)

Return ONLY a valid JSON object with this exact structure:
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

Rules:
- Use null for fields that are not available
- Return ONLY real, existing businesses found in search results
- Do not invent or fabricate any business information
- Do not include directory sites or listing aggregators
- Return raw JSON only, no markdown formatting"""

        try:
            # Generate content with Google Search grounding enabled
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )

            # Parse the JSON response
            response_text = response.text.strip()
            print(f"[LeadDiscovery] Raw response: {response_text[:500]}...")

            # Extract JSON from markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            data = json.loads(response_text)

            # Convert to ScrapedBusiness objects
            businesses = []
            for item in data.get("businesses", [])[:max_results]:
                business = ScrapedBusiness(
                    business_name=item.get("business_name", ""),
                    phone=item.get("phone"),
                    email=item.get("email"),
                    address=item.get("address"),
                    website=item.get("website"),
                    google_maps_url=item.get("google_maps_url")
                )
                if business.business_name:  # Only add if we have a name
                    businesses.append(business)

            print(f"[LeadDiscovery] Found {len(businesses)} businesses")
            return businesses

        except json.JSONDecodeError as e:
            print(f"[LeadDiscovery] JSON parse error: {e}")
            print(f"[LeadDiscovery] Response text: {response_text}")
            return []
        except Exception as e:
            print(f"[LeadDiscovery] Error during lead discovery: {e}")
            return []

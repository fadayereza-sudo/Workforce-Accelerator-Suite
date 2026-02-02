"""
URL scraper service using OpenAI GPT-4o-mini for extraction.

This is the first tier of our two-tier LLM pipeline:
1. GPT-4o-mini (cheap) - Extract & summarize business info from HTML
2. GPT-4o (smart) - Generate insights & pain points with pattern recognition
"""
import json
import hashlib
from typing import Optional
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI


@dataclass
class ExtractedBusiness:
    """Business information extracted from a website."""
    business_name: str
    description: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    website: str
    google_maps_url: Optional[str]

    def get_dedup_hash(self) -> str:
        """
        Generate hash for deduplication.
        Uses business_name + website as unique identifier.
        """
        key = f"{self.business_name.lower().strip()}:{self.website.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]


class URLScraperService:
    """
    URL scraper using OpenAI GPT-4o-mini for business info extraction.

    This service:
    1. Fetches the HTML content from a given URL
    2. Uses GPT-4o-mini to extract & summarize structured business information
    3. Returns the data in a format ready for AI insights generation
    """

    def __init__(self, api_key: str):
        """Initialize the service with OpenAI API key."""
        self.client = AsyncOpenAI(api_key=api_key)

    async def scrape_business(self, url: str) -> Optional[ExtractedBusiness]:
        """
        Scrape business information from a URL.

        Args:
            url: The website URL to scrape

        Returns:
            ExtractedBusiness object or None if extraction fails
        """
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        # Step 1: Fetch HTML content
        html_content = await self._fetch_html(url)
        if not html_content:
            return None

        # Step 2: Extract business info using GPT-4o-mini
        business = await self._extract_with_openai(url, html_content)
        return business

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL."""
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Get text content, limit to first 50KB to avoid huge pages
                content = response.text[:50000]
                print(f"[URLScraper] Fetched {len(content)} chars from {url}")
                return content

        except httpx.HTTPStatusError as e:
            print(f"[URLScraper] HTTP error fetching {url}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            print(f"[URLScraper] Request error fetching {url}: {e}")
            return None
        except Exception as e:
            print(f"[URLScraper] Error fetching {url}: {e}")
            return None

    async def _extract_with_openai(
        self,
        url: str,
        html_content: str
    ) -> Optional[ExtractedBusiness]:
        """Extract business information from HTML using GPT-4o-mini."""

        # Clean up HTML to reduce tokens
        import re
        cleaned = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)  # Remove HTML tags
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Collapse whitespace
        cleaned = cleaned[:20000]  # Limit to 20K chars

        prompt = f"""You are extracting business information from a website.

URL: {url}

WEBSITE CONTENT:
{cleaned}

Extract the following information about this business. Be accurate - only extract what is actually present on the page.

Return ONLY valid JSON in this exact format:
{{
    "business_name": "The company/business name",
    "description": "A 2-3 sentence description of what the business does, their services, and target market",
    "phone": "Phone number in international format if found, or null",
    "email": "Contact email if found, or null",
    "address": "Physical address if found, or null",
    "google_maps_url": "Google Maps link if found on page, or null"
}}

Rules:
- Extract the actual business name, not the website domain
- For description, summarize what the business does based on the content
- Use null for any field you cannot find
- Phone should be in international format if possible (e.g., +1 234 567 8900)
- Return raw JSON only, no markdown formatting"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a business information extraction assistant. Extract data accurately from website content and return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            # Parse the JSON response
            response_text = response.choices[0].message.content.strip()
            print(f"[URLScraper] GPT-4o-mini response: {response_text[:300]}...")

            data = json.loads(response_text)

            # Build ExtractedBusiness
            business = ExtractedBusiness(
                business_name=data.get("business_name", "Unknown Business"),
                description=data.get("description"),
                phone=data.get("phone"),
                email=data.get("email"),
                address=data.get("address"),
                website=url,
                google_maps_url=data.get("google_maps_url")
            )

            print(f"[URLScraper] Extracted: {business.business_name}")
            return business

        except json.JSONDecodeError as e:
            print(f"[URLScraper] JSON parse error: {e}")
            print(f"[URLScraper] Response text: {response_text}")
            return None
        except Exception as e:
            print(f"[URLScraper] Error during extraction: {e}")
            return None

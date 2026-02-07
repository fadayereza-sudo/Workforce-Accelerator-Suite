"""
URL scraper service using Groq Llama 3.1 8B for extraction.

This is the first tier of our two-tier LLM pipeline:
1. Llama 3.1 8B via Groq (cheap & fast) - Extract & summarize business info from HTML
2. GPT-4o (smart) - Generate insights & pain points with pattern recognition
"""
import json
import hashlib
from typing import Optional, Tuple
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI


class ScraperError(Exception):
    """Custom exception for scraper errors with user-friendly messages."""
    def __init__(self, message: str, technical_detail: str = None):
        self.message = message
        self.technical_detail = technical_detail
        super().__init__(message)


@dataclass
class ExtractedBusiness:
    """Business information extracted from a website."""
    business_name: str
    description: Optional[str]
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
    URL scraper using Groq Llama 3.1 8B for business info extraction.

    This service:
    1. Fetches the HTML content from a given URL
    2. Uses Llama 3.1 8B via Groq to extract & summarize structured business information
    3. Returns the data in a format ready for AI insights generation
    """

    def __init__(self, groq_api_key: str):
        """Initialize the service with Groq API key."""
        self.client = AsyncOpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    async def scrape_business(self, url: str) -> ExtractedBusiness:
        """
        Scrape business information from a URL.

        Args:
            url: The website URL to scrape

        Returns:
            ExtractedBusiness object

        Raises:
            ScraperError: If scraping or extraction fails
        """
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        # Step 1: Fetch HTML content
        html_content = await self._fetch_html(url)

        # Step 2: Extract business info using Llama 3.1 8B via Groq
        business = await self._extract_with_llm(url, html_content)
        return business

    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL.

        Raises:
            ScraperError: If fetching fails
        """
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

                # Check if we got meaningful content
                if len(content.strip()) < 100:
                    raise ScraperError(
                        "The website returned insufficient content. It may require JavaScript or have blocked access.",
                        f"Content length: {len(content)}"
                    )

                return content

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            print(f"[URLScraper] HTTP error fetching {url}: {status_code}")

            # Provide user-friendly error messages based on status code
            if status_code == 403:
                raise ScraperError(
                    "This website is blocking automated access (Cloudflare protection detected). Please add this lead manually with the business information you have.",
                    f"HTTP 403 from {url}"
                )
            elif status_code == 404:
                raise ScraperError(
                    "Page not found. Please check the URL and try again.",
                    f"HTTP 404 from {url}"
                )
            elif status_code == 500:
                raise ScraperError(
                    "The website's server returned an error. Please try again later.",
                    f"HTTP 500 from {url}"
                )
            elif status_code == 429:
                raise ScraperError(
                    "Rate limit exceeded. The website is temporarily blocking requests. Please try again later.",
                    f"HTTP 429 from {url}"
                )
            else:
                raise ScraperError(
                    f"Unable to access the website (HTTP {status_code}). Please check the URL and try again.",
                    f"HTTP {status_code} from {url}"
                )

        except httpx.TimeoutException as e:
            print(f"[URLScraper] Timeout fetching {url}: {e}")
            raise ScraperError(
                "The website took too long to respond. Please try again or check if the URL is correct.",
                f"Timeout connecting to {url}"
            )

        except httpx.RequestError as e:
            print(f"[URLScraper] Request error fetching {url}: {e}")
            raise ScraperError(
                "Unable to connect to the website. Please check the URL and your internet connection.",
                f"Connection error: {str(e)}"
            )

        except ScraperError:
            # Re-raise ScraperError as-is
            raise

        except Exception as e:
            print(f"[URLScraper] Unexpected error fetching {url}: {e}")
            raise ScraperError(
                "An unexpected error occurred while fetching the website. Please try again.",
                f"Unexpected error: {str(e)}"
            )

    async def _extract_with_llm(
        self,
        url: str,
        html_content: str
    ) -> ExtractedBusiness:
        """
        Extract business information from HTML using Llama 3.1 8B via Groq.

        Raises:
            ScraperError: If extraction fails
        """

        # Clean up HTML to reduce tokens
        import re
        cleaned = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)  # Remove HTML tags
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Collapse whitespace
        cleaned = cleaned[:20000]  # Limit to 20K chars

        # Check if cleaned content is meaningful
        if len(cleaned.strip()) < 50:
            raise ScraperError(
                "Unable to extract meaningful content from the page. The website might be JavaScript-heavy or blocked.",
                f"Cleaned content too short: {len(cleaned)} chars"
            )

        prompt = f"""You are extracting business information from a website.

URL: {url}

WEBSITE CONTENT:
{cleaned}

Extract the following information about this business. Be accurate - only extract what is actually present on the page.

Return ONLY valid JSON in this exact format:
{{
    "business_name": "The company/business name",
    "description": "A 2-3 sentence description of what the business does, their services, and target market",
    "address": "Physical address if found, or null",
    "google_maps_url": "Google Maps link if found on page, or null"
}}

Rules:
- Extract the actual business name, not the website domain
- For description, summarize what the business does based on the content
- Use null for any field you cannot find
- For ADDRESS: Look for physical addresses, office locations, or mailing addresses
- Return raw JSON only, no markdown formatting"""

        try:
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
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
            print(f"[URLScraper] Groq/Llama response: {response_text[:300]}...")

            data = json.loads(response_text)

            # Validate that we got at least a business name
            business_name = data.get("business_name", "").strip()
            if not business_name or business_name == "Unknown Business":
                raise ScraperError(
                    "Could not identify the business name from the website content. The page might not contain sufficient business information.",
                    f"No valid business_name in response"
                )

            # Build ExtractedBusiness
            business = ExtractedBusiness(
                business_name=business_name,
                description=data.get("description"),
                address=data.get("address"),
                website=url,
                google_maps_url=data.get("google_maps_url")
            )

            print(f"[URLScraper] Extracted: {business.business_name}")
            return business

        except json.JSONDecodeError as e:
            print(f"[URLScraper] JSON parse error: {e}")
            print(f"[URLScraper] Response text: {response_text if 'response_text' in locals() else 'N/A'}")
            raise ScraperError(
                "Failed to parse business information from the website. The AI returned invalid data.",
                f"JSON decode error: {str(e)}"
            )

        except ScraperError:
            # Re-raise ScraperError as-is
            raise

        except Exception as e:
            print(f"[URLScraper] Error during extraction: {e}")
            raise ScraperError(
                "An error occurred while analyzing the website content. Please try again.",
                f"Extraction error: {str(e)}"
            )

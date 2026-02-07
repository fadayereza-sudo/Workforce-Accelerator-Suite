"""
URL scraper service using OpenAI GPT-4o-mini for extraction.

This is the first tier of our two-tier LLM pipeline:
1. GPT-4o-mini (cheap) - Extract & summarize business info from HTML
2. GPT-4o (smart) - Generate insights & pain points with pattern recognition

Fetching strategy: direct httpx first (fast), Jina Reader API fallback
(handles JS rendering + anti-bot bypass).
"""
import json
import hashlib
from typing import Optional
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
        """Generate hash for deduplication."""
        key = f"{self.business_name.lower().strip()}:{self.website.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]


class URLScraperService:
    """URL scraper using OpenAI GPT-4o-mini for business info extraction."""

    def __init__(self, api_key: str, jina_api_key: str = ""):
        self.client = AsyncOpenAI(api_key=api_key)
        self.jina_api_key = jina_api_key

    async def scrape_business(self, url: str) -> ExtractedBusiness:
        """Scrape business information from a URL."""
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        content = await self._fetch_content(url)
        business = await self._extract_with_openai(url, content)
        return business

    async def _fetch_content(self, url: str) -> str:
        """Fetch page content — direct fetch first, Jina Reader fallback."""
        direct_error = None

        # Try direct fetch first (fast, no rate limits)
        try:
            content = await self._fetch_direct(url)
            if content:
                return content
        except ScraperError as e:
            # 404 is a real URL problem — don't retry with Jina
            if "404" in (e.technical_detail or ""):
                raise
            direct_error = e
            print(f"[URLScraper] Direct fetch failed: {e.technical_detail}")

        # Fallback to Jina Reader (handles JS + anti-bot)
        print(f"[URLScraper] Trying Jina Reader fallback for {url}")
        try:
            content = await self._fetch_with_jina(url)
            if content:
                print(f"[URLScraper] Jina Reader succeeded: {len(content)} chars")
                return content
        except Exception as e:
            print(f"[URLScraper] Jina Reader also failed: {e}")

        # Both failed — raise the original direct error or a generic one
        if direct_error:
            raise direct_error
        raise ScraperError(
            "Unable to fetch content from this website. Please add this lead manually.",
            f"Both direct fetch and Jina Reader failed for {url}"
        )

    async def _fetch_direct(self, url: str) -> Optional[str]:
        """Fetch HTML content directly via httpx."""
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

                content = response.text[:50000]
                print(f"[URLScraper] Direct fetch: {len(content)} chars from {url}")

                if len(content.strip()) < 100:
                    raise ScraperError(
                        "The website returned insufficient content. It may require JavaScript or have blocked access.",
                        f"Content length: {len(content)}"
                    )

                return content

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            print(f"[URLScraper] HTTP error fetching {url}: {status_code}")

            if status_code == 403:
                raise ScraperError(
                    "This website is blocking automated access.",
                    f"HTTP 403 from {url}"
                )
            elif status_code == 404:
                raise ScraperError(
                    "Page not found. Please check the URL and try again.",
                    f"HTTP 404 from {url}"
                )
            elif status_code == 500:
                raise ScraperError(
                    "The website's server returned an error.",
                    f"HTTP 500 from {url}"
                )
            elif status_code == 429:
                raise ScraperError(
                    "The website is temporarily blocking requests.",
                    f"HTTP 429 from {url}"
                )
            else:
                raise ScraperError(
                    f"Unable to access the website (HTTP {status_code}).",
                    f"HTTP {status_code} from {url}"
                )

        except httpx.TimeoutException:
            raise ScraperError(
                "The website took too long to respond.",
                f"Timeout connecting to {url}"
            )

        except httpx.RequestError as e:
            raise ScraperError(
                "Unable to connect to the website.",
                f"Connection error: {str(e)}"
            )

        except ScraperError:
            raise

        except Exception as e:
            raise ScraperError(
                "An unexpected error occurred while fetching the website.",
                f"Unexpected error: {str(e)}"
            )

    async def _fetch_with_jina(self, url: str) -> Optional[str]:
        """Fetch page content via Jina Reader API (JS rendering + anti-bot)."""
        headers = {
            "Accept": "application/json",
            "X-Return-Format": "markdown",
            "X-Retain-Images": "none",
        }
        if self.jina_api_key:
            headers["Authorization"] = f"Bearer {self.jina_api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"https://r.jina.ai/{url}",
                headers=headers
            )
            response.raise_for_status()

            try:
                data = response.json()
                content = data.get("data", {}).get("content", "")
            except (json.JSONDecodeError, AttributeError):
                content = response.text

            if not content or len(content.strip()) < 50:
                return None

            return content[:20000]

    async def _extract_with_openai(self, url: str, content: str) -> ExtractedBusiness:
        """Extract business information from page content using GPT-4o-mini."""
        import re
        cleaned = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned[:20000]

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
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a business information extraction assistant. Extract data accurately from website content and return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            response_text = response.choices[0].message.content.strip()
            print(f"[URLScraper] GPT-4o-mini response: {response_text[:300]}...")

            data = json.loads(response_text)

            business_name = data.get("business_name", "").strip()
            if not business_name or business_name == "Unknown Business":
                raise ScraperError(
                    "Could not identify the business name from the website content. The page might not contain sufficient business information.",
                    f"No valid business_name in response"
                )

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
            raise ScraperError(
                "Failed to parse business information from the website. The AI returned invalid data.",
                f"JSON decode error: {str(e)}"
            )

        except ScraperError:
            raise

        except Exception as e:
            print(f"[URLScraper] Error during extraction: {e}")
            raise ScraperError(
                "An error occurred while analyzing the website content. Please try again.",
                f"Extraction error: {str(e)}"
            )

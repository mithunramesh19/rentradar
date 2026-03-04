"""Rent.com scraper — extracts listing data from __NEXT_DATA__ JSON."""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import BaseScraper, RawListing, SourceConfig
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

RENTCOM_URL = "https://www.rent.com/new-york-ny/apartments"
NEXT_DATA_RE = re.compile(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', re.DOTALL)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]


def extract_next_data(html: str) -> dict[str, Any]:
    """Extract __NEXT_DATA__ JSON from page HTML."""
    match = NEXT_DATA_RE.search(html)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("Failed to parse __NEXT_DATA__ JSON")
        return {}


class RentComScraper(BaseScraper):
    """Rent.com scraper using __NEXT_DATA__ embedded JSON."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.RENTCOM,
                base_url=RENTCOM_URL,
                rate_limit_seconds=3.0,
                max_pages=10,
                timeout_seconds=20,
            )
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def scrape(self) -> list[RawListing]:
        """Scrape Rent.com search pages."""
        all_listings: list[RawListing] = []

        for page in range(1, self.config.max_pages + 1):
            self.throttle()
            url = f"{self.config.base_url}?page={page}" if page > 1 else self.config.base_url
            try:
                resp = self._session.get(url, timeout=self.config.timeout_seconds)
                resp.raise_for_status()
            except requests.RequestException:
                self.logger.exception("Failed to fetch Rent.com page %d", page)
                break

            page_listings = self.parse_listing_page(resp.text)
            if not page_listings:
                break
            all_listings.extend(page_listings)
            self.logger.info("Page %d: %d listings (total %d)", page, len(page_listings), len(all_listings))

        return all_listings

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse listings from __NEXT_DATA__ JSON in page HTML."""
        data = extract_next_data(html)
        if not data:
            return []

        listings: list[RawListing] = []

        # Navigate the Next.js page props structure
        props = data.get("props", {}).get("pageProps", {})

        # Try common Rent.com data paths
        search_results = (
            props.get("listings", [])
            or props.get("searchResults", {}).get("listings", [])
            or props.get("properties", [])
        )

        for item in search_results:
            try:
                listings.append(self._parse_listing_item(item))
            except Exception:
                self.logger.debug("Failed to parse Rent.com listing item", exc_info=True)

        return listings

    def parse_listing_detail(self, html: str, url: str) -> RawListing:
        """Parse Rent.com detail page from __NEXT_DATA__."""
        data = extract_next_data(html)
        if not data:
            return RawListing(source=ListingSource.RENTCOM, source_url=url)

        props = data.get("props", {}).get("pageProps", {})
        listing = props.get("listing", {}) or props.get("property", {})

        address_parts = [
            listing.get("address", ""),
            listing.get("city", ""),
            listing.get("state", ""),
        ]
        address = ", ".join(p for p in address_parts if p)

        return RawListing(
            source=ListingSource.RENTCOM,
            source_url=url,
            title=listing.get("name", ""),
            address=address,
            price=str(listing.get("rent", {}).get("min", "")) if isinstance(listing.get("rent"), dict) else str(listing.get("rent", "")),
            bedrooms=str(listing.get("beds", {}).get("min", "")) if isinstance(listing.get("beds"), dict) else str(listing.get("beds", "")),
            bathrooms=str(listing.get("baths", {}).get("min", "")) if isinstance(listing.get("baths"), dict) else str(listing.get("baths", "")),
            neighborhood=listing.get("neighborhood", ""),
            description=listing.get("description", ""),
            image_urls=[img.get("url", "") for img in listing.get("images", []) if img.get("url")],
            detail_data={
                "lat": listing.get("latitude"),
                "lng": listing.get("longitude"),
                "amenities": listing.get("amenities", []),
            },
        )

    def _parse_listing_item(self, item: dict[str, Any]) -> RawListing:
        """Parse a single listing from the search results JSON."""
        address_parts = [
            item.get("address", ""),
            item.get("city", ""),
            item.get("state", ""),
        ]
        address = ", ".join(p for p in address_parts if p)

        # Handle rent as dict {min, max} or scalar
        rent = item.get("rent", item.get("price", ""))
        if isinstance(rent, dict):
            price_str = str(rent.get("min", ""))
        else:
            price_str = str(rent) if rent else ""

        beds = item.get("beds", item.get("bedrooms", ""))
        if isinstance(beds, dict):
            beds = str(beds.get("min", ""))
        else:
            beds = str(beds) if beds else ""

        baths = item.get("baths", item.get("bathrooms", ""))
        if isinstance(baths, dict):
            baths = str(baths.get("min", ""))
        else:
            baths = str(baths) if baths else ""

        detail_url = item.get("url", item.get("detailUrl", ""))
        if detail_url and not detail_url.startswith("http"):
            detail_url = f"https://www.rent.com{detail_url}"

        photos = item.get("images", item.get("photos", []))
        image_urls = [p.get("url", p) if isinstance(p, dict) else str(p) for p in photos[:5]]

        return RawListing(
            source=ListingSource.RENTCOM,
            source_url=detail_url,
            title=item.get("name", item.get("title", "")),
            address=address,
            price=f"${price_str}" if price_str and not price_str.startswith("$") else price_str,
            bedrooms=beds,
            bathrooms=baths,
            neighborhood=item.get("neighborhood", ""),
            image_urls=image_urls,
            detail_data={
                "lat": item.get("latitude"),
                "lng": item.get("longitude"),
            },
        )


register_scraper(ListingSource.RENTCOM, RentComScraper)

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
from rentradar_workers.scrapers.base import (
    BaseScraper,
    RawListing,
    SourceConfig,
    parse_float,
    parse_int,
)
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

RENTCOM_URL = "https://www.rent.com/new-york-ny/apartments"
NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', re.DOTALL
)

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


def _extract_scalar_or_min(val: Any) -> int | None:
    """Extract int from scalar or dict with 'min' key."""
    if val is None:
        return None
    if isinstance(val, dict):
        return parse_int(val.get("min"))
    return parse_int(val)


class RentComScraper(BaseScraper):
    """Rent.com scraper using __NEXT_DATA__ embedded JSON."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.RENTCOM,
                base_url=RENTCOM_URL,
                scrape_interval_hours=8,
                max_pages=10,
                request_delay_range=(3.0, 5.0),
            )
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    async def scrape(self, borough: str | None = None) -> list[RawListing]:
        """Scrape Rent.com search pages."""
        all_listings: list[RawListing] = []

        for page in range(1, self.config.max_pages + 1):
            self._rate_limit()
            url = (
                f"{self.config.base_url}?page={page}"
                if page > 1
                else self.config.base_url
            )
            try:
                resp = self._session.get(url, timeout=20)
                resp.raise_for_status()
            except requests.RequestException:
                self.logger.exception("Failed to fetch Rent.com page %d", page)
                break

            page_listings = self.parse_listing_page(resp.text)
            if not page_listings:
                break
            all_listings.extend(page_listings)
            self.logger.info(
                "Page %d: %d listings (total %d)",
                page,
                len(page_listings),
                len(all_listings),
            )

        return all_listings

    def parse_listing(self, raw: Any) -> RawListing:
        """Parse a single listing dict from __NEXT_DATA__ search results."""
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict, got {type(raw)}")
        return self._parse_listing_item(raw)

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse listings from __NEXT_DATA__ JSON in page HTML (for tests/offline)."""
        data = extract_next_data(html)
        if not data:
            return []

        listings: list[RawListing] = []
        props = data.get("props", {}).get("pageProps", {})
        search_results = (
            props.get("listings", [])
            or props.get("searchResults", {}).get("listings", [])
            or props.get("properties", [])
        )

        for item in search_results:
            try:
                listings.append(self.parse_listing(item))
            except Exception:
                self.logger.debug("Failed to parse Rent.com listing item", exc_info=True)

        return listings

    def _parse_listing_item(self, item: dict[str, Any]) -> RawListing:
        """Parse a single listing from the search results JSON."""
        address_parts = [
            item.get("address", ""),
            item.get("city", ""),
            item.get("state", ""),
        ]
        address = ", ".join(p for p in address_parts if p)

        price = _extract_scalar_or_min(item.get("rent", item.get("price")))
        beds = _extract_scalar_or_min(item.get("beds", item.get("bedrooms")))

        baths_raw = item.get("baths", item.get("bathrooms"))
        if isinstance(baths_raw, dict):
            baths = parse_float(baths_raw.get("min"))
        else:
            baths = parse_float(baths_raw)

        detail_url = item.get("url", item.get("detailUrl", ""))
        if detail_url and not detail_url.startswith("http"):
            detail_url = f"https://www.rent.com{detail_url}"

        photos = item.get("images", item.get("photos", []))
        image_urls = [
            p.get("url", p) if isinstance(p, dict) else str(p) for p in photos[:5]
        ]

        return RawListing(
            source=ListingSource.RENTCOM,
            source_url=detail_url,
            address=address,
            price=price,
            bedrooms=beds,
            bathrooms=baths,
            images=image_urls,
            raw_data={
                "name": item.get("name", ""),
                "neighborhood": item.get("neighborhood", ""),
                "lat": item.get("latitude"),
                "lng": item.get("longitude"),
            },
        )


register_scraper(ListingSource.RENTCOM, RentComScraper)

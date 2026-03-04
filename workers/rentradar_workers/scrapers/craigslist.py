"""Craigslist scraper — requests + BeautifulSoup."""

from __future__ import annotations

import logging
import random
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import (
    BaseScraper,
    RawListing,
    SourceConfig,
    parse_price,
)
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

# ── CSS Selectors ────────────────────────────────────────────────────

SEL_RESULT = "li.cl-static-search-result"
SEL_TITLE = ".title"
SEL_PRICE = ".price"
SEL_DETAILS = ".details"
SEL_POST_BODY = "section#postingbody"
SEL_MAP_ATTRS = "#map"  # data-latitude, data-longitude
SEL_ATTRGROUP = "p.attrgroup span"

NYC_CL_URL = "https://newyork.craigslist.org"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


class CraigslistScraper(BaseScraper):
    """Craigslist apartment scraper using requests + BeautifulSoup."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.CRAIGSLIST,
                base_url=NYC_CL_URL,
                scrape_interval_hours=2,
                max_pages=20,
                request_delay_range=(2.0, 4.0),
            )
        super().__init__(config)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    async def scrape(self, borough: str | None = None) -> list[RawListing]:
        """Scrape CL search results pages."""
        all_listings: list[RawListing] = []
        offset = 0
        per_page = 120

        for page in range(1, self.config.max_pages + 1):
            self._rate_limit()
            url = f"{self.config.base_url}/search/apa#search=1~gallery~{offset}~0"
            try:
                resp = self._session.get(url, timeout=20)
                resp.raise_for_status()
            except requests.RequestException:
                self.logger.exception("Failed to fetch page %d", page)
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
            offset += per_page

        return all_listings

    def parse_listing(self, raw: Any) -> RawListing:
        """Parse a single CL search result element (BS4 Tag)."""
        if not isinstance(raw, Tag):
            raise TypeError(f"Expected BS4 Tag, got {type(raw)}")
        return self._parse_result(raw)

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse CL search page HTML (for tests/offline)."""
        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []

        for result in soup.select(SEL_RESULT):
            try:
                listings.append(self.parse_listing(result))
            except Exception:
                self.logger.debug("Failed to parse CL result", exc_info=True)

        return listings

    def _parse_result(self, result: Tag) -> RawListing:
        """Parse a single CL search result element."""
        title_el = result.select_one(SEL_TITLE)
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = result.select_one(SEL_PRICE)
        price_text = price_el.get_text(strip=True) if price_el else ""

        link_el = result.select_one("a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = f"{self.config.base_url}{href}"

        details_el = result.select_one(SEL_DETAILS)
        details_text = details_el.get_text(strip=True) if details_el else ""

        return RawListing(
            source=ListingSource.CRAIGSLIST,
            source_url=href,
            address=title,
            price=parse_price(price_text),
            description=details_text,
            raw_data={"title": title, "price_raw": price_text},
        )


register_scraper(ListingSource.CRAIGSLIST, CraigslistScraper)

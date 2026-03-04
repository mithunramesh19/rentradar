"""Zillow scraper — Playwright + stealth."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from bs4 import BeautifulSoup, Tag

from rentradar_common.constants import ListingSource
from rentradar_workers.scrapers.base import (
    BaseScraper,
    RawListing,
    SourceConfig,
    parse_float,
    parse_int,
    parse_price,
)
from rentradar_workers.scrapers.tasks import register_scraper

logger = logging.getLogger(__name__)

# ── CSS Selectors ────────────────────────────────────────────────────

SEL_CARD = "article[data-test='property-card']"
SEL_CARD_LINK = "a[data-test='property-card-link']"
SEL_CARD_PRICE = "[data-test='property-card-price']"
SEL_CARD_ADDRESS = "address[data-test='property-card-addr']"
SEL_CARD_BEDS = "abbr[aria-label*='bed']"
SEL_CARD_BATHS = "abbr[aria-label*='bath']"
SEL_CARD_SQFT = "abbr[aria-label*='sqft']"
SEL_CARD_IMG = "img[data-test='property-card-img']"

ZILLOW_NYC_URL = "https://www.zillow.com/new-york-ny/rentals/"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]


class ZillowScraper(BaseScraper):
    """Zillow rental scraper using Playwright with stealth settings."""

    def __init__(self, config: SourceConfig | None = None) -> None:
        if config is None:
            config = SourceConfig(
                source=ListingSource.ZILLOW,
                base_url=ZILLOW_NYC_URL,
                scrape_interval_hours=12,
                max_pages=10,
                request_delay_range=(5.0, 8.0),
                use_browser=True,
            )
        super().__init__(config)

    async def scrape(self, borough: str | None = None) -> list[RawListing]:
        """Scrape Zillow using Playwright with stealth."""
        from playwright.sync_api import sync_playwright

        all_listings: list[RawListing] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            """)

            page = context.new_page()

            for page_num in range(1, self.config.max_pages + 1):
                self._rate_limit()
                url = (
                    f"{self.config.base_url}{page_num}_p/"
                    if page_num > 1
                    else self.config.base_url
                )

                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_selector(SEL_CARD, timeout=10000)
                    time.sleep(random.uniform(1, 3))

                    html = page.content()
                    page_listings = self.parse_listing_page(html)
                    if not page_listings:
                        break
                    all_listings.extend(page_listings)
                    self.logger.info(
                        "Page %d: %d listings (total %d)",
                        page_num,
                        len(page_listings),
                        len(all_listings),
                    )
                except Exception:
                    self.logger.exception("Failed on Zillow page %d", page_num)
                    break

            browser.close()

        return all_listings

    def parse_listing(self, raw: Any) -> RawListing:
        """Parse a single Zillow property card (BS4 Tag)."""
        if not isinstance(raw, Tag):
            raise TypeError(f"Expected BS4 Tag, got {type(raw)}")
        return self._parse_card(raw)

    def parse_listing_page(self, html: str) -> list[RawListing]:
        """Parse Zillow search page HTML (for tests/offline)."""
        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []

        for card in soup.select(SEL_CARD):
            try:
                listings.append(self.parse_listing(card))
            except Exception:
                self.logger.debug("Failed to parse Zillow card", exc_info=True)

        return listings

    def _parse_card(self, card: Tag) -> RawListing:
        """Parse a single Zillow property card."""

        def _text(sel: str) -> str:
            el = card.select_one(sel)
            return el.get_text(strip=True) if el else ""

        def _attr(sel: str, attr: str) -> str:
            el = card.select_one(sel)
            return el.get(attr, "") if el else ""

        address = _text(SEL_CARD_ADDRESS)
        href = _attr(SEL_CARD_LINK, "href")
        if href and not href.startswith("http"):
            href = f"https://www.zillow.com{href}"

        img_url = _attr(SEL_CARD_IMG, "src")

        return RawListing(
            source=ListingSource.ZILLOW,
            source_url=href or f"https://zillow.com#{address}",
            address=address,
            price=parse_price(_text(SEL_CARD_PRICE)),
            bedrooms=parse_int(_text(SEL_CARD_BEDS)),
            bathrooms=parse_float(_text(SEL_CARD_BATHS)),
            sqft=parse_int(_text(SEL_CARD_SQFT)),
            images=[img_url] if img_url else [],
        )


register_scraper(ListingSource.ZILLOW, ZillowScraper)
